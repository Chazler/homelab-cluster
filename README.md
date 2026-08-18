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
- Authentik forward-auth for private application routes
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

Private HTTPRoutes use the `authentik-forward-auth: "true"` label. Kyverno
generates a fail-closed Envoy external-auth `SecurityPolicy`; each application
chart also exposes an unprotected `/outpost.goauthentik.io` route to the managed
Authentik proxy outpost. Authentik has a separate forward-auth provider and
application for every private hostname, so application policies remain isolated.
Google sign-in is configured only as an Authentik source and uses the
`auth.joeriberman.nl` callback.

Jellyfin, Jellyseerr, Polylearn, Home Assistant and OpenClaw are
intentionally public (Home Assistant's companion apps require direct,
unauthenticated access to its own login; OpenClaw authenticates its iOS
client natively via a shared token, since a native client cannot complete
Authentik's browser SSO redirect). n8n splits its hostname across two
HTTPRoutes: the editor UI stays behind Authentik forward-auth, while
`/webhook`, `/webhook-waiting`, `/mcp-server`, `/mcp-oauth` and the
`/.well-known/oauth-*` discovery paths are public and unauthenticated at
the gateway, since webhook senders and MCP clients can't complete a
browser SSO redirect; those paths rely on n8n's own per-node auth and
its native MCP OAuth2 authorization server instead. Deluge has no
public route and is reachable only by the other media services through its VPN
pod. AdGuard's DNS listener is a separate Cilium LoadBalancer service and does
not pass through Envoy.

## Secrets

Runtime application credentials are stored in Vault KV v2 and synchronized into
Kubernetes Secrets by Vault Secrets Operator. Only encrypted bootstrap
`SealedSecret` resources, such as Vault's Google Cloud KMS credential, belong
in Git. The following local files are intentionally ignored:

- `kubeconfig`
- `talos/secrets.yml`
- `talos/talosconfig`
- `talos/controlplane.yaml`
- `talos/worker.yaml`
- plaintext `secret.yaml` files

The Google OAuth client used by Authentik is synchronized from Vault only into
the Authentik namespace. Operational procedures are in [SETUP.md](SETUP.md)
and [cheatsheet.md](cheatsheet.md).

## Current limitations

- A single control-plane node means the Kubernetes API and etcd are not highly available.
- Longhorn uses two replicas per volume. The third node adds placement options,
  but two replicas do not replace an external backup.
- The media library is a retained local PV on `k8s-worker-2`; it is node-bound
  and is not replicated by Longhorn.
- Umami and Idea Triage share one PostgreSQL instance. Their databases and
  roles are isolated, but the database pod and volume remain a shared failure
  domain.
