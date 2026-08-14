# Home Assistant migration

This chart restores Home Assistant 2026.8.1 from the downloadbox backup dated
2026-08-13. It is pinned to `k8s-worker-2` and uses host networking so local
discovery protocols and HomeKit retain their former network behavior.

The application waits for `/config/.restore-complete`, then validates the
restored YAML before starting. Keep the HTTPRoute disabled until the database,
integrations, and local port 8123 have been checked. Remove transient lock,
log, PID, macOS metadata, and already-corrupt database files during restore.

The Envoy pod subnet `10.244.0.0/16` must be included in Home Assistant's
`http.trusted_proxies` before enabling the route.
