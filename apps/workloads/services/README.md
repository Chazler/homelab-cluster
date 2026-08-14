# Services

This chart runs AdGuard Home, Umami, Polylearn, Idea Triage and n8n.

Umami and Idea Triage share one PostgreSQL 16 StatefulSet and Longhorn volume,
but use separate roles and databases. Application credentials and the private
GHCR pull credential are committed only as SealedSecrets.

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

For a new installation, create the referenced secrets with environment-specific
values and seal them for the `services` namespace. The PostgreSQL initialization
script creates isolated `umami` and `idea_triage` databases on an empty volume.

## PostgreSQL backup and restore

The two applications share a PostgreSQL server and volume, but each has its own
database and login role. Back up and restore one logical database at a time;
use the corresponding role and do not include credentials on the command line.

```bash
# Back up (the archive is written to the PostgreSQL pod).
kubectl exec -n services postgres-0 -- \
  pg_dump -U umami -Fc -f /tmp/umami.dump umami
kubectl cp services/postgres-0:/tmp/umami.dump ./umami.dump

# Restore into an existing, empty target database after copying the archive in.
kubectl cp ./umami.dump services/postgres-0:/tmp/umami.dump
kubectl exec -n services postgres-0 -- \
  pg_restore -U postgres -d umami --clean --if-exists /tmp/umami.dump
```

Replace `umami` with `idea_triage` for the other logical database. Take a
Longhorn volume backup as well when a point-in-time backup of the entire shared
server is required.
