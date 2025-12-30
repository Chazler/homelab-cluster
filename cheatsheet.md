### Create sealed secret
```bash
cat ./secret.yaml | kubeseal --controller-namespace sealed-secrets --controller-name sealed-secrets --format yaml > ./sealed-secret.yaml
```


kubectl describe order wildcard-tls-1-1065682888 -n envoy-gateway 2>/dev/null | tail -
40

kubectl describe certificaterequest wildcard-tls-1 -n envoy-gateway | tail -30

kubectl get application envoy-gateway -n argocd -o yaml | grep -A 5 "syncPolicy:
"