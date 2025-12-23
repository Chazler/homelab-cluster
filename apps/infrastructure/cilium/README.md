# Cilium CNI with Kube-Proxy Replacement

This directory contains the Helm chart configuration for Cilium CNI with kube-proxy replacement enabled, optimized for Talos Linux.

## Problem Statement

The cluster was experiencing connectivity issues where pods (including ArgoCD) could not reach the Kubernetes API server service IP (`10.96.0.1:443`). This was caused by:

1. Cilium installed with `kubeProxyReplacement=false`
2. kube-proxy running in nftables mode but failing to properly route service traffic
3. A known incompatibility between kube-proxy's nftables mode and Talos's firewall configuration

**Symptoms:**
- Pods crash with `dial tcp 10.96.0.1:443: i/o timeout`
- Direct connection to API server IP (`10.0.0.10:6443`) works
- Service IP (`10.96.0.1:443`) times out

## Solution

Enable Cilium's kube-proxy replacement, which provides:
- Full kube-proxy functionality natively in Cilium
- Better performance and reduced latency
- Native support for Talos Linux
- Proper service load balancing and connectivity

## Configuration

Key settings in [values.yaml](values.yaml):

```yaml
kubeProxyReplacement: true
k8sServiceHost: 10.0.0.10      # Direct API server connection
k8sServicePort: 6443
```

## Migration Steps

⚠️ **WARNING**: This is a disruptive change. Service connectivity will be briefly interrupted.

### Prerequisites

1. Backup current cluster state
2. Ensure you have console access to nodes
3. Have the Talos config and kubeconfig ready

### Step 1: Update Cilium via Helm (Manual - One Time)

Since ArgoCD is currently broken, we need to manually apply the Cilium upgrade first:

```bash
cd /Users/joeriberman/Git/homelab-cluster/apps/infrastructure/cilium

# Download dependencies
helm dependency update

# Upgrade Cilium with kube-proxy replacement
helm upgrade cilium . \
  --namespace kube-system \
  --reuse-values \
  -f values.yaml
```

### Step 2: Verify Cilium Status

```bash
# Check Cilium pods
kubectl get pods -n kube-system -l k8s-app=cilium

# Verify kube-proxy replacement is active
kubectl exec -n kube-system ds/cilium -- cilium status | grep KubeProxyReplacement
```

You should see: `KubeProxyReplacement: True`

### Step 3: Test Service Connectivity

```bash
# Test API server service IP from a pod
kubectl run test-api --image=curlimages/curl --rm -it --restart=Never -- \
  curl -k https://10.96.0.1:443/version --max-time 5
```

If this returns a response (even 401 Unauthorized), connectivity is working!

### Step 4: Disable kube-proxy in Talos

Once Cilium is handling service routing, disable kube-proxy:

```bash
# Apply the patch to both nodes
talosctl patch machineconfig -n 10.0.0.10 --patch @talos/patches/disable-kube-proxy.yaml
talosctl patch machineconfig -n 10.0.0.11 --patch @talos/patches/disable-kube-proxy.yaml
```

### Step 5: Verify and Clean Up

```bash
# Check that kube-proxy pods are gone
kubectl get pods -n kube-system -l k8s-app=kube-proxy

# Should return: No resources found

# Verify ArgoCD pods are now healthy
kubectl get pods -n argocd

# Delete old network policies (if they still exist)
kubectl delete networkpolicies -n argocd --all
```

### Step 6: Enable ArgoCD Management (GitOps)

Once everything is working, let ArgoCD manage Cilium going forward:

```bash
# Apply the Cilium ArgoCD Application
kubectl apply -f apps/infrastructure/cilium/application.yaml

# Sync the application
kubectl get application -n argocd cilium
```

## Post-Migration Verification

Run these checks to ensure everything is working:

```bash
# 1. Cilium connectivity test
cilium connectivity test

# 2. Check ArgoCD pods
kubectl get pods -n argocd

# 3. Verify service connectivity
kubectl run test-svc --image=busybox --rm -it --restart=Never -- \
  wget -O- --timeout=5 https://kubernetes.default.svc:443 2>&1

# 4. Check Cilium status
kubectl exec -n kube-system ds/cilium -- cilium status
```

## Configuration Details

### Talos-Specific Settings

```yaml
securityContext:
  capabilities:
    ciliumAgent: [CHOWN, KILL, NET_ADMIN, NET_RAW, IPC_LOCK, SYS_ADMIN, ...]
    
cgroup:
  autoMount:
    enabled: false
  hostRoot: /sys/fs/cgroup
```

### API Server Connection

```yaml
k8sServiceHost: 10.0.0.10  # Control plane node IP
k8sServicePort: 6443       # API server port
```

This allows Cilium to connect directly to the API server, bypassing the service IP during initialization.

## Rollback

If you need to rollback:

```bash
# 1. Re-enable kube-proxy in Talos
talosctl patch machineconfig -n 10.0.0.10 --patch '{"cluster":{"proxy":{"disabled":false}}}'
talosctl patch machineconfig -n 10.0.0.11 --patch '{"cluster":{"proxy":{"disabled":false}}}'

# 2. Disable Cilium kube-proxy replacement
helm upgrade cilium cilium/cilium \
  --namespace kube-system \
  --reuse-values \
  --set kubeProxyReplacement=false
```

## Troubleshooting

### Cilium pods not starting

Check Cilium agent logs:
```bash
kubectl logs -n kube-system ds/cilium -c cilium-agent
```

### Service connectivity still broken

Verify kube-proxy replacement is active:
```bash
kubectl exec -n kube-system ds/cilium -- cilium status | grep -A 10 KubeProxyReplacement
```

### ArgoCD still crashing

Check if network policies are blocking traffic:
```bash
kubectl get networkpolicies -n argocd
kubectl delete networkpolicies -n argocd --all  # Temporary fix
```

## References

- [Cilium Kube-Proxy Replacement](https://docs.cilium.io/en/stable/network/kubernetes/kubeproxy-free/)
- [Talos + Cilium Guide](https://www.talos.dev/latest/kubernetes-guides/network/deploying-cilium/)
- [Issue Tracking](https://github.com/cilium/cilium/issues?q=is%3Aissue+talos+kube-proxy)

## Version History

| Version | Date | Changes |
|---------|------|---------|
| 1.0.0 | 2025-12-22 | Initial chart with kube-proxy replacement enabled |
