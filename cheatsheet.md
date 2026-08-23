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
VAULT_CACERT=/vault/userconfig/vault-server-tls/ca.crt
kubectl exec -n vault vault-0 -- sh -c "VAULT_CACERT=$VAULT_CACERT vault status"
kubectl exec -n vault vault-1 -- sh -c "VAULT_CACERT=$VAULT_CACERT vault status"
kubectl exec -n vault vault-2 -- sh -c "VAULT_CACERT=$VAULT_CACERT vault status"

# Vault auto-unseals via GCP KMS; no manual unseal is needed. Restart one
# pod at a time (standbys first, active last) since the StatefulSet uses
# OnDelete. See SETUP.md "Vault TLS and recovery" for the full procedure.
kubectl delete pod vault-2 -n vault
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

## Create a sealed secret

Keep `secret.yaml` local; it is ignored by Git.

```bash
kubeseal \
  --controller-namespace sealed-secrets \
  --controller-name sealed-secrets \
  --format yaml \
  < secret.yaml > sealed-secret.yaml
```
