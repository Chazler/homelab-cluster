# Talos Cluster Setup

This guide rebuilds the cluster represented by this repository. It assumes the node addresses and network ranges documented in [README.md](README.md).

## Prerequisites

Install:

- `talosctl`
- `kubectl`
- Helm
- Cilium CLI
- `kubeseal`

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

## 7. Validate networking, TLS and storage

```bash
cilium status
kubectl get ciliumloadbalancerippool,ciliuml2announcementpolicy
kubectl get gateway,httproute -A
kubectl get clusterissuer
kubectl get certificate -n envoy-gateway
kubectl get storageclass
kubectl -n longhorn get volumes.longhorn.io
```

Expected results:

- Gateway address is `10.0.0.242`.
- Apex and wildcard certificates are Ready.
- `platform-rwo` is the only default StorageClass.
- Active Longhorn volumes have two healthy replicas.

## 8. Initialize Vault only on a new empty cluster

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

Upgrade one node at a time. Start with the worker and verify cluster and storage health before upgrading the control plane:

```bash
talosctl upgrade --nodes 10.0.0.20 --image <installer-image>
talosctl -n 10.0.0.10,10.0.0.20 health

talosctl upgrade --nodes 10.0.0.10 --image <installer-image>
talosctl -n 10.0.0.10,10.0.0.20 health
```

Vault must be manually unsealed after either Vault pod restarts until Google Cloud KMS auto-unseal is configured.

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
