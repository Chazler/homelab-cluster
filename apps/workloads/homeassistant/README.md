# Home Assistant

This chart runs Home Assistant on `k8s-worker-2` with a Longhorn-backed
configuration volume. The pod uses host networking so discovery protocols,
HomeKit and integrations that expect the LAN can work without additional
multicast forwarding. Envoy Gateway publishes the service through a dedicated
HTTPRoute.

The Envoy pod subnet `10.244.0.0/16` must be included in Home Assistant's
trusted proxies. In Home Assistant 2026.8 this value can be persisted in
`.storage/http`, so verify the active HTTP server settings as well as
`configuration.yaml` when changing the proxy configuration.

To reproduce this deployment, change `nodeName`, the public hostname, storage
size and resource limits in `values.yaml`. Integration endpoints must be LAN
addresses or resolvable DNS names; Docker-only aliases are not available in
Kubernetes.
