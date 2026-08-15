# Homelab Kubernetes Cluster

Three-node Talos Linux cluster managed declaratively with Argo CD.

## Current state

Last verified: 2026-08-14.

| Role | Name | Address |
| --- | --- | --- |
| Control plane and storage | `k8s-controlplane-1` | `10.0.0.10` |
| Worker and storage | `k8s-worker-1` | `10.0.0.20` |
| Worker, storage, media and home automation | `k8s-worker-2` | `10.0.0.30` |
| Envoy Gateway | `envoy-gateway` | `10.0.0.242` |

- Talos Linux 1.13.7
- Kubernetes 1.35.0
- Cilium 1.18.5 with full kube-proxy replacement, LB-IPAM and L2 announcements
- Argo CD with automated pruning and self-healing
- Envoy Gateway and Gateway API
- cert-manager with Cloudflare DNS-01 validation
- Longhorn with two replicas per active volume
- Sealed Secrets
- Kyverno-generated Envoy OIDC policies
- Vault Community Edition with integrated Raft storage

The workload layer includes Home Assistant; a media stack built around
Jellyfin, Jellyseerr, Jellystat, Sonarr, Radarr, Prowlarr, Bazarr, SABnzbd and
Deluge; and a services stack containing AdGuard Home, Umami, Polylearn, Idea
Triage and n8n. Umami and Idea Triage use separate roles and databases on one
PostgreSQL instance. Container images are pinned by digest.

Metrics Server, Prometheus, Grafana, Alertmanager and external-dns are not currently installed.

## Network

| Network | Range |
| --- | --- |
| Node network | `10.0.0.0/16` |
| Pod network | `10.244.0.0/16` |
| Service network | `10.96.0.0/12` |
| Cilium LoadBalancer pool | `10.0.0.240/28` (`.241` through `.254`) |

Envoy Gateway uses `10.0.0.242`. AdGuard DNS uses `10.0.0.243` and exposes
TCP and UDP port 53 directly to the LAN.

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

## Ingress and authentication

Public DNS points the application hostnames at the home connection, where TCP
443 is forwarded to the Envoy Gateway address. cert-manager obtains the apex
and wildcard certificates with Cloudflare DNS-01 challenges.

Namespaces opt into a synchronized copy of the sealed OAuth credentials with
the `oidc-secrets: "true"` label. Administrative HTTPRoutes opt into Google
OIDC with the `oidc: "true"` label, which makes Kyverno generate an Envoy
`SecurityPolicy` with an email allowlist. Public-facing services such as
Jellyfin do not carry this route label. Deluge has no public route and is
reachable only by the other media services through its VPN pod.

AdGuard Home, Umami, Idea Triage and n8n use the same OIDC protection.
Polylearn is intentionally public. AdGuard's DNS listener is a separate Cilium
LoadBalancer service and does not pass through Envoy.

## Bootstrap order

For a new cluster, follow [SETUP.md](SETUP.md). The required order is:

1. Replace the example addresses, hostnames, storage paths and secret material.
2. Generate and apply Talos machine configurations with Cilium CNI and kube-proxy patches.
3. Bootstrap etcd and retrieve kubeconfig.
4. Install Cilium directly from `apps/networking/cilium`.
5. Install Argo CD directly from `apps/core/argocd`.
6. Apply the four resources in `apps/app-of-apps/`.
7. Confirm every Argo CD application is synced and healthy.

## Routine health checks

```bash
talosctl -n 10.0.0.10,10.0.0.20,10.0.0.30 health
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

Google Cloud KMS auto-unseal is not configured in the current state.

The in-progress auto-unseal migration runbook is in
[`apps/platform/vault/README.md`](apps/platform/vault/README.md). It requires a
planned outage and an interactive use of the existing Shamir key.

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

The Google OAuth client used by Envoy is represented in Git only by
`apps/platform/envoy-gateway/templates/sealed-secret.yaml`. A replacement
deployment must create its own Web application client, register every
`https://<hostname>/oauth2/callback` URI, seal both credentials for the
`envoy-gateway` namespace, and replace the encrypted values in that manifest.

## Current limitations

- A single control-plane node means the Kubernetes API and etcd are not highly available.
- Longhorn uses two replicas per volume. The third node adds placement options,
  but two replicas do not replace an external backup.
- The two-member Vault Raft cluster cannot maintain quorum after losing either member.
- The media library is a retained local PV on `k8s-worker-2`; it is node-bound
  and is not replicated by Longhorn.
- Umami and Idea Triage share one PostgreSQL instance. Their databases and
  roles are isolated, but the database pod and volume remain a shared failure
  domain.
- Vault must be manually unsealed after restarts.
