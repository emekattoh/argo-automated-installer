# Test From Scratch - Complete Walkthrough

## ✅ Cleanup Complete

All resources have been deleted:
- ✓ Argo Workflows uninstalled
- ✓ ArgoCD uninstalled
- ✓ All CRDs removed
- ✓ All namespaces deleted
- ✓ RBAC resources cleaned
- ✓ Local manifests removed

## Fresh Start Testing

Follow these steps to test everything from scratch:

### Step 1: Verify Clean State

```bash
# Check no ArgoCD
kubectl get ns argocd
# Should show: Error from server (NotFound)

# Check no Argo Workflows
kubectl get ns argo
# Should show: Error from server (NotFound)

# Verify CLI is installed
argocd-cli --version
# Should show: argocd-cli, version 1.0.0
```

### Step 2: Install ArgoCD

```bash
# Install ArgoCD
argocd-cli argocd install

# Expected output:
# ✓ Success!
# Admin Credentials:
#   Username: admin
#   Password: <generated-password>
# UI Access: kubectl port-forward -n argocd svc/argocd-server 8080:443
```

**Verify:**
```bash
# Check ArgoCD status
argocd-cli argocd status

# Check pods are running
kubectl get pods -n argocd

# All pods should be Running
```

### Step 3: Install Argo Workflows

```bash
# Install Argo Workflows
argocd-cli workflows install

# Expected output:
# ✓ Success!
# Argo Workflows installed successfully in namespace 'argo'
# RBAC configured: ServiceAccount 'argo-workflow-sa', ClusterRole 'argo-workflow-role'
```

**Verify:**
```bash
# Check pods
kubectl get pods -n argo

# Should see:
# - argo-workflows-server (Running)
# - argo-workflows-workflow-controller (Running)
```

### Step 4: Create Workflow Templates

```bash
# Create all templates
argocd-cli workflows templates create

# Expected output:
# ✓ Successfully created 3 template(s)
# Created Templates:
#   • create-argocd-application
#   • create-argocd-applicationset
#   • provision-infrastructure
```

**Verify:**
```bash
# List templates
argocd-cli workflows templates list

# Should show 3 templates with parameters
```

### Step 5: Test Application Creation (No GitOps)

```bash
# Create a simple application
argocd-cli workflows submit app \
  --app-name test-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace test-app

# Note the workflow name from output
```

**Monitor:**
```bash
# List workflows
argocd-cli workflows list

# Check status
argocd-cli workflows status <workflow-name>

# Watch in real-time
argocd-cli workflows status <workflow-name> --watch

# View logs
argocd-cli workflows logs <workflow-name>
```

**Verify:**
```bash
# Check application created
kubectl get application test-app -n argocd

# Check namespace created
kubectl get ns test-app

# Should see application and namespace
```

### Step 6: Test GitOps - Local Save

```bash
# Create application with local manifest save
argocd-cli workflows submit app \
  --app-name gitops-local-test \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace gitops-local \
  --save-manifest

# Expected output:
# ✓ Manifest saved to ./argocd-manifests/gitops-local-test.yaml
```

**Verify:**
```bash
# Check manifest file exists
ls -la argocd-manifests/

# View manifest content
cat argocd-manifests/gitops-local-test.yaml

# Should see valid ArgoCD Application YAML
```

### Step 7: Test GitOps - Git Repository (Optional)

**Prerequisites:**
```bash
# Set up Git credentials
export GIT_USERNAME="your-github-username"
export GIT_TOKEN="ghp_your_personal_access_token"

# Create a test repository on GitHub first
# Example: https://github.com/yourusername/argocd-test-manifests
```

**Test:**
```bash
# Create application with Git save
argocd-cli workflows submit app \
  --app-name gitops-git-test \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace gitops-git \
  --gitops-repo https://github.com/yourusername/argocd-test-manifests \
  --gitops-branch main \
  --gitops-path applications

# Expected output:
# ✓ Successfully committed gitops-git-test.yaml to <repo-url>
```

**Verify:**
```bash
# Check your GitHub repository
# Should see: applications/gitops-git-test.yaml
```

### Step 8: Test ApplicationSet (Optional)

```bash
# Create environments file
cat > test-environments.json <<EOF
[
  {"name":"dev","cluster":"https://kubernetes.default.svc","namespace":"dev"},
  {"name":"staging","cluster":"https://kubernetes.default.svc","namespace":"staging"}
]
EOF

# Submit ApplicationSet
argocd-cli workflows submit appset \
  --appset-name multi-env-test \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --environments @test-environments.json \
  --save-manifest

# Monitor
argocd-cli workflows status <workflow-name> --watch
```

**Verify:**
```bash
# Check ApplicationSet created
kubectl get applicationset multi-env-test -n argocd

# Check generated Applications
kubectl get applications -n argocd

# Should see applications for dev and staging
```

### Step 9: Access UIs

**ArgoCD UI:**
```bash
# Port-forward
kubectl port-forward -n argocd svc/argocd-server 8080:443

# Open browser to: https://localhost:8080
# Login with admin credentials from Step 2
```

**Argo Workflows UI:**
```bash
# Port-forward (in a new terminal)
kubectl port-forward -n argo svc/argo-workflows-server 8081:2746

# Open browser to: http://localhost:8081
# No login required (server mode)
```

### Step 10: Cleanup Test Resources

```bash
# Delete test workflows
argocd-cli workflows delete --all --yes

# Delete test applications
kubectl delete applications -n argocd --all

# Delete test namespaces
kubectl delete ns test-app gitops-local gitops-git dev staging --wait=false
```

## Expected Results

### ✅ Success Criteria

1. **ArgoCD Installation**
   - ArgoCD pods running in `argocd` namespace
   - Admin credentials retrieved
   - UI accessible

2. **Argo Workflows Installation**
   - Workflow controller running
   - Server accessible
   - RBAC configured

3. **Template Creation**
   - 3 templates created successfully
   - Templates visible in list

4. **Application Creation**
   - Workflow completes successfully
   - Application created in ArgoCD
   - Destination namespace created

5. **GitOps - Local**
   - Manifest saved to `./argocd-manifests/`
   - Valid YAML format

6. **GitOps - Git** (if tested)
   - Manifest committed to Git repository
   - Visible on GitHub

7. **ApplicationSet** (if tested)
   - ApplicationSet created
   - Multiple Applications generated

## Troubleshooting

### Issue: ArgoCD Installation Fails

```bash
# Check Helm
helm version

# Check cluster access
kubectl cluster-info

# Check permissions
kubectl auth can-i create deployments --namespace argocd

# Try kubectl method instead
argocd-cli argocd install --use-kubectl
```

### Issue: Workflow Fails

```bash
# Check workflow status
argocd-cli workflows status <workflow-name>

# View detailed logs
argocd-cli workflows logs <workflow-name>

# Check RBAC
kubectl get clusterrole argo-workflow-role
kubectl get clusterrolebinding argo-workflow-binding

# Check ServiceAccount
kubectl get sa argo-workflow-sa -n argo
```

### Issue: GitOps Fails

```bash
# Verify credentials
echo $GIT_USERNAME
echo $GIT_TOKEN | cut -c1-10

# Test Git access
git ls-remote https://$GIT_USERNAME:$GIT_TOKEN@github.com/yourusername/repo

# Check error in CLI output
```

## Test Checklist

- [ ] ArgoCD installed successfully
- [ ] ArgoCD UI accessible
- [ ] Argo Workflows installed successfully
- [ ] Workflow templates created
- [ ] Application workflow succeeds
- [ ] Application visible in ArgoCD
- [ ] Local manifest save works
- [ ] Git manifest save works (optional)
- [ ] ApplicationSet works (optional)
- [ ] Workflows UI accessible
- [ ] Cleanup successful

## Performance Metrics

Expected timings:
- ArgoCD installation: ~2-3 minutes
- Argo Workflows installation: ~1-2 minutes
- Template creation: ~5-10 seconds
- Application workflow: ~30-60 seconds
- GitOps commit: ~5-10 seconds

## Next Steps After Testing

1. ✅ Verify all features work
2. ✅ Document any issues found
3. ✅ Test with real Helm charts
4. ✅ Set up production GitOps repository
5. ✅ Configure CI/CD integration
6. ✅ Train team on usage

---

**Ready to start testing!** Follow the steps above in order. 🚀
