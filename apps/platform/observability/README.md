# Observability

This application deploys Prometheus, Grafana, Alertmanager, and a SMART
exporter in the `observability` namespace. It intentionally does not deploy
log aggregation. ntfy is deployed separately as a reusable platform service.

Prometheus data uses the `observability-rwo` Longhorn storage class, which has
one replica to avoid doubling metrics write amplification. Prometheus has a
25 GiB claim and a 20 GiB retention-size limit. Grafana is available through
Authentik at `grafana.joeriberman.nl`; Prometheus and Alertmanager remain
cluster-internal.

Runtime secrets are synchronized from Vault:

| Vault path | Required fields |
| --- | --- |
| `kv/observability/grafana` | `admin-user`, `admin-password` |
| `kv/observability/alertmanager` | `alertmanager-username`, `alertmanager-password`, `webhook-username`, `webhook-password` |

The Alertmanager user is configured by ntfy's standalone service. Its webhook
credentials protect the relay's cluster-internal HTTP endpoint.
