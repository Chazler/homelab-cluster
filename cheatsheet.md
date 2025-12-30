### Create sealed secret
```bash
cat ./secret.yaml | kubeseal --controller-namespace sealed-secrets --controller-name sealed-secrets --format yaml > ./sealed-secret.yaml
```
