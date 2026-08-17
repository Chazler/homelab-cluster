# ntfy

ntfy is the cluster's standalone notification service. Workloads publish to
`http://ntfy.ntfy.svc/<topic>` using an account scoped to the topic they need.
It is externally available at `ntfy.joeriberman.nl` for subscribed clients and
uses ntfy's native default-deny ACLs rather than interactive forward-auth.

The `kv/ntfy/runtime` Vault secret provides `auth-users` and `auth-access`.
Provision one non-admin account per publishing workload and grant it only
`write-only` access to its dedicated topic. Users who subscribe need a separate
read-only account or ACL entry.
