# Media stack migration

This chart restores the Jellyfin media stack from the downloadbox backup dated
2026-08-13. It deploys Jellyfin, Jellyseerr, Jellystat/PostgreSQL, Sonarr,
Sonarr Anime, Radarr, Bazarr, Prowlarr, SABnzbd, and Deluge behind its VPN
sidecar. Home Assistant is intentionally outside this migration.

All workloads are pinned to `k8s-worker-2`. The existing LVM filesystem is
exposed by the static `jellyfin-media` local PV at
`/var/mnt/vault/media/downloadbox/data`. During recovery, both Talos and the
pods mount this data read-only.

The namespace uses the privileged Pod Security level because Jellyfin mounts
`/dev/dri` for hardware transcoding and the VPN sidecar requires `NET_ADMIN`
and `/dev/net/tun`. Images are digest-pinned and only Jellyfin is public.

## Recovery sequence

1. Sync the chart. Application containers wait for `.restore-complete` files,
   while `jellyfin-restore-helper` mounts every configuration PVC.
2. Restore the contents of each archived application directory into its PVC,
   excluding transient PID files, Jellyfin transcodes, and macOS `._*` or
   `.DS_Store` metadata.
3. Restore the Jellystat PostgreSQL dump and verify its row counts.
4. Write a `.restore-complete` marker to each checked configuration PVC.
5. Verify Jellyfin users, watch/resume state, libraries, and readable media;
   then verify all supporting service health endpoints.
6. Remount the Talos LVM volume read-write and set `media.readOnly: false` only
   after validation. This enables downloads, imports, renames, and subtitles.
7. Disable `restoreHelper` after the migration is complete.

## Post-restore service addresses

Backup configuration still contains addresses from the former Docker host. Set
Jellystat's `JF_HOST` to `http://jellyfin:8096`, Jellyseerr's Jellyfin host to
`jellyfin:8096`, and the Deluge host in Sonarr, Sonarr Anime, and Radarr to
`vpn:8112`. Their other credentials and settings remain unchanged.

Jellyfin, Jellyseerr, and Jellystat are published through Envoy Gateway as they
were on the old server. Administrative services stay cluster-internal until
equivalent authentication is configured.

The PV uses the `Retain` policy. Never delete or reformat the underlying LVM
volume as part of Kubernetes cleanup.
