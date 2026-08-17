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

OpenClaw (https://docs.openclaw.ai) needs, in Vault at `services/openclaw-env`:

- One model provider API key: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `OPENAI_API_KEY` or `OPENROUTER_API_KEY`.
- `OPENCLAW_GATEWAY_TOKEN`, a random token the Control UI uses to
  authenticate (generate with `openssl rand -hex 32`).

Vault Secrets Operator syncs both into the `openclaw-env` secret consumed
via `envFrom`; the Deployment won't come up healthy without them. An
init container seeds `openclaw.json`/`AGENTS.md` from the
`openclaw-config` ConfigMap into the PVC on first boot only — after that
the PVC copy is authoritative, so config edits made through OpenClaw
(onboard, `doctor --fix`, Control UI) survive restarts, and ConfigMap
changes need a manual reseed to take effect.

AdGuard DNS is advertised on `10.0.0.243` over TCP and UDP port 53. Configure
the router or individual clients to use that address only after the
LoadBalancer service and AdGuard health have been verified.
