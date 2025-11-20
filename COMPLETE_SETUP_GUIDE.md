# Complete Setup Guide - ArgoCD CLI

## Overview

This guide walks you through setting up a complete GitOps workflow using the ArgoCD CLI tool, from installation to creating your first application.

## Architecture

```
┌──────────────────────────────────────────────────────────────┐
│                     Your Kubernetes Cluster                   │
│                                                               │
│  ┌─────────────┐      ┌──────────────┐      ┌────────────┐  │
│  │   ArgoCD    │◄─────│     Argo     │      │   Your     │  │
│  │  (Manages   │      │  Workflows   │      │   Apps     │  │
│  │   Apps)     │      │  (Creates    │      │            │  │
│  └──────┬──────┘      │   Apps)      │      └────────────┘  │
│         │             └──────────────┘                       │
│         │ Watches                                            │
│         ▼                                                    │
│  ┌─────────────────────────────────────────────────────┐    │
│  │          Git Repository (GitOps)                    │    │
│  │  - Application manifests                            │    │
│  │  - ApplicationSet manifests                         │    │
│  │  - Version controlled                               │    │
│  └─────────────────────────────────────────────────────┘    │
└──────────────────────────────────────────────────────────────┘
```

## Prerequisites

- Kubernetes cluster (v1.19+)
- kubectl configured
- Helm 3.x installed
- Python 3.8+
- Git account (GitHub, GitLab, etc.)

## Step-by-Step Setup

### Step 1: Install the ArgoCD CLI Tool

```bash
# Clone the repository
git clone https://github.com/yourusername/argo-automated-installer
cd argo-automated-installer

# Install dependencies
pip install -r requirements.txt

# Install the CLI
pip install -e .

# Verify installation
argocd-cli --version
```

### Step 2: Install ArgoCD

```bash
# Install ArgoCD in your cluster
argocd-cli argocd install

# Check installation status
argocd-cli argocd status

# Note the admin password from the output
```

**Output will show:**
```
Admin Credentials:
  Username: admin
  Password: <your-password>

UI Access: kubectl port-forward -n argocd svc/argocd-server 8080:443
```

### Step 3: Access ArgoCD UI (Optional)

```bash
# Port-forward to access UI
kubectl port-forward -n argocd svc/argocd-server 8080:443

# Open browser to https://localhost:8080
# Login with admin credentials
```

### Step 4: Install Argo Workflows

```bash
# Install Argo Workflows
argocd-cli workflows install

# Verify installation
kubectl get pods -n argo
```

### Step 5: Create Workflow Templates

```bash
# Create all workflow templates
argocd-cli workflows templates create

# List templates
argocd-cli workflows templates list
```

**Output:**
```
┌──────────────────────────────┬────────────────┬────────────┬──────────────────┐
│ Name                         │ Description    │ Parameters │ Created          │
├──────────────────────────────┼────────────────┼────────────┼──────────────────┤
│ create-argocd-application    │ No description │     10     │ 2025-11-18 17:06 │
│ create-argocd-applicationset │ No description │     8      │ 2025-11-18 17:06 │
│ provision-infrastructure     │ No description │     4      │ 2025-11-18 17:06 │
└──────────────────────────────┴────────────────┴────────────┴──────────────────┘
```

### Step 6: Set Up GitOps Repository (Optional but Recommended)

```bash
# Create a new repository on GitHub
# Example: https://github.com/yourusername/argocd-manifests

# Clone it locally
git clone https://github.com/yourusername/argocd-manifests
cd argocd-manifests

# Create directory structure
mkdir -p argocd-manifests/applications
mkdir -p argocd-manifests/applicationsets

# Add README
cat > README.md <<EOF
# ArgoCD Manifests

This repository contains ArgoCD Application and ApplicationSet manifests.
EOF

git add .
git commit -m "Initial commit"
git push origin main
```

### Step 7: Configure Git Credentials

```bash
# Generate GitHub Personal Access Token
# Go to: GitHub Settings → Developer settings → Personal access tokens
# Create token with 'repo' scope

# Set environment variables
export GIT_USERNAME="your-github-username"
export GIT_TOKEN="ghp_your_personal_access_token"

# Add to your shell profile for persistence
echo 'export GIT_USERNAME="your-github-username"' >> ~/.bashrc
echo 'export GIT_TOKEN="ghp_your_token"' >> ~/.bashrc
```

### Step 8: Create Your First Application

#### Option A: Without GitOps (Quick Test)

```bash
argocd-cli workflows submit app \
  --app-name my-first-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace my-first-app
```

#### Option B: With GitOps (Recommended)

```bash
argocd-cli workflows submit app \
  --app-name my-first-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace my-first-app \
  --gitops-repo https://github.com/yourusername/argocd-manifests \
  --gitops-branch main \
  --gitops-path applications
```

#### Option C: Save Locally First

```bash
argocd-cli workflows submit app \
  --app-name my-first-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace my-first-app \
  --save-manifest

# Manifest saved to: ./argocd-manifests/my-first-app.yaml
# Review it, then commit to Git manually
```

### Step 9: Monitor the Workflow

```bash
# List all workflows
argocd-cli workflows list

# Get detailed status
argocd-cli workflows status <workflow-name>

# Watch in real-time
argocd-cli workflows status <workflow-name> --watch

# View logs
argocd-cli workflows logs <workflow-name>
```

### Step 10: Verify Application Created

```bash
# Check ArgoCD Applications
kubectl get applications -n argocd

# Get application details
kubectl get application my-first-app -n argocd -o yaml

# Check if pods are running
kubectl get pods -n my-first-app
```

### Step 11: Configure ArgoCD to Watch Git Repository (GitOps)

If you're using GitOps, configure ArgoCD to automatically sync from your Git repository:

```bash
# Create an Application that watches your manifests directory
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argocd-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/yourusername/argocd-manifests
    targetRevision: HEAD
    path: argocd-manifests/applications
  destination:
    server: https://kubernetes.default.svc
    namespace: argocd
  syncPolicy:
    automated:
      prune: true
      selfHeal: true
EOF
```

Now any manifests you commit to Git will automatically be synced by ArgoCD!

## Complete Workflow Example

Here's a complete example creating a production application with GitOps:

```bash
# 1. Create production application with auto-sync and GitOps
argocd-cli workflows submit app \
  --app-name production-api \
  --repo-url https://github.com/myorg/helm-charts \
  --chart-path charts/api \
  --values-file values-prod.yaml \
  --destination-namespace production \
  --sync-policy auto-heal \
  --helm-parameters "replicas=3,image.tag=v2.0.0" \
  --gitops-repo https://github.com/myorg/argocd-manifests \
  --gitops-branch main \
  --gitops-path applications/production

# 2. Monitor workflow
argocd-cli workflows status <workflow-name> --watch

# 3. Verify in ArgoCD UI
kubectl port-forward -n argocd svc/argocd-server 8080:443
# Open https://localhost:8080

# 4. Check Git repository
# Your manifest is now in: applications/production/production-api.yaml

# 5. Verify application is running
kubectl get pods -n production
```

## Multi-Environment Setup

Create an ApplicationSet for multiple environments:

```bash
# 1. Create environments configuration
cat > environments.json <<EOF
[
  {
    "name": "dev",
    "cluster": "https://kubernetes.default.svc",
    "namespace": "dev"
  },
  {
    "name": "staging",
    "cluster": "https://kubernetes.default.svc",
    "namespace": "staging"
  },
  {
    "name": "prod",
    "cluster": "https://kubernetes.default.svc",
    "namespace": "prod"
  }
]
EOF

# 2. Submit ApplicationSet with GitOps
argocd-cli workflows submit appset \
  --appset-name multi-env-app \
  --repo-url https://github.com/myorg/helm-charts \
  --chart-path charts/app \
  --environments @environments.json \
  --sync-policy auto \
  --gitops-repo https://github.com/myorg/argocd-manifests \
  --gitops-path applicationsets

# 3. Monitor
argocd-cli workflows status <workflow-name> --watch

# 4. Verify all environments
kubectl get applications -n argocd
```

## Troubleshooting

### ArgoCD Not Installed

```bash
# Check status
argocd-cli argocd status

# Install if needed
argocd-cli argocd install
```

### Argo Workflows Not Running

```bash
# Check pods
kubectl get pods -n argo

# Reinstall if needed
argocd-cli workflows install
```

### Workflow Failed

```bash
# Check status
argocd-cli workflows status <workflow-name>

# View logs
argocd-cli workflows logs <workflow-name>

# Delete and retry
argocd-cli workflows delete <workflow-name> --yes
```

### GitOps Not Working

```bash
# Verify credentials
echo $GIT_USERNAME
echo $GIT_TOKEN | cut -c1-10

# Test Git access
git ls-remote https://$GIT_USERNAME:$GIT_TOKEN@github.com/yourusername/argocd-manifests
```

### Application Not Syncing

```bash
# Check ArgoCD Application
kubectl get application <app-name> -n argocd -o yaml

# Check ArgoCD logs
kubectl logs -n argocd -l app.kubernetes.io/name=argocd-server

# Manually sync
kubectl patch application <app-name> -n argocd --type merge -p '{"operation":{"initiatedBy":{"username":"admin"},"sync":{"revision":"HEAD"}}}'
```

## Best Practices

### 1. Use GitOps

Always use `--gitops-repo` to store manifests in Git:
- Version control
- Audit trail
- Disaster recovery
- Team collaboration

### 2. Organize Your Repository

```
argocd-manifests/
├── applications/
│   ├── dev/
│   ├── staging/
│   └── production/
├── applicationsets/
└── README.md
```

### 3. Use Environment-Specific Values

```bash
# Different values per environment
argocd-cli workflows submit app \
  --app-name api \
  --values-file values-${ENV}.yaml \
  --destination-namespace ${ENV}
```

### 4. Enable Auto-Sync for Production

```bash
# Production with auto-heal
argocd-cli workflows submit app \
  --app-name prod-app \
  --sync-policy auto-heal
```

### 5. Monitor Workflows

```bash
# Always check workflow status
argocd-cli workflows list
argocd-cli workflows status <workflow-name>
```

## Next Steps

1. ✅ Set up your GitOps repository
2. ✅ Configure Git credentials
3. ✅ Create your first application
4. ✅ Configure ArgoCD to watch Git
5. ✅ Set up multi-environment deployments
6. ✅ Implement CI/CD pipeline integration

## Additional Resources

- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [GitOps Usage Guide](GITOPS_USAGE.md)
- [README](README.md)

## Support

For issues or questions:
1. Check the troubleshooting section
2. Review the logs: `argocd-cli workflows logs <workflow-name>`
3. Check ArgoCD UI for application status
4. Review Git repository for manifest issues

---

**Congratulations!** You now have a complete GitOps workflow set up with ArgoCD and Argo Workflows! 🎉
