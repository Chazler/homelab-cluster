# Talos Cluster Setup Guide

This document tracks the commands and steps taken to set up a 2-node Talos Kubernetes cluster with Cilium CNI and modern tooling.

## Environment

- **Network**: 10.0.0.0/24 VLAN (isolated)
- **Gateway**: 10.0.0.1
- **Control Plane**: 10.0.0.10 (talos-r7i-mbe)
- **Worker**: 10.0.0.11 (talos-twk-hmz)
- **Talos Version**: 1.11.5
- **Kubernetes Version**: 1.34.1

## Prerequisites

- Talos ISO flashed to USB drive
- Static IPs configured in router DHCP/VLAN settings
- Both nodes booted from USB in maintenance mode

## Step 1: Generate Talos Configuration

```bash
# Generate secrets and configs
talosctl gen config cluster https://10.0.0.10:6443 \
  --output-dir talos/ \
  --with-secrets talos/secrets.yml

# This creates:
# - talos/controlplane.yaml
# - talos/worker.yaml
# - talos/talosconfig
# - talos/secrets.yml
```

## Step 2: Apply Configurations

```bash
# Apply control plane config (node booted from USB, in maintenance mode)
talosctl apply-config --insecure \
  --nodes 10.0.0.10 \
  --file talos/controlplane.yaml

# Wait for control plane to install to /dev/sda and reboot
# Remove USB drive after installation, let node boot from disk

# Apply worker config (node booted from USB, in maintenance mode)
talosctl apply-config --insecure \
  --nodes 10.0.0.11 \
  --file talos/worker.yaml

# Wait for worker to install to /dev/sda and reboot
# Remove USB drive after installation
```

## Step 3: Configure Talosctl Context

```bash
# Merge talosconfig into default config
talosctl config merge talos/talosconfig

# Verify context
talosctl config contexts
talosctl -n 10.0.0.10 version
```

## Step 4: Bootstrap Cluster

```bash
# Bootstrap etcd on control plane
talosctl bootstrap -n 10.0.0.10

# Wait for bootstrap to complete (~2-3 minutes)
talosctl -n 10.0.0.10 get members
```

## Step 5: Get Kubeconfig

```bash
# Fetch kubeconfig from control plane
talosctl kubeconfig -n 10.0.0.10 kubeconfig

# Set environment variable for kubectl
export KUBECONFIG=/Users/joeriberman/Git/talos-cluster/kubeconfig

# Verify nodes
kubectl get nodes
```

## Step 6: Switch to Cilium CNI

```bash
# Create patch directory
mkdir -p talos/patches

# Create cilium-cni.yaml patch:
cat > talos/patches/cilium-cni.yaml <<EOF
cluster:
  network:
    cni:
      name: none  # Disable built-in CNI (Flannel), Cilium will handle it
EOF

# Apply patch to both nodes
talosctl patch machineconfig -n 10.0.0.10 --patch @talos/patches/cilium-cni.yaml
talosctl patch machineconfig -n 10.0.0.11 --patch @talos/patches/cilium-cni.yaml
```

## Step 7: Install Cilium

```bash
# Install Cilium CLI
brew install cilium-cli

# Install Cilium with Talos-specific settings
cilium install \
    --set ipam.mode=kubernetes \
    --set kubeProxyReplacement=false \
    --set securityContext.capabilities.ciliumAgent="{CHOWN,KILL,NET_ADMIN,NET_RAW,IPC_LOCK,SYS_ADMIN,SYS_RESOURCE,DAC_OVERRIDE,FOWNER,SETGID,SETUID}" \
    --set securityContext.capabilities.cleanCiliumState="{NET_ADMIN,SYS_ADMIN,SYS_RESOURCE}" \
    --set cgroup.autoMount.enabled=false \
    --set cgroup.hostRoot=/sys/fs/cgroup

# Wait for Cilium to be ready
cilium status --wait

# Run connectivity test (optional)
cilium connectivity test
```

## Step 8: Configure Cilium LoadBalancer IP Pool

```bash
# Apply LoadBalancer IP pool and L2 announcement policy
kubectl apply -f manifests/cilium-lb-pool.yaml

# Verify IP pool
kubectl get ciliumloadbalancerippool -A
kubectl get ciliuml2announcementpolicy -A
```

## Step 9: Install Argo CD

```bash
# Create namespace and install Argo CD
kubectl create namespace argocd
kubectl apply -n argocd -f https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml

# Wait for pods to be ready
kubectl get pods -n argocd -w
```

## Next Steps

- [ ] Install Envoy Gateway
- [ ] Configure external-dns with Cloudflare
- [ ] Set up cert-manager for TLS certificates
- [ ] Deploy portfolio application
- [ ] Configure Cloudflare Tunnel (optional, for external access)
- [ ] Install observability stack (Prometheus, Grafana, Hubble UI)

## Useful Commands

```bash
# Check Talos node status
talosctl -n 10.0.0.10 dashboard
talosctl -n 10.0.0.10,10.0.0.11 health

# Check Kubernetes nodes
kubectl get nodes -o wide

# Check Cilium status
cilium status
cilium connectivity test

# View logs
talosctl -n 10.0.0.10 logs kubelet
talosctl -n 10.0.0.10 logs controller-runtime

# Access Argo CD (temporary)
kubectl port-forward svc/argocd-server -n argocd 8080:443
# Get initial admin password
kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath="{.data.password}" | base64 -d
```

## File Structure

```
talos-cluster/
├── talos/
│   ├── controlplane.yaml      # Control plane machine config
│   ├── worker.yaml             # Worker machine config
│   ├── talosconfig             # Talosctl client config
│   ├── secrets.yml             # Cluster secrets (keep safe!)
│   └── patches/
│       └── cilium-cni.yaml     # CNI patch
├── manifests/
│   └── cilium-lb-pool.yaml     # Cilium LoadBalancer IP pool
├── kubeconfig                  # Kubernetes admin config
└── SETUP.md                    # This file
```

## Troubleshooting

### Nodes stuck in NotReady
- Check Cilium status: `cilium status`
- Check pod networking: `kubectl get pods -A`
- Verify CNI patch applied: `talosctl -n 10.0.0.10 get machineconfig -o yaml | grep cni`

### Can't connect to nodes
- Verify talosconfig has correct endpoints: `cat ~/.talos/config`
- Check network connectivity: `ping 10.0.0.10`
- Use `--insecure` flag if certificates are mismatched (only in maintenance mode)

### LoadBalancer stuck in Pending
- Check Cilium LB-IPAM: `kubectl get ciliumloadbalancerippool -A`
- Verify L2 announcements: `kubectl get ciliuml2announcementpolicy -A`
- Check interface names match your nodes: `talosctl -n 10.0.0.10 get links`
