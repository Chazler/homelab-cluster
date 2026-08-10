# Homelab Kubernetes Cluster

Two-node Talos Linux cluster managed declaratively with Argo CD.

## Current state

Last verified: 2026-08-10.

| Role | Name | Address |
| --- | --- | --- |
| Control plane and storage | `k8s-controlplane-1` | `10.0.0.10` |
| Worker and storage | `k8s-worker-1` | `10.0.0.20` |
| Envoy Gateway | `envoy-gateway` | `10.0.0.242` |

- Talos Linux 1.12.0
- Kubernetes 1.35.0
- Cilium 1.18.5 with full kube-proxy replacement, LB-IPAM and L2 announcements
- Argo CD with automated pruning and self-healing
- Envoy Gateway and Gateway API
- cert-manager with Cloudflare DNS-01 validation
- Longhorn with two replicas per active volume
- Sealed Secrets
- Kyverno-generated Envoy OIDC policies
- Vault Community Edition with integrated Raft storage

Metrics Server, Prometheus, Grafana, Alertmanager and external-dns are not currently installed.

## Network

| Network | Range |
| --- | --- |
| Node network | `10.0.0.0/16` |
| Pod network | `10.244.0.0/16` |
| Service network | `10.96.0.0/12` |
| Cilium LoadBalancer pool | `10.0.0.240/28` (`.241` through `.254`) |

Cilium owns Kubernetes Service routing. Talos has `cluster.proxy.disabled: true`; do not reinstall kube-proxy unless `cilium.kubeProxyReplacement` is disabled first.

## Repository layout

```text
apps/
  app-of-apps/       Argo CD Applications and ApplicationSets
  core/              Argo CD self-management
  networking/        Cilium
  platform/          cert-manager, Envoy, Kyverno, Longhorn, Vault, secrets
  workloads/         User workloads
talos/
  patches/           Safe, tracked Talos patches
  controlplane.yaml  Generated locally; ignored because it contains credentials
  worker.yaml        Generated locally; ignored because it contains credentials
```

Every directory selected by an ApplicationSet must be a valid Helm chart. Argo CD tracks `main` and applies changes with automated prune and self-heal.

## Bootstrap order

For a new cluster, follow [SETUP.md](SETUP.md). The required order is:

1. Generate and apply Talos machine configurations with Cilium CNI and kube-proxy patches.
2. Bootstrap etcd and retrieve kubeconfig.
3. Install Cilium directly from `apps/networking/cilium`.
4. Install Argo CD directly from `apps/core/argocd`.
5. Apply the four resources in `apps/app-of-apps/`.
6. Confirm every Argo CD application is synced and healthy.

## Routine health checks

```bash
talosctl -n 10.0.0.10,10.0.0.20 health
kubectl get nodes
kubectl get pods -A
cilium status
kubectl get applications -n argocd
kubectl get certificate -n envoy-gateway
kubectl -n longhorn get volumes.longhorn.io
```

## Vault after a restart

Vault currently uses manual Shamir unseal. Enter the key interactively so it is not recorded in shell history:

```bash
kubectl exec -it -n vault vault-0 -- vault operator unseal
kubectl exec -it -n vault vault-1 -- vault operator unseal
kubectl get pods -n vault
```

Google Cloud KMS auto-unseal is planned but not configured. Migrating the seal requires a maintenance window and `vault operator unseal -migrate`; do not add a KMS seal block and restart Vault without following the migration procedure.

## Secrets

Only encrypted `SealedSecret` resources belong in Git. The following local files are intentionally ignored:

- `kubeconfig`
- `talos/secrets.yml`
- `talos/talosconfig`
- `talos/controlplane.yaml`
- `talos/worker.yaml`
- plaintext `secret.yaml` files

Create or update a sealed secret with:

```bash
kubeseal \
  --controller-namespace sealed-secrets \
  --controller-name sealed-secrets \
  --format yaml \
  < secret.yaml > sealed-secret.yaml
```

Never pass unseal keys, root tokens, cloud credentials or plaintext application secrets on a command line that will be retained in shell history.

## Current limitations

- A single control-plane node means the Kubernetes API and etcd are not highly available.
- Two-node Longhorn replication tolerates one replica failure but does not replace an external backup.
- The two-member Vault Raft cluster cannot maintain quorum after losing either member.
- A third node is planned; after it joins, expand Vault to three members and reconsider three Longhorn replicas.
- Vault must be manually unsealed after restarts until Google Cloud KMS migration is completed.
