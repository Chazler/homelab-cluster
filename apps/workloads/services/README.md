# Services

This chart runs AdGuard Home, Umami, Polylearn, Idea Triage, n8n and OpenClaw.

Umami and Idea Triage share one PostgreSQL 16 StatefulSet and Longhorn volume,
but use separate roles and databases. Application credentials and the private
GHCR pull credentials and application runtime secrets are synchronized from
Vault by Vault Secrets Operator.

| Service | Endpoint | Access |
| --- | --- | --- |
| AdGuard Home | `adguard.joeriberman.nl` | Authentik forward-auth |
| Umami | `umami.joeriberman.nl` | Authentik forward-auth |
| Polylearn | `polylearn.joeriberman.nl` | Public |
| Idea Triage | `idea-triage.joeriberman.nl` | Authentik forward-auth |
| n8n | `n8n.joeriberman.nl` | Authentik forward-auth |
| OpenClaw | `openclaw.joeriberman.nl` | Authentik forward-auth |

OpenClaw (https://docs.openclaw.ai) needs a model provider API key. Write it
to Vault at `services/openclaw-env` as one of `ANTHROPIC_API_KEY`,
`GEMINI_API_KEY`, `OPENAI_API_KEY` or `OPENROUTER_API_KEY` before the
Deployment will come up healthy; Vault Secrets Operator syncs it into the
`openclaw-env` secret consumed via `envFrom`.

AdGuard DNS is advertised on `10.0.0.243` over TCP and UDP port 53. Configure
the router or individual clients to use that address only after the
LoadBalancer service and AdGuard health have been verified.
