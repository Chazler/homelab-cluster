# Services

This chart runs AdGuard Home, Umami, Polylearn, Idea Triage and n8n.

Umami and Idea Triage share one PostgreSQL 16 StatefulSet and Longhorn volume,
but use separate roles and databases. Application credentials and the private
GHCR pull credentials and application runtime secrets are synchronized from
Vault by Vault Secrets Operator.

| Service | Endpoint | Access |
| --- | --- | --- |
| AdGuard Home | `adguard.joeriberman.nl` | Google OIDC |
| Umami | `umami.joeriberman.nl` | Google OIDC |
| Polylearn | `polylearn.joeriberman.nl` | Public |
| Idea Triage | `idea-triage.joeriberman.nl` | Google OIDC |
| n8n | `n8n.joeriberman.nl` | Google OIDC |

AdGuard DNS is advertised on `10.0.0.243` over TCP and UDP port 53. Configure
the router or individual clients to use that address only after the
LoadBalancer service and AdGuard health have been verified.
