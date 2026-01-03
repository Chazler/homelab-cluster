### Create sealed secret
```bash
cat ./secret.yaml | kubeseal --controller-namespace sealed-secrets --controller-name sealed-secrets --format yaml > ./sealed-secret.yaml
```


kubectl describe order wildcard-tls-1-1065682888 -n envoy-gateway 2>/dev/null | tail -
40

kubectl describe certificaterequest wildcard-tls-1 -n envoy-gateway | tail -30

kubectl get application envoy-gateway -n argocd -o yaml | grep -A 5 "syncPolicy:"


kubectl -n kube-system exec ds/cilium -- cilium-dbg config --all | grep EnableL2Announcements
kubectl -n kube-system exec ds/cilium -- cilium-dbg config --all | grep KubeProxyReplacement
kubectl -n kube-system exec ds/cilium -- cilium-dbg config --all | grep EnableExternalIPs


talosctl upgrade --nodes 10.0.0.10 \
  --image factory.talos.dev/metal-installer/