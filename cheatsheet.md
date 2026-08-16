# Operations Cheatsheet

## Cluster health

```bash
talosctl -n 10.0.0.10,10.0.0.20 health
kubectl get nodes
kubectl get pods -A
kubectl get applications -n argocd
cilium status
```

## Vault

```bash
kubectl get pods -n vault
kubectl exec -n vault vault-0 -- vault status
kubectl exec -n vault vault-1 -- vault status

# Interactive: do not put the unseal key in shell history.
kubectl exec -it -n vault vault-0 -- vault operator unseal
kubectl exec -it -n vault vault-1 -- vault operator unseal
```

## Certificates and routes

```bash
kubectl get gateway,httproute -A
kubectl get certificate,certificaterequest,order,challenge -A
kubectl describe challenge -n envoy-gateway <challenge-name>
```

## Cilium

```bash
cilium status
kubectl -n kube-system exec ds/cilium -c cilium-agent -- cilium-dbg status --verbose
kubectl get ciliumloadbalancerippool,ciliuml2announcementpolicy
```

## Longhorn

```bash
kubectl -n longhorn get volumes.longhorn.io
kubectl -n longhorn get replicas.longhorn.io
kubectl get pv,pvc -A
```

## PostgreSQL logical database backup and restore

Back up and restore `umami` and `idea_triage` independently. Substitute the
other database name where appropriate.

```bash
kubectl exec -n services postgres-0 -- \
  pg_dump -U umami -Fc -f /tmp/umami.dump umami
kubectl cp services/postgres-0:/tmp/umami.dump ./umami.dump

kubectl cp ./umami.dump services/postgres-0:/tmp/umami.dump
kubectl exec -n services postgres-0 -- \
  pg_restore -U postgres -d umami --clean --if-exists /tmp/umami.dump
```

## Create a sealed secret

Keep `secret.yaml` local; it is ignored by Git.

```bash
kubeseal \
  --controller-namespace sealed-secrets \
  --controller-name sealed-secrets \
  --format yaml \
  < secret.yaml > sealed-secret.yaml
```
