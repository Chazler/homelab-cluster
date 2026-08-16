# Media stack

This chart deploys Jellyfin, Jellyseerr, Jellystat/PostgreSQL, Sonarr, Sonarr
Anime, Radarr, Bazarr, Prowlarr, SABnzbd, and Deluge behind an OpenVPN sidecar.

All workloads are pinned to `k8s-worker-2`. The existing LVM filesystem is
exposed by the static `jellyfin-media` local PV at
`/var/mnt/vault/media/downloadbox/data`. The PV uses the `Retain` reclaim
policy and is mounted read-write by the applications that manage media.

The namespace uses the privileged Pod Security level because Jellyfin mounts
`/dev/dri` for hardware transcoding and the VPN sidecar requires `NET_ADMIN`
and `/dev/net/tun`. Images are digest-pinned. Application configuration and the
Jellystat database use Longhorn PVCs; the large media library deliberately
uses the local PV instead.

## Service topology

Kubernetes service names provide the internal application addresses. Jellyfin
is `http://jellyfin:8096`, Jellystat is `http://jellystat:3000`, and the Deluge
API used by Sonarr and Radarr is `http://vpn:8112`. Deluge shares a pod with the
VPN client and has no external HTTPRoute.

Jellyfin, Jellyseerr, and Jellystat are published through Envoy Gateway.
Sonarr, Sonarr Anime, Radarr, Prowlarr, Bazarr, and SABnzbd are also published,
but their HTTPRoutes carry the `oidc: "true"` label. The cluster Kyverno policy
generates an Envoy Google OIDC `SecurityPolicy` and enforces the configured
email allowlist before forwarding requests to those administrative services.
Jellyfin, Jellyseerr and Jellystat use their own application-level
authentication.
