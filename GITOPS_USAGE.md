# GitOps Feature - Usage Guide

## Overview

The ArgoCD CLI now supports GitOps methodology by automatically saving Application and ApplicationSet manifests to a Git repository. This enables:

- **Version Control**: Track all changes to your ArgoCD resources
- **Audit Trail**: See who made what changes and when
- **Disaster Recovery**: Restore applications from Git
- **GitOps Workflow**: Manage infrastructure as code

## Quick Start

### 1. Set Up Git Credentials

```bash
# Set environment variables
export GIT_USERNAME="your-github-username"
export GIT_TOKEN="your-github-token"  # Personal Access Token with repo permissions
```

### 2. Create Application with GitOps

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace my-app \
  --gitops-repo https://github.com/myorg/argocd-manifests \
  --gitops-branch main \
  --gitops-path applications
```

### 3. Save Manifest Locally (No Git)

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace my-app \
  --save-manifest
```

This saves the manifest to `./argocd-manifests/my-app.yaml`

## GitOps Options

### For Applications

| Option | Description | Default |
|--------|-------------|---------|
| `--gitops-repo` | Git repository URL for storing manifests | None |
| `--gitops-branch` | Git branch to commit to | `main` |
| `--gitops-path` | Path within repo for manifests | `argocd-manifests` |
| `--save-manifest` | Save manifest locally | `false` |
| `--git-username` | Git username (or use GIT_USERNAME env var) | None |
| `--git-token` | Git token (or use GIT_TOKEN env var) | None |

### For ApplicationSets

Same options as Applications, plus:
- Manifest will be saved as `{appset-name}.yaml`
- Includes all generator configurations

## Complete Examples

### Example 1: Application with GitOps

```bash
# Create application and save to Git
argocd-cli workflows submit app \
  --app-name production-api \
  --repo-url https://github.com/myorg/helm-charts \
  --chart-path charts/api \
  --values-file values-prod.yaml \
  --destination-namespace production \
  --sync-policy auto-heal \
  --gitops-repo https://github.com/myorg/argocd-config \
  --gitops-branch main \
  --gitops-path apps/production \
  --git-username $GIT_USERNAME \
  --git-token $GIT_TOKEN
```

**Result:**
- Workflow creates the Application in ArgoCD
- Manifest is committed to: `https://github.com/myorg/argocd-config/apps/production/production-api.yaml`
- Git commit message: "Add ArgoCD Application: production-api"

### Example 2: ApplicationSet with GitOps

```bash
# Create environments.json
cat > environments.json <<EOF
[
  {"name":"dev","cluster":"https://kubernetes.default.svc","namespace":"dev"},
  {"name":"staging","cluster":"https://kubernetes.default.svc","namespace":"staging"},
  {"name":"prod","cluster":"https://prod.k8s.example.com","namespace":"prod"}
]
EOF

# Submit ApplicationSet with GitOps
argocd-cli workflows submit appset \
  --appset-name multi-env-app \
  --repo-url https://github.com/myorg/helm-charts \
  --chart-path charts/app \
  --environments @environments.json \
  --sync-policy auto \
  --gitops-repo https://github.com/myorg/argocd-config \
  --gitops-path applicationsets
```

### Example 3: Local Save Only

```bash
# Save manifest locally without Git
argocd-cli workflows submit app \
  --app-name test-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --save-manifest

# Manifest saved to: ./argocd-manifests/test-app.yaml
# You can manually commit this to Git later
```

### Example 4: Both Git and Local

```bash
# Save to both Git and local filesystem
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --gitops-repo https://github.com/myorg/argocd-config \
  --save-manifest
```

## Git Repository Structure

Your GitOps repository will be organized like this:

```
argocd-manifests/
├── applications/
│   ├── production-api.yaml
│   ├── staging-api.yaml
│   └── dev-api.yaml
├── applicationsets/
│   ├── multi-env-app.yaml
│   └── microservices.yaml
└── README.md
```

## Setting Up Your GitOps Repository

### 1. Create a New Repository

```bash
# On GitHub, create a new repository: argocd-config
# Then clone it locally
git clone https://github.com/myorg/argocd-config
cd argocd-config

# Create directory structure
mkdir -p argocd-manifests/applications
mkdir -p argocd-manifests/applicationsets

# Add README
cat > README.md <<EOF
# ArgoCD Configuration Repository

This repository contains ArgoCD Application and ApplicationSet manifests
managed by the ArgoCD CLI tool.

## Structure

- \`argocd-manifests/applications/\` - Individual Application manifests
- \`argocd-manifests/applicationsets/\` - ApplicationSet manifests

## Usage

These manifests are automatically generated and committed by the ArgoCD CLI.
To apply them manually:

\`\`\`bash
kubectl apply -f argocd-manifests/applications/
kubectl apply -f argocd-manifests/applicationsets/
\`\`\`
EOF

git add .
git commit -m "Initial commit"
git push origin main
```

### 2. Generate GitHub Personal Access Token

1. Go to GitHub Settings → Developer settings → Personal access tokens
2. Click "Generate new token (classic)"
3. Give it a name: "ArgoCD CLI"
4. Select scopes: `repo` (Full control of private repositories)
5. Click "Generate token"
6. Copy the token and save it securely

```bash
# Set as environment variable
export GIT_TOKEN="ghp_xxxxxxxxxxxxxxxxxxxx"
export GIT_USERNAME="your-username"
```

### 3. Configure ArgoCD to Watch the Repository

```bash
# Add the GitOps repo to ArgoCD
argocd repo add https://github.com/myorg/argocd-config \
  --username $GIT_USERNAME \
  --password $GIT_TOKEN

# Create an Application that watches the manifests directory
kubectl apply -f - <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: argocd-apps
  namespace: argocd
spec:
  project: default
  source:
    repoURL: https://github.com/myorg/argocd-config
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

Now ArgoCD will automatically sync any Applications you commit to the Git repository!

## Workflow

1. **Developer runs CLI command** with `--gitops-repo` option
2. **Workflow creates Application** in ArgoCD cluster
3. **CLI generates manifest** from the Application spec
4. **CLI commits manifest** to Git repository
5. **ArgoCD watches Git repo** and keeps Applications in sync
6. **Changes to Git** automatically update Applications

## Benefits

✅ **Single Source of Truth**: Git is the source of truth for all ArgoCD resources  
✅ **Audit Trail**: Every change is tracked in Git history  
✅ **Rollback**: Easy to revert to previous versions  
✅ **Collaboration**: Team members can review changes via Pull Requests  
✅ **Disaster Recovery**: Restore entire ArgoCD configuration from Git  
✅ **GitOps Compliance**: Follows GitOps best practices  

## Troubleshooting

### Authentication Failed

```bash
# Verify credentials
echo $GIT_USERNAME
echo $GIT_TOKEN | cut -c1-10  # Show first 10 chars

# Test Git access
git clone https://$GIT_USERNAME:$GIT_TOKEN@github.com/myorg/argocd-config
```

### Manifest Not Committed

Check the CLI output for error messages. Common issues:
- Invalid Git credentials
- Repository doesn't exist
- Branch doesn't exist (will be created automatically)
- Network connectivity issues

### Local Manifest Location

By default, manifests are saved to `./argocd-manifests/` in your current directory.
You can change this by modifying the `local_path` in the code.

## Advanced Usage

### Custom Commit Messages

The CLI automatically generates commit messages like:
- "Add ArgoCD Application: my-app"
- "Add ArgoCD ApplicationSet: multi-env"

### Pull Request Workflow

To create a PR instead of direct commit (future feature):
```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --gitops-repo https://github.com/myorg/argocd-config \
  --create-pr  # Future feature
```

## Next Steps

1. Set up your GitOps repository
2. Configure Git credentials
3. Start using `--gitops-repo` with your commands
4. Configure ArgoCD to watch your GitOps repository
5. Enjoy automated GitOps workflow!
