# Home Assistant

This chart runs Home Assistant on `k8s-worker-2` with a Longhorn-backed
configuration volume. The pod uses host networking so discovery protocols,
HomeKit and integrations that expect the LAN can work without additional
multicast forwarding. Envoy Gateway publishes the service through a dedicated
HTTPRoute.

The Envoy pod subnet `10.244.0.0/16` is included in Home Assistant's trusted
proxies. In Home Assistant 2026.8 this setting is persisted in `.storage/http`
as well as `configuration.yaml`.
