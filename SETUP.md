# Talos Cluster Setup

This guide rebuilds the cluster represented by this repository. It assumes the node addresses and network ranges documented in [README.md](README.md).

## Prerequisites

Install:

- `talosctl`
- `kubectl`
- Helm
- Cilium CLI
- `kubeseal`

You also need:

- a domain whose DNS you control;
- Cloudflare API credentials for cert-manager DNS-01 challenges;
- a Google Cloud project and Web application OAuth client for protected routes;
- suitable disks for Talos, Longhorn and any local media volume.

Fork or clone the repository and replace the example `joeriberman.nl`
hostnames, node addresses, email allowlist, local storage path and node names.
Do not reuse the encrypted secrets: Sealed Secrets ciphertext is bound to the
controller key of the cluster that created it.

Boot each target node from a Talos installer image and confirm it is reachable in maintenance mode. Verify installation disk and interface names on each machine rather than assuming `/dev/sdb` and `enp1s0` are correct:

```bash
talosctl get disks --insecure --nodes <node-address>
talosctl get links --insecure --nodes <node-address>
```

## 1. Generate Talos configuration

Generate secrets once, then generate machine configurations with Cilium as the CNI and kube-proxy disabled:

```bash
talosctl gen secrets --output-file talos/secrets.yml

talosctl gen config homelab-cluster https://10.0.0.10:6443 \
  --output-dir talos \
  --with-secrets talos/secrets.yml \
  --config-patch @talos/patches/cilium-cni.yaml \
  --config-patch @talos/patches/disable-kube-proxy.yaml
```

Review both generated files before applying them. Configure the correct installation disk, static address or DHCP reservation, interface, routes and certificate SANs. Generated machine configurations contain private keys and must remain outside Git.

Generate or patch a separate worker configuration for each physical worker when
their disks, interfaces, addresses or machine-specific mounts differ. The
media worker additionally needs the local filesystem mounted at the path used
by the `jellyfin-media` PV.

Validate them:

```bash
talosctl validate --config talos/controlplane.yaml --mode metal
talosctl validate --config talos/worker.yaml --mode metal
```

## 2. Install Talos

These commands erase the configured installation disks:

```bash
talosctl apply-config --insecure \
  --nodes 10.0.0.10 \
  --file talos/controlplane.yaml

talosctl apply-config --insecure \
  --nodes 10.0.0.20 \
  --file talos/worker.yaml

talosctl apply-config --insecure \
  --nodes 10.0.0.30 \
  --file talos/worker-2.yaml
```

Remove the installer media after installation and wait for both machines to reboot.

## 3. Configure talosctl and bootstrap etcd

```bash
talosctl config merge talos/talosconfig
talosctl bootstrap --nodes 10.0.0.10
talosctl kubeconfig --nodes 10.0.0.10 kubeconfig
export KUBECONFIG="$PWD/kubeconfig"
```

The nodes remain `NotReady` until Cilium is installed.

## 4. Install Cilium

Build the pinned dependency and install the repository wrapper chart:

```bash
helm dependency build apps/networking/cilium
helm upgrade --install cilium apps/networking/cilium \
  --namespace kube-system

cilium status --wait
```

Verify full kube-proxy replacement before continuing:

```bash
kubectl -n kube-system exec ds/cilium -c cilium-agent -- \
  cilium-dbg status --verbose

kubectl -n kube-system get daemonset kube-proxy
```

`KubeProxyReplacement` must be `True`, and the final command should report that kube-proxy does not exist.

## 5. Install Argo CD

```bash
helm dependency build apps/core/argocd
helm upgrade --install argocd apps/core/argocd \
  --namespace argocd \
  --create-namespace
```

Wait for its controllers:

```bash
kubectl rollout status deployment/argocd-server -n argocd
kubectl rollout status deployment/argocd-repo-server -n argocd
kubectl rollout status statefulset/argocd-application-controller -n argocd
```

## 6. Enable GitOps

Apply Cilium and Argo CD self-management, followed by the platform and workload ApplicationSets:

```bash
kubectl apply -f apps/app-of-apps/cilium.yaml
kubectl apply -f apps/app-of-apps/argocd.yaml
kubectl apply -f apps/app-of-apps/platform-applications.yaml
kubectl apply -f apps/app-of-apps/workload-applications.yaml
```

Monitor reconciliation:

```bash
kubectl get applications,applicationsets -n argocd
kubectl get pods -A
```

## 7. Configure DNS, TLS and Google OIDC

Create the Cloudflare API token and Google OAuth client outside the cluster,
then create namespace-scoped plaintext Secret manifests locally and seal them
with your cluster's Sealed Secrets controller. Never commit the plaintext
files.

For the Google client, choose **Web application** and register one exact
redirect URI for every protected hostname:

```text
https://<hostname>/oauth2/callback
```

Store the client ID under the `client-id` key and the client secret under the
`client-secret` key. Seal both Secrets for the `envoy-gateway` namespace and
replace the example ciphertext in
`apps/platform/envoy-gateway/templates/sealed-secret.yaml`.

Kyverno watches HTTPRoutes labeled `oidc: "true"`. For each matching route it
clones the two credentials into the workload namespace and generates an Envoy
OIDC `SecurityPolicy`. Configure your own allowed email addresses in
`apps/platform/kyverno/values.yaml`.

Point the application DNS records at your public address and forward TCP 443
to the Envoy Gateway LoadBalancer address. Split DNS or NAT loopback is needed
to use the same names from the LAN.

## 8. Validate networking, TLS, authentication and storage

```bash
cilium status
kubectl get ciliumloadbalancerippool,ciliuml2announcementpolicy
kubectl get gateway,httproute -A
kubectl get clusterissuer
kubectl get certificate -n envoy-gateway
kubectl get securitypolicy -A
kubectl get storageclass
kubectl -n longhorn get volumes.longhorn.io
```

Expected results:

- Gateway address is `10.0.0.242`.
- Apex and wildcard certificates are Ready.
- `platform-rwo` is the only default StorageClass.
- Active Longhorn volumes have two healthy replicas.
- Unauthenticated requests to protected routes redirect to
  `accounts.google.com`.

## 9. Initialize Vault only on a new empty cluster

Do not initialize Vault if it already contains data.

```bash
kubectl exec -it -n vault vault-0 -- \
  vault operator init -key-shares=1 -key-threshold=1
```

Store the unseal key and initial root token in a secure password manager. Unseal the first member, join the second member to Raft if required, then unseal it:

```bash
kubectl exec -it -n vault vault-0 -- vault operator unseal
kubectl exec -it -n vault vault-1 -- vault operator unseal
kubectl get pods -n vault
```

## Operations

### Upgrade Talos

Upgrade one node at a time. Upgrade and verify each worker before upgrading the
control plane:

```bash
talosctl upgrade --nodes 10.0.0.20 --image <installer-image>
talosctl -n 10.0.0.10,10.0.0.20,10.0.0.30 health

talosctl upgrade --nodes 10.0.0.30 --image <installer-image>
talosctl -n 10.0.0.10,10.0.0.20,10.0.0.30 health

talosctl upgrade --nodes 10.0.0.10 --image <installer-image>
talosctl -n 10.0.0.10,10.0.0.20,10.0.0.30 health
```

Vault must be manually unsealed after either Vault pod restarts in the current
configuration.

### Diagnose certificate issuance

```bash
kubectl get certificate,certificaterequest,order,challenge -A
kubectl describe challenge -n envoy-gateway <challenge-name>
kubectl logs -n cert-manager deployment/cert-manager
```

### Diagnose storage

```bash
kubectl -n longhorn get volumes.longhorn.io
kubectl -n longhorn get replicas.longhorn.io
kubectl get pv,pvc -A
```

### Access Argo CD locally

The normal endpoint is `https://argocd.joeriberman.nl`. For emergency access:

```bash
kubectl port-forward service/argocd-server -n argocd 8080:443
```
