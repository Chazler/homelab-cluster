# Homelab Kubernetes Cluster

Talos Linux cluster with GitOps managed by Argo CD.

## Stack

- **OS:** Talos Linux 1.11.5
- **Orchestration:** Kubernetes v1.34.1
- **Networking:** Cilium CNI with LB-IPAM
- **GitOps:** Argo CD
- **Ingress:** Envoy Gateway (Gateway API)
- **DNS:** external-dns (Cloudflare)
- **Storage:** Rancher Local Path Provisioner
- **Secrets:** Sealed Secrets
- **Monitoring:** kube-prometheus-stack (Prometheus, Grafana, Alertmanager)

## Network

- Control Plane: 10.0.0.10
- Worker: 10.0.0.11
- LoadBalancer Pool: 10.0.1.0/24

## Structure

```
talos/          # Machine configs, secrets, patches (NEVER commit configs!)
apps/           # Argo CD applications
  argocd/       # Argo CD self-management
  platform/     # Platform services (gateway, DNS)
  infrastructure/ # Infrastructure services (Cilium)
manifests/      # Direct Kubernetes manifests
```

## Security Notice

⚠️ **Sensitive files are excluded from Git:**
- `talos/secrets.yml` - Cluster secrets and certificates
- `talos/talosconfig` - Admin credentials
- `talos/controlplane.yaml` - Machine config with embedded secrets
- `talos/worker.yaml` - Machine config with embedded secrets
- `kubeconfig` - Kubernetes admin credentials

Use `talos/rotate-secrets.sh` to generate fresh configs.

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
