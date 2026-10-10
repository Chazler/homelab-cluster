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
  --talos-version v1.13.7 \
  --kubernetes-version v1.36.5 \
  --output-dir talos \
  --with-secrets talos/secrets.yml \
  --config-patch @talos/patches/cilium-cni.yaml \
  --config-patch @talos/patches/disable-kube-proxy.yaml \
  --config-patch @talos/patches/dns.yaml
```

Match the generation versions to `talos/versions.yaml`. The explicit Talos
version keeps the tracked v1alpha1 patches compatible when using a newer CLI;
fresh Talos 1.14 configurations use separate network configuration documents
and require converting these legacy network patches before generation.

Review both generated files before applying them. Configure the correct installation disk, static address or DHCP reservation, interface, routes and certificate SANs. Generated machine configurations contain private keys and must remain outside Git.

Generate or patch a separate worker configuration for each physical worker when
their disks, interfaces, addresses or machine-specific mounts differ. The
media worker additionally needs the local filesystem mounted at the path used
by the media library's PV.

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

The shared `talos/patches/dns.yaml` sets the LAN router (`10.0.0.1`) as the
upstream resolver and disables `machine.features.hostDNS.forwardKubeDNSToHost`.
Host DNS caching remains enabled. Talos renders `/system/resolved/resolv.conf`
for kubelet with the router address; CoreDNS's `dnsPolicy: Default` inherits
that resolver. Keep the standard Corefile's `forward . /etc/resolv.conf` so
Talos's Kubernetes upgrade manifest reconciliation preserves this behavior.
This also preserves the router's resolution of UniFi Protect `*.id.ui.direct`
hostnames used by Home Assistant.

### Repair DNS configuration on an existing cluster

Apply the shared DNS patch one node at a time without rebooting. After each
node, confirm its pod resolver contains `nameserver 10.0.0.1` and that the node
remains Ready before continuing:

```bash
talosctl patch machineconfig --nodes 10.0.0.20 --mode no-reboot --patch @talos/patches/dns.yaml
talosctl read /system/resolved/resolv.conf --nodes 10.0.0.20
kubectl get nodes
# Repeat for 10.0.0.30, then 10.0.0.10.
```

Include the same patch when regenerating local machine configurations, or
patch each existing local full machine configuration with
`talosctl machineconfig patch <config-file> --patch @talos/patches/dns.yaml --output <patched-file>`.
Generated files contain credentials and must stay outside Git.

Once all three pod resolver files contain the router address, remove the
previous manual Corefile override and recreate CoreDNS pods so they inherit
the updated resolver file:

```bash
kubectl get configmap -n kube-system coredns -o json | \
  python3 -c "
import json, sys
cm = json.load(sys.stdin)
cm['data']['Corefile'] = cm['data']['Corefile'].replace(
    'forward . 10.0.0.1 {', 'forward . /etc/resolv.conf {')
print(json.dumps(cm))
" | kubectl apply -f -
kubectl rollout restart deployment coredns -n kube-system
kubectl rollout status deployment coredns -n kube-system
```

Verify cluster service names, external domains and the actual UniFi Protect
hostname from a workload pod. Run `talosctl upgrade-k8s --to <next-minor-patch>
--dry-run --pre-pull-images=false` and confirm it no longer changes the
CoreDNS forwarding line before upgrading Kubernetes.

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

Optionally, if a private services repo is configured (see "Private services repo" below):

```bash
kubectl apply -f apps/app-of-apps/private-applications.yaml
```

Monitor reconciliation:

```bash
kubectl get applications,applicationsets -n argocd
kubectl get pods -A
```

## 7. Configure DNS, TLS and Google sign-in

Create the Cloudflare API token and Google OAuth client outside the cluster,
then create namespace-scoped plaintext Secret manifests locally and seal them
with your cluster's Sealed Secrets controller. Never commit the plaintext
files.

For the Google client, choose **Web application** and register only the
Authentik callback URL:

```text
https://auth.joeriberman.nl/source/oauth/callback/google/
```

Store the client ID under the `client-id` key and the client secret under the
`client-secret` key in Vault at `authentik/google-oauth`. The Vault secret sync
creates the `authentik-google-oauth` Secret for the Authentik server and worker.

Kyverno watches HTTPRoutes labeled `authentik-forward-auth: "true"` and
generates a fail-closed Envoy external-auth `SecurityPolicy` plus a public
`/outpost.goauthentik.io` route for each hostname. Each private hostname has a
separate Authentik forward-auth provider and application; manage authorization
policies on that Authentik application.

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
- Unauthenticated requests to protected routes redirect through Authentik.

## 9. Initialize Vault only on a new empty cluster

Do not initialize Vault if it already contains data. Vault auto-unseals with
GCP KMS (`apps/platform/vault/values.yaml`), so init produces recovery keys
rather than unseal keys:

```bash
kubectl exec -it -n vault vault-0 -- \
  vault operator init -recovery-shares=1 -recovery-threshold=1
```

Store the recovery key and initial root token in a secure password manager.
Vault unseals itself automatically via GCP KMS; the recovery key is only
needed for break-glass operations such as seal migration, so no manual
`vault operator unseal` step is required. Confirm the other Raft members join
and unseal on their own:

```bash
kubectl get pods -n vault
kubectl exec -n vault vault-1 -- sh -c 'VAULT_CACERT=/vault/userconfig/vault-server-tls/ca.crt vault status'
kubectl exec -n vault vault-2 -- sh -c 'VAULT_CACERT=/vault/userconfig/vault-server-tls/ca.crt vault status'
```

## Operations

### Catch up Longhorn volume engines

Treat the manager chart and each volume's engine as separate upgrades. Before
either operation, take an independent etcd snapshot and verified application
PVC backups. A Longhorn volume snapshot alone is not an off-cluster backup.
Keep user-excluded media claims out of backup helpers. If no Longhorn backup
target is configured, local cold PVC archives and resource exports provide an
independent recovery bundle, but are not a native Longhorn system backup.

Inventory the running engine versions and volume health before choosing a path:

```bash
kubectl -n longhorn get volumes.longhorn.io
kubectl -n longhorn get engineimages.longhorn.io
kubectl -n longhorn get engines.longhorn.io
```

For manager 1.12.1, the documented V1 live engine upgrade path starts at 1.11.x.
Use the documented offline procedure for older 1.10.1 engines: pause Argo
reconciliation, record and stop every writer of the selected PVC, and wait for
the volume to detach. In Longhorn, use the volume's **Upgrade Engine** operation
to select the default engine supplied by the installed manager, then restore
the original workload replicas. Start with one low-impact volume and verify
the engine version, replica health, filesystem writability and application
behaviour before proceeding. Pause the monitoring operator before stopping
its managed StatefulSets. Keep unused volumes detached.

After the old engines have caught up and all workloads are healthy, prepare
the next manager upgrade separately through GitOps. Manager 1.13.0 supports V1
live engine upgrades from 1.12.x on healthy blockdev volumes; iSCSI frontends
require the offline procedure. V2 volumes have a separate instance-manager
upgrade procedure. Never remove an old engine image while volumes reference it.

Stop on degraded or faulted volumes, failed mounts, read-only filesystems, or
application errors. Longhorn does not support manager downgrades: reverting
the chart is not a recovery plan. Preserve backups and review the matching
restore procedure before maintenance.

References: [1.12.1 engine upgrades](https://longhorn.io/docs/1.12.1/deploy/upgrade/upgrade-engine/),
[1.13.0 manager upgrades](https://longhorn.io/docs/1.13.0/deploy/upgrade/),
and [1.13.0 engine upgrades](https://longhorn.io/docs/1.13.0/deploy/upgrade/upgrade-engine/).

### Upgrade Kubernetes

Before a minor upgrade, save an etcd snapshot and the live Talos machine
configurations on an administration laptop outside Git. Back up application
PVCs separately; an etcd snapshot does not include their files. For consistent
filesystem backups, stop the volume's writers, archive the PVC from a
read-only helper mount, verify the archive and checksum, then restore the
original workload replicas. Exclude user-selected media PVCs by never mounting
them in backup helpers. Temporary replica changes require pausing Argo's
application controller; pause the monitoring operator as well when stopping
its managed StatefulSets, and restore both controllers afterwards.

```bash
# Use a private directory outside Git for snapshots and generated configs.
talosctl --nodes 10.0.0.10 etcd snapshot <backup-dir>/etcd.snapshot

# Upgrade one Kubernetes minor at a time, using an explicit target patch.
talosctl --nodes 10.0.0.10 upgrade-k8s --to 1.36.5 --dry-run --pre-pull-images=false
talosctl --nodes 10.0.0.10 upgrade-k8s --to 1.36.5

kubectl get nodes -o wide
kubectl get applications,applicationsets -n argocd
kubectl get pods -A
talosctl --nodes 10.0.0.10 health --control-plane-nodes 10.0.0.10 --worker-nodes 10.0.0.20,10.0.0.30
```

`upgrade-k8s` discovers every node, updates control-plane components and
kubelets sequentially, waits for health, and reconciles bootstrap manifests.
Keep kube-proxy disabled because Cilium owns Service routing. Review the
bootstrap manifest diff, especially CoreDNS, before applying the upgrade.
Kubelet updates can restart workloads; the single control plane may also
briefly interrupt API access. If interrupted, rerun the same explicit target
command to continue rather than assuming all components upgraded.

After live validation, update `talos/versions.yaml`, the generation versions
above, and the Kubernetes version in README. Refresh ignored local machine
configurations from the live nodes so a future apply cannot revert the
Kubernetes component images. Keep snapshots and generated configurations
private: they contain credentials.

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

Vault auto-unseals via GCP KMS after a pod restart; no manual unseal step is
required. If GCP KMS is unreachable, affected pods stay sealed until KMS
access is restored — the stored recovery key is only needed for break-glass
operations such as seal migration, not for routine restarts. See
"Vault TLS and recovery" below for the certificate chain and restart order.

### Vault TLS and recovery

Vault's client listener is TLS-only. `apps/platform/vault/templates/internal-ca.yaml`
defines a self-signed `vault-selfsigned` Issuer, a 5-year `vault-ca`
Certificate, and a `vault-ca-issuer` CA Issuer that signs the 90-day
`vault-server-tls` server certificate mounted into every Vault pod. Raft
request forwarding on the cluster port (8201) is always encrypted with
Vault's own internally managed cluster TLS, independent of this listener
certificate.

The CA's public certificate (not sensitive) is duplicated as a literal value
in `apps/platform/vault/values.yaml` (for the gateway's `BackendTLSPolicy`)
and `apps/platform/vault-secret-sync/values.yaml` (for every Vault Secrets
Operator `VaultConnection`). If the root CA is ever rotated, re-fetch it and
update both files:

```bash
kubectl get secret vault-ca-tls -n vault -o jsonpath='{.data.tls\.crt}' | base64 -d
```

`vault-server-tls` renews automatically 30 days before expiry, but Vault does
not hot-reload listener certificates, so each pod needs a rolling restart
after renewal to pick up the new certificate. The Vault StatefulSet uses the
`OnDelete` update strategy, so restarts are always deliberate:

```bash
kubectl delete pod vault-2 -n vault   # verify Sealed=false, HA Mode=standby before continuing
kubectl delete pod vault-1 -n vault
kubectl delete pod vault-0 -n vault   # restart the active/leader node last
```

Each pod auto-unseals via GCP KMS and rejoins Raft on its own; no `vault
operator unseal` step is needed. Deleting the active node causes a brief,
automatic Raft leader election to one of the standbys.

### Private services repo

`apps/app-of-apps/private-applications.yaml` is an ApplicationSet, scoped to
the `private` AppProject, that mirrors `workload-applications.yaml` but
sources from the private `git@github.com:Chazler/homelab-private.git` repo
instead: every top-level `apps/*` directory in that repo becomes an
Application, normally in its matching namespace. The split utility applications
retain the existing `services` namespace; `media-stack` retains `jellyfin`.
`apps/archive` is excluded from discovery. The `hermes` Application uses
`private-hermes-admin`, scoped to the existing `services` namespace and its
ClusterRoleBinding permission. Its existing `hermes-k8s-admin` ServiceAccount
remains bound to `cluster-admin`; this exception belongs only to the Hermes
chart. Hermes can read Secrets
and make changes anywhere in Kubernetes, so keep its access limited to
trusted operators. Its API credential is a rotating, pod-projected token,
not a stored admin kubeconfig.
Argo CD authenticates with a read-only deploy key, stored as a `SealedSecret`
at `apps/core/argocd/templates/private-repo-secret.yaml` (part of the
self-managed `argocd` chart, so it reconciles like any other in-repo change).

Vault access for a namespace created by the private repo works the same way
as any platform/workload namespace, except the `VaultConnection`/`VaultAuth`/
`VaultStaticSecret` manifests must live in the private chart itself (via
`apps/platform/vault-secret-sync/templates/vault-static-secrets.yaml` for the
exact shape to copy) rather than in this repo's `vault-secret-sync` values,
so secret names/paths for private services aren't exposed here either. Before
a private chart's `VaultStaticSecret` will work, create its Vault
kubernetes-auth role and policy once (break-glass, not tracked in git — same
as every other namespace's):

```bash
kubectl exec -it -n vault vault-0 -- sh -c '
VAULT_CACERT=/vault/userconfig/vault-server-tls/ca.crt
export VAULT_CACERT
vault policy write vault-sync-<namespace> - <<EOF
path "kv/data/<namespace>/*" {
  capabilities = ["read"]
}
path "kv/metadata/<namespace>/*" {
  capabilities = ["list"]
}
EOF
vault write auth/kubernetes/role/vault-sync-<namespace> \
  bound_service_account_names=vault-secrets \
  bound_service_account_namespaces=<namespace> \
  audience=vault \
  policies=vault-sync-<namespace> \
  ttl=24h
'
```

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


### Split or rename an Argo application without replacing storage

Validate the union of the replacement charts against the existing manifests:
resource identities, workload specs, selectors, routes, Vault paths and PVC
specifications must remain unchanged. Save current Applications, controller
replica counts and PVC/PV identities privately before the handoff.

For an ownership transfer, pause both the ApplicationSet controller and the
application controller. Remove the old Application resource finalizers and
delete only the obsolete Application objects, leaving their workloads and
storage intact. Publish the replacement chart paths and ApplicationSet rules. Apply the tracked
ApplicationSet manifest as in the bootstrap procedure, then resume the application controller to reconcile those rules before resuming
the ApplicationSet controller. The new Applications adopt the existing resources.
Verify tracking ownership, sync and health, workload identities and PVC/PV UIDs.
Do not cascade-delete an old Application during a rename or split.

Directory discovery can briefly return a cached tree and recreate retired
Applications. During the handoff, temporarily pin the live generator revision
to the published private commit and enable `preserveResourcesOnDeletion`.
Remove deletion finalizers from any recreated obsolete Applications before
refreshing discovery. After the replacement Applications have adopted every
resource, reapply the tracked `main` generator configuration and remove the
temporary preservation override. Verify discovery remains correct on `main`.

When archiving an application, retain its namespace and PVCs under an active
retained-state chart with `Prune=false,Delete=false`. Stop and remove only its
workloads, services, routes and reconciliation resources. Preserve Vault data
and runtime credentials for restoration; never delete its PVCs or namespace as
part of archiving. Exclude the archive directory from application discovery,
Helm CI and Renovate.

### Migrate PostgreSQL major versions

A PostgreSQL major image change requires a data migration. Rehearse a logical
restore on a new `platform-rwo` PVC before replacing the running database.
Preserve each original PVC with `Prune=false,Delete=false`; keep the new PVC
explicitly configured in the owning chart. Keep database dumps, role/password
exports, live resources and checksums in a private laptop directory outside Git.
Exclude archived applications and externally managed databases from active
cluster migrations.

For a final cutover, pause the Argo application controller and stop all database
writers: Umami and Idea Triage for `services/postgres`, Jellystat for
`jellyfin/jellystat-db`, and Authentik server/worker for its PostgreSQL instance.
Verify there are no remaining client sessions. Export cluster roles with
`pg_dumpall --globals-only` and each non-template database with `pg_dump -Fc`.
Restore roles and databases into the rehearsed target with `pg_restore
--create --clean --if-exists --exit-on-error`; compare table row counts while
writers remain stopped and refresh statistics with `vacuumdb --analyze-in-stages`.
Disable login and clear the password on any temporary restore administrator
before connecting production clients. PostgreSQL requires its bootstrap role to
retain SUPERUSER and system-object ownership; keep that role inaccessible.

PostgreSQL 18 uses `/var/lib/postgresql/18/docker` below the PVC mount at
`/var/lib/postgresql` for the shared and Jellystat databases. Authentik retains
its upstream chart's `/bitnami/postgresql/data` layout and non-root UID 1001.
Its explicit `existingClaim` avoids replacing the old PVC. Changing a StatefulSet
from `volumeClaimTemplates` to `existingClaim` requires stopping the StatefulSet
and recreating its controller during the documented maintenance window; retain
its original claim. Do not delete any PVC or PV as part of this operation.

After restoring, stop the migration helpers, stop the old database controllers,
publish the validated charts. Before resuming reconciliation, pause the
ApplicationSet controller and temporarily pin each affected Application source
to its published commit SHA. Clear any pending sync operation against an older
revision and request a hard refresh. This prevents cached `main` manifests from
reverting the database image or PVC during controller startup. Resume the
application controller, verify successful sync at the pinned revisions, then
restore sources to `main` and the ApplicationSet controller to its original
replicas. Verify PostgreSQL
versions, database integrity, application readiness, authentication, and all
affected Application health. Retain original volumes and local dumps until the
migration has been accepted. To roll back before new production writes, pause
Argo, stop clients, restore the old chart/controller definition and original PVC
bindings, then resume reconciliation. After new writes, reconcile or migrate
that data before rollback to avoid losing changes.
