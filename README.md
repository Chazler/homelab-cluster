# Talos Kubernetes Cluster

Home lab Kubernetes cluster running on Talos Linux with GitOps (Argo CD).

## Stack

- **OS**: Talos Linux 1.11.5
- **Kubernetes**: v1.34.1
- **CNI**: Cilium (with LB-IPAM)
- **GitOps**: Argo CD
- **Gateway**: Envoy Gateway (Gateway API)
- **DNS**: external-dns (Cloudflare)

## Network

- **VLAN**: 10.0.0.0/24 (isolated)
- **Gateway**: 10.0.0.1
- **Control Plane**: 10.0.0.10 (talos-r7i-mbe)
- **Worker**: 10.0.0.11 (talos-twk-hmz)
- **LoadBalancer IPs**: 10.0.1.0/24 (managed by Cilium)

## Directory Structure

```
.
├── talos/                    # Talos machine configs
│   ├── controlplane.yaml
│   ├── worker.yaml
│   ├── talosconfig
│   ├── secrets.yml
│   └── patches/
│       └── cilium-cni.yaml
├── apps/                     # Application manifests
│   ├── platform/            # Platform services (ingress, DNS, certs)
│   │   ├── envoy-gateway/
│   │   └── external-dns/
│   └── infrastructure/      # Core infrastructure (monitoring, logging)
├── manifests/               # Raw Kubernetes manifests
│   └── cilium-lb-pool.yaml
├── kubeconfig              # Kubernetes admin config
├── SETUP.md                # Setup instructions
└── README.md               # This file
```

## Getting Started

See [SETUP.md](SETUP.md) for detailed installation instructions.

## Bootstrap Workflow

### 1. Initial Argo CD Installation (manual)

```bash
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml
```

### 2. Push this repo to GitHub

```bash
git init
git add .
git commit -m "Initial cluster configuration"
git remote add origin https://github.com/YOUR_USERNAME/talos-cluster.git
git push -u origin main
```

### 3. Configure Argo CD to manage itself

Update [apps/root-app.yaml](apps/root-app.yaml) with your GitHub repo URL, then:

```bash
# Make Argo CD manage itself (Helm-based)
kubectl apply -f apps/argocd/application.yaml

# Deploy root app (App of Apps pattern)
kubectl apply -f apps/root-app.yaml
```

Now all applications in `apps/platform/` will be automatically deployed!

### Access Argo CD UI

```bash
# Get LoadBalancer IP
kubectl get svc argocd-server -n argocd

# Or port forward
kubectl port-forward svc/argocd-server -n argocd 8080:80

# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

Then open: http://10.0.1.X (LoadBalancer IP) or http://localhost:8080

## Secrets Management

For sensitive values (Cloudflare API tokens, etc.), create secrets manually:

```bash
# Example: Cloudflare API token for external-dns
kubectl create secret generic cloudflare-api-token \
  -n external-dns \
  --from-literal=token=YOUR_TOKEN_HERE
```

## Useful Commands

```bash
# Set kubeconfig
export KUBECONFIG=/Users/joeriberman/Git/talos-cluster/kubeconfig

# Check cluster status
kubectl get nodes
cilium status

# Check Argo CD applications
kubectl get applications -n argocd

# Check LoadBalancer IPs
kubectl get svc -A | grep LoadBalancer
```
