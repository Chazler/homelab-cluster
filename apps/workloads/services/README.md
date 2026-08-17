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

OpenClaw (https://docs.openclaw.ai) needs one model provider API key in
Vault at `services/openclaw-env`: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
`OPENAI_API_KEY` or `OPENROUTER_API_KEY`. Vault Secrets Operator syncs it
into the `openclaw-env` secret and each key is wired in individually
(`optional: true`) rather than via `envFrom`, since `gateway.auth.mode`
is `trusted-proxy` and the gateway refuses to start if a
`OPENCLAW_GATEWAY_TOKEN` is present alongside it — trusted-proxy and
shared-token auth are mutually exclusive. The gateway instead trusts the
`x-authentik-email` header injected by the Authentik forward-auth
outpost (see `apps/platform/kyverno/templates/authentik-forward-auth.yaml`),
scoped to `gateway.trustedProxies: ["10.244.0.0/16"]` (the cluster pod
CIDR) so only in-cluster proxies can set it. The pinned image
(`2026.7.1`) predates `gateway.auth.identityScopes` — any request with a
verified trusted-proxy identity is granted the Control UI operator
role, so there's currently no per-user allowlist. Revisit once the
pinned digest is bumped past a release that ships identityScopes.

`gateway.controlUi.dangerouslyDisableDeviceAuth` is also set. Without
it, a brand-new browser session needs one-time device pairing approved
via a privileged, already-paired caller — a bootstrap that the
gateway's own WS RPC auth model has no way to satisfy for a trusted-proxy
connection with no prior paired device (approving requires the
`operator.pairing` scope on an *existing* paired connection, which
none exists yet for a fresh deploy). Since every connection is already
identity-verified by Authentik before Envoy ever forwards it to the
gateway (see `x-authentik-email` above), the extra per-device pairing
ceremony is redundant here; disabling it accepts that trade-off
explicitly rather than working around the bootstrap deadlock.

An init container seeds `openclaw.json`/`AGENTS.md` from the
`openclaw-config` ConfigMap into the PVC on first boot only — after that
the PVC copy is authoritative, so config edits made through OpenClaw
(onboard, `doctor --fix`, Control UI) survive restarts, and ConfigMap
changes need a manual reseed (`kubectl exec deploy/openclaw -n services
-- rm /home/node/.openclaw/openclaw.json && kubectl rollout restart
deployment/openclaw -n services`) to take effect.

AdGuard DNS is advertised on `10.0.0.243` over TCP and UDP port 53. Configure
the router or individual clients to use that address only after the
LoadBalancer service and AdGuard health have been verified.
