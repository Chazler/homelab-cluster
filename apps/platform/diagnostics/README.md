# Cluster diagnostics

The platform ApplicationSet manages the `diagnostics` namespace and the
`codex-diagnostics` service account. Its cluster role reads workload status,
pod logs, events, resource metrics, storage status, Longhorn resources, Argo CD
applications, and Gateway API routes. Metrics require a functioning metrics API.

The account cannot read Secrets or ConfigMaps, change workloads, request tokens,
impersonate users, proxy nodes, or execute commands by default. Logs and workload
specifications can still contain sensitive information; protect its credentials.
No permanent token Secret is created, and automatic token mounting is disabled.

## Access from a persistent workspace

After Argo CD has synced the chart, run this from a trusted machine with an
administrator kubeconfig and `kubectl` in PATH:

```sh
mkdir -p ~/.kube
python3 apps/platform/diagnostics/scripts/create-kubeconfig.py ~/.kube/homelab-diagnostics.json
KUBECONFIG=~/.kube/homelab-diagnostics.json kubectl get pods -A
```

The file is created with mode 0600 and contains only the diagnostic identity,
server address, and public cluster CA. The script refuses to overwrite an
existing file. Kubernetes grants the token lifetime; `--duration` requests 8h by
default. For renewal, remove the expired diagnostic file and run the script
again with administrator credentials. The diagnostic account cannot renew
itself. Keep this file outside Git. Persistent workspace storage survives
ordinary sessions but does not guarantee survival of workspace replacement.

Delete/recreate the service account to revoke all its tokens, or remove its
bindings to revoke permissions. Desired configuration changes go through GitHub.

## Optional exec access

`execNamespaces` is empty by default. Set an explicit namespace list in Git
only when deeper diagnostics need commands inside containers. Each namespace
must already exist and be allowed in the platform Argo CD project's destinations.
This grants `create` on `pods/exec` to every pod in those namespaces, including
access to mounted data and workload credentials; Kubernetes RBAC cannot restrict
exec to particular commands. Do not enable it for privileged storage/system pods.
