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
| OpenClaw | `openclaw.joeriberman.nl` | OpenClaw gateway token |

OpenClaw (https://docs.openclaw.ai) is the one service here **not**
behind Authentik forward-auth. It authenticates natively with
`gateway.auth.mode: "token"`, because the OpenClaw iOS app pairs by
scanning a setup code (`openclaw qr`) that embeds a bearer token — a
native client has no way to complete Authentik's browser SSO redirect,
and `trusted-proxy` mode is mutually exclusive with any shared token
(the gateway refuses to start with both). Delegating to Authentik and
supporting the mobile app are therefore incompatible; the gateway token
is the single authentication boundary for both browser and app.

Required secrets in Vault at `services/openclaw-env`:

- `OPENCLAW_GATEWAY_TOKEN` — the gateway credential. The pod will not
  start without it. Generate with `openssl rand -hex 32`.
- One model provider API key: `ANTHROPIC_API_KEY`, `GEMINI_API_KEY`,
  `OPENAI_API_KEY` or `OPENROUTER_API_KEY`.

Vault Secrets Operator syncs these into the `openclaw-env` secret; each
is wired in as an individual `secretKeyRef` (provider keys
`optional: true`) rather than via `envFrom`.

To reach the Control UI in a browser, paste the token into the
connection page:

    kubectl get secret openclaw-env -n services \
      -o jsonpath='{.data.OPENCLAW_GATEWAY_TOKEN}' | base64 -d && echo

Device pairing is enforced. A new browser raises a pairing request that
an operator approves from inside the pod, which works because the token
authenticates the CLI itself:

    kubectl exec -n services deploy/openclaw -c openclaw -- sh -c \
      'node /app/openclaw.mjs devices list --token "$OPENCLAW_GATEWAY_TOKEN"'
    kubectl exec -n services deploy/openclaw -c openclaw -- sh -c \
      'node /app/openclaw.mjs devices approve <requestId> --token "$OPENCLAW_GATEWAY_TOKEN"'

The iOS app self-enrols instead: `openclaw qr` mints a short-lived
bootstrap token, so it needs no manual approval.

`gateway.controlUi.dangerouslyDisableDeviceAuth` was previously set and
is now removed. It was only ever needed under `trusted-proxy`, where
approving the first device was impossible — approval requires the
`operator.pairing` scope on an already-paired connection, which cannot
exist on a fresh deploy. Token auth breaks that deadlock, so pairing is
enforced again. Note the pinned image (`2026.7.1`) also predates
`gateway.auth.identityScopes` and `trustedProxy.deviceAutoApprove`,
both of which the online docs describe; verify any new auth field
against the image before using it.

`agents.defaults.model`/`agents.list[0].model` are pinned to
`openrouter/auto` so the agent actually routes through OpenRouter (and
therefore `OPENROUTER_API_KEY`) — without an explicit model, OpenClaw
falls back to its own hardcoded default (`openai/gpt-5.5`), which
silently fails without an `OPENAI_API_KEY`. Change this if you add a
different provider key to `services/openclaw-env`.

`agents.defaults.models` is the picker allowlist — without it the
Control UI model switcher only ever showed `openrouter/auto`, since an
unset allowlist falls back to a tiny built-in catalog rather than every
model OpenRouter serves. It's set to six current OpenRouter model IDs
(one flagship per major lab plus `auto`), verified live against
`GET https://openrouter.ai/api/v1/models` and confirmed `available:
true` via `openclaw models list` against the pinned image — model
naming and availability drift over time, so re-check both before
editing this list.

An init container seeds `openclaw.json`/`AGENTS.md` from the
`openclaw-config` ConfigMap into the PVC on first boot only — after that
the PVC copy is authoritative, so config edits made through OpenClaw
(onboard, `doctor --fix`, Control UI) survive restarts and ConfigMap
changes need a manual reseed.

**Reseeding is not just `rm openclaw.json`.** OpenClaw keeps its own
restore chain (`openclaw.json.last-good`, `.bak*`) and treats a config
it did not write itself as an external overwrite: it quarantines the
incoming file as `openclaw.json.clobbered.<timestamp>` and silently
reverts to `.last-good`. Deleting only `openclaw.json` therefore
appears to work but the old config comes back on the next boot. Clear
the whole restore chain, then recreate the pod so the init container
reseeds:

    kubectl exec -n services deploy/openclaw -c openclaw -- sh -c \
      'rm -f /home/node/.openclaw/openclaw.json \
             /home/node/.openclaw/openclaw.json.bak* \
             /home/node/.openclaw/openclaw.json.last-good \
             /home/node/.openclaw/openclaw.json.clobbered.*'
    kubectl delete pod -n services -l app.kubernetes.io/name=openclaw

If the gateway is already crashlooping on bad config the exec window is
short; loop the command until it lands. Confirm the result with
`grep -A3 '"auth"' /home/node/.openclaw/openclaw.json` rather than
assuming the reseed took.

AdGuard DNS is advertised on `10.0.0.243` over TCP and UDP port 53. Configure
the router or individual clients to use that address only after the
LoadBalancer service and AdGuard health have been verified.
