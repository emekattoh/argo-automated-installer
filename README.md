# ArgoCD CLI - Workflow-Based Application Automation

A Python CLI tool that automates ArgoCD Application and ApplicationSet creation using Argo Workflows. Deploy Helm charts to Kubernetes clusters with minimal configuration and workflow-based orchestration.

## Table of Contents

- [Overview](#overview)
- [Features](#features)
- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Quick Start](#quick-start)
- [Usage Guide](#usage-guide)
- [Configuration](#configuration)
- [Troubleshooting](#troubleshooting)
- [Examples](#examples)

## Overview

This tool provides a streamlined interface for deploying applications to Kubernetes using ArgoCD and Argo Workflows. Instead of manually writing YAML manifests, you provide Helm chart references and deployment parameters, and the tool handles the rest through automated workflows.

**Key Benefits:**
- **Workflow-based automation**: Leverage Argo Workflows for reliable, auditable deployments
- **Minimal YAML**: No need to write ArgoCD Application manifests manually
- **Multi-environment support**: Deploy to multiple environments with ApplicationSets
- **Built-in validation**: Pre-flight checks catch configuration errors early
- **Rich monitoring**: Track workflow progress with detailed status and logs

## Features

- ✅ Install and configure Argo Workflows in your cluster
- ✅ Create ArgoCD Applications from Helm charts
- ✅ Create ApplicationSets for multi-environment deployments
- ✅ **GitOps Support**: Automatically save manifests to Git repositories
- ✅ Manage workflow templates (create, list, update)
- ✅ Submit and monitor workflow executions
- ✅ View workflow status and logs in real-time
- ✅ Delete workflows and clean up resources
- ✅ Input validation and error handling
- ✅ Rich terminal output with tables and color-coding

## Prerequisites

Before using this tool, ensure you have:

1. **Kubernetes Cluster**: Access to a Kubernetes cluster (v1.19+)
2. **kubectl**: Configured with cluster access
3. **Helm 3.x**: For installing Argo Workflows
4. **Python 3.8+**: For running the CLI tool
5. **ArgoCD** (optional): If you want to use existing ArgoCD installation

## Installation

### 1. Install Python Dependencies

```bash
pip install -r requirements.txt
```

### 2. Install the CLI Tool

```bash
# Install in development mode
pip install -e .

# Or run directly
python argocd_cli.py --help
```

### 3. Verify Installation

```bash
argocd-cli --version
```

## Quick Start

Get up and running in 5 minutes:

```bash
# 1. Install Argo Workflows in your cluster
argocd-cli workflows install

# 2. Create workflow templates
argocd-cli workflows templates create

# 3. Submit your first Application workflow
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://github.com/bitnami/charts \
  --chart-path bitnami/nginx

# 4. Monitor the workflow
argocd-cli workflows list
argocd-cli workflows status <workflow-name>
```

## Usage Guide

### Installing Argo Workflows

Install Argo Workflows in your Kubernetes cluster:

```bash
# Install with default settings (namespace: argo)
argocd-cli workflows install

# Install in a custom namespace
argocd-cli workflows install -n my-namespace

# Install with custom release name
argocd-cli workflows install --release-name my-argo
```


**What this does:**
- Adds the Argo Helm repository
- Installs Argo Workflows using Helm
- Configures RBAC permissions for workflow execution
- Sets up ServiceAccount with necessary permissions
- Displays UI access URL

**Verify installation:**

```bash
kubectl get pods -n argo
kubectl get svc -n argo
```

### Managing Workflow Templates

Workflow templates are reusable definitions for common automation tasks.

#### Create Templates

```bash
# Create all templates (application, applicationset, infrastructure)
argocd-cli workflows templates create

# Create specific template type
argocd-cli workflows templates create --template-type application
argocd-cli workflows templates create --template-type applicationset
argocd-cli workflows templates create --template-type infrastructure

# Create in custom namespace
argocd-cli workflows templates create -n my-namespace
```

**Available template types:**
- `application`: Create single ArgoCD Applications
- `applicationset`: Create ApplicationSets for multi-environment deployment
- `infrastructure`: Provision namespaces, secrets, and ConfigMaps
- `all`: Create all template types (default)

#### List Templates

```bash
# List all templates
argocd-cli workflows templates list

# List templates in specific namespace
argocd-cli workflows templates list -n my-namespace
```

**Output includes:**
- Template name
- Description
- Number of parameters
- Creation timestamp

### Creating Applications

Submit workflows to create ArgoCD Applications from Helm charts.

#### Basic Application Creation

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app
```

#### Application with Custom Values

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --values-file values-prod.yaml \
  --helm-parameters "replicas=3,image.tag=v2.0"
```

#### Application with Auto-Sync

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --sync-policy auto
```

**Sync policy options:**
- `manual`: Manual sync (default)
- `auto`: Automated sync
- `auto-prune`: Auto-sync with pruning of deleted resources
- `auto-heal`: Auto-sync with self-healing

#### Application with Custom Destination

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --app-namespace argocd \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --destination-cluster https://my-cluster.example.com \
  --destination-namespace production
```

#### Using Helm Repository

```bash
argocd-cli workflows submit app \
  --app-name nginx \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --helm-parameters "service.type=LoadBalancer"
```

### Creating ApplicationSets

Submit workflows to create ApplicationSets for multi-environment deployments.

#### ApplicationSet with Inline Environments

```bash
argocd-cli workflows submit appset \
  --appset-name my-appset \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --environments '[
    {"name":"dev","cluster":"https://kubernetes.default.svc","namespace":"dev"},
    {"name":"staging","cluster":"https://kubernetes.default.svc","namespace":"staging"},
    {"name":"prod","cluster":"https://kubernetes.default.svc","namespace":"prod"}
  ]'
```

### GitOps: Saving Manifests to Git

**NEW!** Automatically save your ArgoCD manifests to a Git repository for version control and GitOps workflow.

#### Save Manifest Locally

```bash
argocd-cli workflows submit app \
  --app-name my-app \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --save-manifest
```

Manifest saved to: `./argocd-manifests/my-app.yaml`

#### Save to Git Repository

```bash
# Set Git credentials
export GIT_USERNAME="your-username"
export GIT_TOKEN="ghp_your_github_token"

# Submit with GitOps
argocd-cli workflows submit app \
  --app-name production-api \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/api \
  --gitops-repo https://github.com/myorg/argocd-config \
  --gitops-branch main \
  --gitops-path applications
```

**Result:**
- Application created in ArgoCD
- Manifest committed to Git: `applications/production-api.yaml`
- Ready for GitOps workflow!

**GitOps Options:**
- `--gitops-repo` - Git repository URL for manifests
- `--gitops-branch` - Git branch (default: main)
- `--gitops-path` - Path in repo (default: argocd-manifests)
- `--save-manifest` - Save locally
- `--git-username` - Git username (or GIT_USERNAME env var)
- `--git-token` - Git token (or GIT_TOKEN env var)

📖 **See [GITOPS_USAGE.md](GITOPS_USAGE.md) for complete GitOps guide**

#### ApplicationSet from JSON File

Create an `environments.json` file:

```json
[
  {
    "name": "dev",
    "cluster": "https://kubernetes.default.svc",
    "namespace": "dev-apps"
  },
  {
    "name": "staging",
    "cluster": "https://kubernetes.default.svc",
    "namespace": "staging-apps"
  },
  {
    "name": "prod",
    "cluster": "https://prod-cluster.example.com",
    "namespace": "prod-apps"
  }
]
```

Submit the ApplicationSet:

```bash
argocd-cli workflows submit appset \
  --appset-name my-appset \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --environments @environments.json \
  --sync-policy auto
```

#### ApplicationSet with Git Generator

```bash
argocd-cli workflows submit appset \
  --appset-name my-appset \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --generator-type git \
  --environments '[{"name":"*","cluster":"https://kubernetes.default.svc","namespace":"{{path.basename}}"}]'
```

### Monitoring Workflows

Track workflow execution with status and log commands.

#### List All Workflows

```bash
# List all workflows
argocd-cli workflows list

# List workflows in specific namespace
argocd-cli workflows list -n my-namespace

# Filter by label
argocd-cli workflows list -l app=myapp -l env=prod
```

**Output includes:**
- Workflow name
- Status (Running, Succeeded, Failed, etc.)
- Progress (e.g., "3/5 steps completed")
- Start time
- Duration

#### Get Workflow Status

```bash
# Get status once
argocd-cli workflows status my-workflow-abc123

# Watch status in real-time (updates every 2 seconds)
argocd-cli workflows status my-workflow-abc123 --watch

# Check status in different namespace
argocd-cli workflows status my-workflow-abc123 -n my-namespace
```

**Status output includes:**
- Overall workflow phase
- Progress indicator
- Individual step status
- Error messages for failed steps
- Start and finish times

#### View Workflow Logs

```bash
# Get logs from all workflow steps
argocd-cli workflows logs my-workflow-abc123

# Get logs from specific step
argocd-cli workflows logs my-workflow-abc123 --step validate-inputs

# Stream logs in real-time
argocd-cli workflows logs my-workflow-abc123 --follow

# Stream logs from specific step
argocd-cli workflows logs my-workflow-abc123 -s create-application -f
```

**Log features:**
- Syntax highlighting for errors and warnings
- Timestamps for each log entry
- Step-by-step execution details
- Real-time streaming for running workflows

### Managing Workflows

Delete completed or failed workflows to clean up resources.

#### Delete Specific Workflow

```bash
# Delete with confirmation prompt
argocd-cli workflows delete my-workflow-abc123

# Delete without confirmation
argocd-cli workflows delete my-workflow-abc123 --yes

# Delete and retain logs
argocd-cli workflows delete my-workflow-abc123 --retain-logs
```

#### Delete Multiple Workflows

```bash
# Delete by label
argocd-cli workflows delete -l app=myapp -l env=dev

# Delete all workflows in namespace (with confirmation)
argocd-cli workflows delete --all

# Delete all without confirmation
argocd-cli workflows delete --all --yes
```

**Deletion options:**
- `--yes, -y`: Skip confirmation prompt
- `--retain-logs`: Keep workflow pods to preserve logs
- `--label, -l`: Filter by label selector
- `--all, -a`: Delete all workflows in namespace

## Configuration

### Configuration File

The CLI uses a configuration file at `~/.argocd-cli/config.yaml`:

```yaml
# Default namespace for Argo Workflows operations
namespace: argo

# Kubernetes context to use
cluster_context: my-cluster

# Path to kubeconfig file
kubeconfig: ~/.kube/config

# Output format (table, json, yaml)
output_format: table
```

### Environment Variables

Override configuration with environment variables:

```bash
# Set default namespace
export ARGO_NAMESPACE=my-namespace

# Set Kubernetes context
export KUBE_CONTEXT=my-cluster

# Set kubeconfig path
export KUBECONFIG=~/.kube/my-config

# Set output format
export ARGOCD_CLI_OUTPUT_FORMAT=json
```

### Command-Line Options

Override configuration per command:

```bash
# Use custom kubeconfig
argocd-cli --kubeconfig ~/.kube/prod-config workflows list

# Use specific context
argocd-cli --context prod-cluster workflows list

# Use custom namespace
argocd-cli workflows list -n custom-namespace
```

**Precedence order** (highest to lowest):
1. Command-line options
2. Environment variables
3. Configuration file
4. Default values

## Troubleshooting

### Common Issues

#### 1. Cannot Access Kubernetes Cluster

**Error:** `Cannot access Kubernetes cluster`

**Solutions:**
```bash
# Verify kubectl is configured
kubectl cluster-info

# Check kubeconfig
kubectl config view

# Test cluster connectivity
kubectl get nodes
```

#### 2. Argo Workflows Not Installed

**Error:** `Argo Workflows is not installed`

**Solutions:**
```bash
# Install Argo Workflows
argocd-cli workflows install

# Verify installation
kubectl get pods -n argo

# Check CRDs
kubectl get crd workflows.argoproj.io
```

#### 3. WorkflowTemplate Not Found

**Error:** `WorkflowTemplate 'create-argocd-application' not found`

**Solutions:**
```bash
# Create templates
argocd-cli workflows templates create

# List templates
argocd-cli workflows templates list

# Verify template exists
kubectl get workflowtemplates -n argo
```

#### 4. Workflow Submission Failed

**Error:** `Failed to submit workflow`

**Solutions:**
```bash
# Check Argo Workflows is running
kubectl get pods -n argo -l app=workflow-controller

# Check RBAC permissions
kubectl auth can-i create workflows.argoproj.io -n argo

# View controller logs
kubectl logs -n argo -l app=workflow-controller
```

#### 5. Workflow Execution Failed

**Error:** Workflow shows `Failed` status

**Solutions:**
```bash
# Check workflow status
argocd-cli workflows status <workflow-name>

# View workflow logs
argocd-cli workflows logs <workflow-name>

# Check workflow pods
kubectl get pods -n argo -l workflows.argoproj.io/workflow=<workflow-name>

# View pod logs
kubectl logs -n argo <pod-name>
```

### Debug Mode

Enable verbose logging for troubleshooting:

```bash
# Set log level
export LOG_LEVEL=DEBUG

# Run command with verbose output
argocd-cli --verbose workflows submit app ...
```

### Getting Help

```bash
# General help
argocd-cli --help

# Command-specific help
argocd-cli workflows --help
argocd-cli workflows submit app --help
argocd-cli workflows templates create --help
```

## Examples

### Example 1: Deploy NGINX to Development

```bash
# Submit workflow
argocd-cli workflows submit app \
  --app-name nginx-dev \
  --repo-url https://charts.bitnami.com/bitnami \
  --chart-path nginx \
  --destination-namespace dev \
  --helm-parameters "replicaCount=2,service.type=ClusterIP"

# Monitor workflow
argocd-cli workflows list
argocd-cli workflows status <workflow-name> --watch

# View logs
argocd-cli workflows logs <workflow-name>

# Verify Application created
kubectl get applications -n argocd
```

### Example 2: Multi-Environment Deployment

Create `environments.json`:

```json
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
```

Submit ApplicationSet:

```bash
argocd-cli workflows submit appset \
  --appset-name my-app-multienv \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --environments @environments.json \
  --sync-policy auto-prune

# Monitor ApplicationSet creation
argocd-cli workflows status <workflow-name> --watch

# Verify Applications generated
kubectl get applications -n argocd
kubectl get applicationsets -n argocd
```

### Example 3: Custom Values and Auto-Sync

Create `values-prod.yaml`:

```yaml
replicaCount: 3
image:
  tag: v2.0.0
resources:
  limits:
    cpu: 500m
    memory: 512Mi
  requests:
    cpu: 250m
    memory: 256Mi
```

Submit workflow:

```bash
argocd-cli workflows submit app \
  --app-name my-app-prod \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app \
  --values-file values-prod.yaml \
  --destination-namespace production \
  --sync-policy auto-heal \
  --helm-parameters "ingress.enabled=true,ingress.host=myapp.example.com"

# Watch deployment
argocd-cli workflows status <workflow-name> --watch
argocd-cli workflows logs <workflow-name> --follow
```

### Example 4: Cleanup Workflows

```bash
# List all workflows
argocd-cli workflows list

# Delete completed workflows
argocd-cli workflows delete -l status=Succeeded --yes

# Delete failed workflows and retain logs
argocd-cli workflows delete -l status=Failed --retain-logs --yes

# Delete all workflows (with confirmation)
argocd-cli workflows delete --all
```

### Example 5: Using Different Namespaces

```bash
# Install Argo Workflows in custom namespace
argocd-cli workflows install -n my-workflows

# Create templates in custom namespace
argocd-cli workflows templates create -n my-workflows

# Submit workflow to custom namespace
argocd-cli workflows submit app \
  -n my-workflows \
  --app-name my-app \
  --repo-url https://github.com/myorg/charts \
  --chart-path charts/my-app

# Monitor workflows in custom namespace
argocd-cli workflows list -n my-workflows
argocd-cli workflows status <workflow-name> -n my-workflows
```

---

## Additional Resources

- [Argo Workflows Documentation](https://argoproj.github.io/argo-workflows/)
- [ArgoCD Documentation](https://argo-cd.readthedocs.io/)
- [Helm Documentation](https://helm.sh/docs/)
- [Kubernetes Documentation](https://kubernetes.io/docs/)

## License

MIT License - See LICENSE file for details

## Contributing

Contributions are welcome! Please open an issue or submit a pull request.
