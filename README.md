# Homelab Kubernetes Cluster

Talos Linux cluster with GitOps managed by Argo CD.

## Stack

- Talos Linux 1.11.5
- Kubernetes v1.34.1
- Cilium CNI with LB-IPAM
- Argo CD for GitOps
- Envoy Gateway (Gateway API)
- external-dns (Cloudflare)

## Network

- Control Plane: 10.0.0.10
- Worker: 10.0.0.11
- LoadBalancer Pool: 10.0.1.0/24

## Structure

```
talos/          # Machine configs, secrets, patches
apps/           # Argo CD applications
  argocd/       # Argo CD self-management
  platform/     # Platform services (gateway, DNS)
  infrastructure/ # Infrastructure services
manifests/      # Direct Kubernetes manifests
```

## Quick Start

See [SETUP.md](SETUP.md) for installation details.

## Bootstrap

1. Install Argo CD:
```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

2. Deploy this repo's applications:
```bash
kubectl apply -f apps/argocd/application.yaml
kubectl apply -f apps/root-app.yaml
```

3. Access UI (admin password):
```bash
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

## Security

Never commit these files:
- `kubeconfig` - Cluster credentials
- `talos/secrets.yml` - Talos secrets
- `talos/talosconfig` - Talos configuration

Create secrets manually:
```bash
kubectl create secret generic cloudflare-api-token \
  -n external-dns \
  --from-literal=token=YOUR_TOKEN
```
