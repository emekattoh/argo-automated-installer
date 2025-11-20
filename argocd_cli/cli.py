"""Main CLI entry point for ArgoCD automation tool."""

import click
import os
from rich.console import Console

from argocd_cli.workflows_installer import WorkflowsInstaller
from argocd_cli.template_generator import TemplateGenerator
from argocd_cli.workflow_client import WorkflowClient
from argocd_cli.validators import Validator
from argocd_cli.formatters import Formatters
from argocd_cli.config import get_config
from argocd_cli.exceptions import (
    ArgoCDCLIError,
    ClusterAccessError,
    ValidationError,
    WorkflowSubmissionError,
    TemplateError
)
from argocd_cli.error_handlers import handle_cli_errors

console = Console()


@click.group()
@click.version_option(version="1.0.0", prog_name="argocd-cli")
@click.option(
    "--kubeconfig",
    envvar="KUBECONFIG",
    help="Path to kubeconfig file (defaults to $KUBECONFIG or ~/.kube/config)",
    type=click.Path(exists=True)
)
@click.option(
    "--context",
    help="Kubernetes context to use (defaults to current context)"
)
@click.pass_context
def cli(ctx, kubeconfig, context):
    """ArgoCD CLI - Automate ArgoCD Applications and ApplicationSets using Argo Workflows.
    
    This CLI tool provides workflow-based automation for creating and managing
    ArgoCD Applications and ApplicationSets from Helm charts.
    
    Global Options:
    
      --kubeconfig: Specify a custom kubeconfig file path
      
      --context: Use a specific Kubernetes context
    
    Command Hierarchy:
    
      workflows install          Install Argo Workflows in the cluster
      
      workflows templates        Manage workflow templates
        └── create              Create workflow templates
        └── list                List available templates
      
      workflows submit           Submit workflows
        └── app                 Submit Application creation workflow
        └── appset              Submit ApplicationSet creation workflow
      
      workflows list             List all workflows
      
      workflows status           Get workflow status
      
      workflows logs             View workflow logs
      
      workflows delete           Delete workflows
    
    Examples:
    
      # Install Argo Workflows
      argocd-cli workflows install
      
      # Create workflow templates
      argocd-cli workflows templates create
      
      # Submit an Application workflow
      argocd-cli workflows submit app --app-name my-app --repo-url https://github.com/myorg/charts --chart-path charts/my-app
      
      # Monitor workflows
      argocd-cli workflows list
      argocd-cli workflows status my-workflow-abc123
      argocd-cli workflows logs my-workflow-abc123
    
    For more information on a specific command, use:
      argocd-cli COMMAND --help
    """
    # Ensure context object exists
    ctx.ensure_object(dict)
    
    # Load configuration
    config = get_config()
    
    # Command-line options override config file
    # Use provided kubeconfig or fall back to config
    effective_kubeconfig = kubeconfig or config.kubeconfig
    effective_context = context or config.cluster_context
    
    # Store global options in context for use by subcommands
    ctx.obj['kubeconfig'] = effective_kubeconfig
    ctx.obj['context'] = effective_context
    ctx.obj['config'] = config
    
    # Set environment variables if provided
    if effective_kubeconfig:
        os.environ['KUBECONFIG'] = effective_kubeconfig
    
    if effective_context:
        os.environ['KUBE_CONTEXT'] = effective_context


@cli.group()
@click.option(
    "--namespace",
    "-n",
    envvar="ARGO_NAMESPACE",
    help="Kubernetes namespace for Argo Workflows operations (can also be set via ARGO_NAMESPACE env var or config file)"
)
@click.pass_context
def workflows(ctx, namespace):
    """Manage Argo Workflows and workflow executions.
    
    This command group provides comprehensive workflow management capabilities:
    
    - Install Argo Workflows in your cluster
    - Create and manage workflow templates
    - Submit workflows for Application and ApplicationSet creation
    - Monitor workflow execution status and logs
    - Delete completed or failed workflows
    
    The --namespace option can be set globally for all workflow commands,
    in the config file (~/.argocd-cli/config.yaml), via ARGO_NAMESPACE
    environment variable, or overridden per command.
    """
    # Get config from context
    config = ctx.obj.get('config')
    
    # Use provided namespace, or fall back to config, or default to 'argo'
    effective_namespace = namespace or (config.namespace if config else 'argo')
    
    # Store namespace in context for subcommands
    ctx.obj['workflows_namespace'] = effective_namespace


@workflows.group()
@click.pass_context
def templates(ctx):
    """Manage workflow templates.
    
    WorkflowTemplates are reusable workflow definitions that can be instantiated
    with different parameters. This tool provides templates for:
    
    - Application creation: Create ArgoCD Applications from Helm charts
    - ApplicationSet creation: Deploy to multiple environments
    - Infrastructure provisioning: Set up namespaces, secrets, and ConfigMaps
    """
    pass


@templates.command()
@click.option(
    "--template-type",
    "-t",
    type=click.Choice(["application", "applicationset", "infrastructure", "all"], case_sensitive=False),
    default="all",
    help="Type of template to create",
    show_default=True
)
@click.pass_context
def create(ctx, template_type: str):
    """
    Create workflow templates in the Kubernetes cluster.
    
    This command generates and applies WorkflowTemplate resources for:
    - Application: Create ArgoCD Applications from Helm charts
    - ApplicationSet: Create ArgoCD ApplicationSets for multi-environment deployments
    - Infrastructure: Provision infrastructure resources (namespaces, secrets, configmaps)
    
    Prerequisites:
    - kubectl configured with cluster access
    - Argo Workflows installed in the cluster
    - Sufficient cluster permissions to create WorkflowTemplates
    """
    # Get namespace from context (set by workflows group)
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    console.print("\n[bold cyan]Creating Workflow Templates...[/bold cyan]\n")
    
    try:
        # Validate cluster access
        validator = Validator()
        
        with console.status("[bold yellow]Validating cluster access...[/bold yellow]"):
            if not validator.validate_cluster_access():
                Formatters.print_error("Cannot access Kubernetes cluster")
                console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
                console.print("• Verify kubectl is configured: [bold]kubectl cluster-info[/bold]")
                console.print("• Check kubeconfig: [bold]kubectl config view[/bold]")
                console.print("• Verify cluster connectivity: [bold]kubectl get nodes[/bold]\n")
                raise click.ClickException("Cluster access validation failed")
        
        Formatters.print_success("Cluster access validated")
        
        # Validate namespace exists
        with console.status(f"[bold yellow]Validating namespace '{namespace}'...[/bold yellow]"):
            if not validator.validate_namespace(namespace):
                Formatters.print_warning(f"Namespace '{namespace}' does not exist, creating it...")
                import subprocess
                result = subprocess.run(
                    ["kubectl", "create", "namespace", namespace],
                    capture_output=True,
                    text=True
                )
                if result.returncode != 0:
                    Formatters.print_error(f"Failed to create namespace: {result.stderr}")
                    raise click.ClickException(f"Namespace creation failed")
                Formatters.print_success(f"Namespace '{namespace}' created")
            else:
                Formatters.print_success(f"Namespace '{namespace}' exists")
        
        # Initialize template generator
        generator = TemplateGenerator(namespace=namespace)
        
        templates_to_create = []
        if template_type == "all":
            templates_to_create = ["application", "applicationset", "infrastructure"]
        else:
            templates_to_create = [template_type]
        
        created_templates = []
        
        for tmpl_type in templates_to_create:
            console.print(f"\n[bold cyan]Creating {tmpl_type} template...[/bold cyan]")
            
            try:
                # Generate template YAML
                with console.status(f"[bold yellow]Generating {tmpl_type} template YAML...[/bold yellow]"):
                    if tmpl_type == "application":
                        template_yaml = generator.generate_application_template()
                        template_name = "create-argocd-application"
                    elif tmpl_type == "applicationset":
                        template_yaml = generator.generate_applicationset_template()
                        template_name = "create-argocd-applicationset"
                    elif tmpl_type == "infrastructure":
                        template_yaml = generator.generate_infrastructure_template()
                        template_name = "provision-infrastructure"
                
                Formatters.print_success(f"Generated {tmpl_type} template YAML")
                
                # Apply template to cluster
                with console.status(f"[bold yellow]Applying {tmpl_type} template to cluster...[/bold yellow]"):
                    generator.apply_template(template_yaml)
                
                Formatters.print_success(f"Template '{template_name}' created successfully")
                created_templates.append(template_name)
                
            except ValueError as e:
                Formatters.print_error(f"Validation error for {tmpl_type} template: {str(e)}")
                raise click.ClickException(f"Template validation failed: {str(e)}")
            except RuntimeError as e:
                Formatters.print_error(f"Failed to apply {tmpl_type} template: {str(e)}")
                raise click.ClickException(f"Template application failed: {str(e)}")
        
        # Summary
        console.print(f"\n[bold green]✓ Successfully created {len(created_templates)} template(s)[/bold green]\n")
        console.print("[bold cyan]Created Templates:[/bold cyan]")
        for tmpl in created_templates:
            console.print(f"  • {tmpl}")
        
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("1. List templates: [bold]argocd-cli workflows templates list[/bold]")
        console.print("2. Submit a workflow: [bold]argocd-cli workflows submit app[/bold]")
        console.print("3. Monitor workflows: [bold]argocd-cli workflows list[/bold]\n")
        
    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Verify Argo Workflows is installed: [bold]kubectl get pods -n argo[/bold]")
        console.print("• Check cluster permissions: [bold]kubectl auth can-i create workflowtemplates.argoproj.io -n argo[/bold]")
        console.print("• Review Argo Workflows logs: [bold]kubectl logs -n argo -l app=workflow-controller[/bold]\n")
        raise click.ClickException(f"Template creation error: {str(e)}")


@templates.command("list")
@click.pass_context
def list_templates(ctx):
    """
    List all workflow templates in the cluster.
    
    Displays a table with template names, descriptions, parameter counts,
    and creation timestamps.
    
    Prerequisites:
    - kubectl configured with cluster access
    - Argo Workflows installed in the cluster
    """
    # Get namespace from context
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    console.print("\n[bold cyan]Listing Workflow Templates...[/bold cyan]\n")
    
    try:
        # Initialize workflow client
        client = WorkflowClient(namespace=namespace)
        
        # List templates
        with console.status(f"[bold yellow]Retrieving templates from namespace '{namespace}'...[/bold yellow]"):
            templates = client.list_workflow_templates(namespace=namespace)
        
        if not templates:
            Formatters.print_warning(f"No workflow templates found in namespace '{namespace}'")
            console.print("\n[bold cyan]Tip:[/bold cyan] Create templates using: [bold]argocd-cli workflows templates create[/bold]\n")
            return
        
        # Format and display templates
        output = Formatters.format_template_list(templates)
        console.print(output)
        
        # Display additional information
        console.print(f"\n[dim]Found {len(templates)} template(s) in namespace '{namespace}'[/dim]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Error listing templates[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Verify cluster access: [bold]kubectl cluster-info[/bold]")
        console.print("• Check namespace exists: [bold]kubectl get namespace argo[/bold]")
        console.print("• Verify Argo Workflows is installed: [bold]kubectl get crd workflowtemplates.argoproj.io[/bold]\n")
        raise click.ClickException(f"Failed to list templates: {str(e)}")


@workflows.group()
@click.pass_context
def submit(ctx):
    """Submit workflows for Application and ApplicationSet creation.
    
    Submit workflows to create ArgoCD resources:
    
    - app: Create a single ArgoCD Application from a Helm chart
    - appset: Create an ApplicationSet for multi-environment deployment
    
    Workflows are executed by Argo Workflows and can be monitored using
    the status and logs commands.
    """
    pass


@submit.command("app")
@click.option(
    "--app-name",
    required=True,
    help="Name of the ArgoCD Application to create"
)
@click.option(
    "--app-namespace",
    default="argocd",
    help="Namespace where the Application will be created",
    show_default=True
)
@click.option(
    "--repo-url",
    required=True,
    help="Git repository URL or Helm repository URL containing the chart"
)
@click.option(
    "--chart-path",
    required=True,
    help="Path to Helm chart in repository or chart name"
)
@click.option(
    "--values-file",
    help="Path to values file for Helm chart (optional)"
)
@click.option(
    "--destination-cluster",
    default="https://kubernetes.default.svc",
    help="Destination cluster URL",
    show_default=True
)
@click.option(
    "--destination-namespace",
    help="Destination namespace for application deployment (defaults to app-name)"
)
@click.option(
    "--sync-policy",
    type=click.Choice(["manual", "auto", "auto-prune", "auto-heal"], case_sensitive=False),
    default="manual",
    help="Sync policy for the Application",
    show_default=True
)
@click.option(
    "--helm-parameters",
    help="Helm parameters as key=value pairs, comma-separated (e.g., 'replicas=3,image.tag=v1.0')"
)
@click.option(
    "--gitops-repo",
    help="Git repository URL for storing ArgoCD manifests (GitOps)"
)
@click.option(
    "--gitops-branch",
    default="main",
    help="Git branch for manifests",
    show_default=True
)
@click.option(
    "--gitops-path",
    default="argocd-manifests",
    help="Path within Git repo for manifests",
    show_default=True
)
@click.option(
    "--save-manifest",
    is_flag=True,
    help="Save manifest locally to ./argocd-manifests/"
)
@click.option(
    "--git-username",
    envvar="GIT_USERNAME",
    help="Git username for authentication (or set GIT_USERNAME env var)"
)
@click.option(
    "--git-token",
    envvar="GIT_TOKEN",
    help="Git token/password for authentication (or set GIT_TOKEN env var)"
)
@click.pass_context
def submit_app(
    ctx,
    app_name: str,
    app_namespace: str,
    repo_url: str,
    chart_path: str,
    values_file: str,
    destination_cluster: str,
    destination_namespace: str,
    sync_policy: str,
    helm_parameters: str,
    gitops_repo: str,
    gitops_branch: str,
    gitops_path: str,
    save_manifest: bool,
    git_username: str,
    git_token: str
):
    """
    Submit a workflow to create an ArgoCD Application from a Helm chart.
    
    This command submits a workflow that will:
    - Validate inputs and cluster access
    - Create the destination namespace if needed
    - Generate an ArgoCD Application manifest
    - Apply the Application to the cluster
    - Verify Application creation
    
    Prerequisites:
    - Argo Workflows installed and running
    - WorkflowTemplate 'create-argocd-application' exists
    - Sufficient cluster permissions
    
    Examples:
    
      # Create Application from Git repository
      argocd-cli workflows submit app \\
        --app-name my-app \\
        --repo-url https://github.com/myorg/charts \\
        --chart-path charts/my-app
      
      # Create Application with custom values and auto-sync
      argocd-cli workflows submit app \\
        --app-name my-app \\
        --repo-url https://github.com/myorg/charts \\
        --chart-path charts/my-app \\
        --values-file values-prod.yaml \\
        --sync-policy auto \\
        --helm-parameters "replicas=3,image.tag=v2.0"
    """
    # Get workflow namespace from context
    workflow_namespace = ctx.obj.get('workflows_namespace', 'argo')
    # Use app_namespace for the Application resource namespace
    namespace = app_namespace
    
    console.print("\n[bold cyan]Submitting Application Creation Workflow...[/bold cyan]\n")
    
    try:
        # Initialize validator and workflow client
        validator = Validator()
        client = WorkflowClient(namespace=workflow_namespace)
        
        # Validate cluster access
        with console.status("[bold yellow]Validating cluster access...[/bold yellow]"):
            if not validator.validate_cluster_access():
                Formatters.print_error("Cannot access Kubernetes cluster")
                console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
                console.print("• Verify kubectl is configured: [bold]kubectl cluster-info[/bold]")
                console.print("• Check kubeconfig: [bold]kubectl config view[/bold]\n")
                raise click.ClickException("Cluster access validation failed")
        
        Formatters.print_success("Cluster access validated")
        
        # Set default destination namespace if not provided
        if not destination_namespace:
            destination_namespace = app_name
        
        # Parse helm parameters if provided
        helm_params_dict = {}
        if helm_parameters:
            try:
                for param in helm_parameters.split(','):
                    if '=' in param:
                        key, value = param.split('=', 1)
                        helm_params_dict[key.strip()] = value.strip()
                    else:
                        Formatters.print_warning(f"Ignoring invalid parameter format: {param}")
            except Exception as e:
                Formatters.print_error(f"Failed to parse helm parameters: {str(e)}")
                raise click.ClickException("Invalid helm parameters format")
        
        # Parse sync policy
        automated = sync_policy in ["auto", "auto-prune", "auto-heal"]
        prune = sync_policy == "auto-prune"
        self_heal = sync_policy == "auto-heal"
        
        # Build workflow parameters
        parameters = {
            "app_name": app_name,
            "namespace": namespace,
            "repo_url": repo_url,
            "chart_path": chart_path,
            "destination_cluster": destination_cluster,
            "destination_namespace": destination_namespace,
            "sync_automated": str(automated).lower(),
            "sync_prune": str(prune).lower(),
            "sync_self_heal": str(self_heal).lower(),
        }
        
        # Add optional parameters
        if values_file:
            parameters["values_file"] = values_file
        
        if helm_params_dict:
            # Convert dict to comma-separated key=value format
            parameters["helm_parameters"] = ",".join([f"{k}={v}" for k, v in helm_params_dict.items()])
        
        # Validate required parameters
        with console.status("[bold yellow]Validating parameters...[/bold yellow]"):
            required_params = ["app_name", "namespace", "repo_url", "chart_path", 
                             "destination_cluster", "destination_namespace"]
            try:
                validator.validate_parameters(required_params, parameters)
            except Exception as e:
                Formatters.print_error(f"Parameter validation failed: {str(e)}")
                raise click.ClickException(str(e))
        
        Formatters.print_success("Parameters validated")
        
        # Validate Git URL if it's a Git repository (not a Helm repository)
        # Check if it's actually a Git URL by looking for .git or known Git hosting patterns
        is_git_repo = (
            repo_url.endswith('.git') or
            'github.com' in repo_url or
            'gitlab.com' in repo_url or
            'bitbucket.org' in repo_url or
            repo_url.startswith('git@') or
            repo_url.startswith('git://') or
            repo_url.startswith('ssh://')
        )
        
        if is_git_repo:
            with console.status("[bold yellow]Validating repository URL...[/bold yellow]"):
                try:
                    validator.validate_git_url(repo_url)
                    Formatters.print_success("Repository URL validated")
                except Exception as e:
                    Formatters.print_error(f"Repository URL validation failed: {str(e)}")
                    raise click.ClickException(str(e))
        
        # Display submission summary
        console.print("\n[bold cyan]Workflow Submission Summary:[/bold cyan]")
        console.print(f"  Application Name: [bold]{app_name}[/bold]")
        console.print(f"  Namespace: [bold]{namespace}[/bold]")
        console.print(f"  Repository: [bold]{repo_url}[/bold]")
        console.print(f"  Chart Path: [bold]{chart_path}[/bold]")
        console.print(f"  Destination Cluster: [bold]{destination_cluster}[/bold]")
        console.print(f"  Destination Namespace: [bold]{destination_namespace}[/bold]")
        console.print(f"  Sync Policy: [bold]{sync_policy}[/bold]")
        if values_file:
            console.print(f"  Values File: [bold]{values_file}[/bold]")
        if helm_params_dict:
            console.print(f"  Helm Parameters: [bold]{len(helm_params_dict)} parameter(s)[/bold]")
        console.print()
        
        # Submit workflow
        with console.status("[bold yellow]Submitting workflow to Argo Workflows...[/bold yellow]"):
            try:
                workflow_name = client.submit_workflow(
                    template_name="create-argocd-application",
                    parameters=parameters
                )
            except Exception as e:
                Formatters.print_error(f"Failed to submit workflow: {str(e)}")
                console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
                console.print("• Verify Argo Workflows is running: [bold]kubectl get pods -n argo[/bold]")
                console.print("• Check WorkflowTemplate exists: [bold]argocd-cli workflows templates list[/bold]")
                console.print("• Create templates if missing: [bold]argocd-cli workflows templates create[/bold]\n")
                raise click.ClickException(f"Workflow submission failed: {str(e)}")
        
        Formatters.print_success(f"Workflow submitted: {workflow_name}")
        
        # Get initial workflow status
        with console.status("[bold yellow]Retrieving workflow status...[/bold yellow]"):
            try:
                status = client.get_workflow_status(workflow_name)
                console.print(f"\n[bold green]✓ Workflow Created Successfully[/bold green]\n")
                console.print(f"  Workflow Name: [bold]{workflow_name}[/bold]")
                console.print(f"  Status: [bold]{status.phase}[/bold]")
                console.print(f"  Progress: [bold]{status.progress}[/bold]")
                if status.started_at:
                    console.print(f"  Started: [bold]{status.started_at.strftime('%Y-%m-%d %H:%M:%S')}[/bold]")
            except Exception as e:
                # Don't fail if we can't get status, workflow was submitted successfully
                Formatters.print_warning(f"Workflow submitted but status unavailable: {str(e)}")
        
        # GitOps: Save manifest to Git repository or locally
        if gitops_repo or save_manifest:
            from argocd_cli.gitops import GitOpsManager
            
            console.print("\n[bold cyan]GitOps: Saving Application Manifest...[/bold cyan]\n")
            
            # Generate the Application manifest
            # Detect if this is a Helm repository or Git repository
            is_helm_repo = 'charts.' in repo_url or 'artifacthub.io' in repo_url or 'chartmuseum' in repo_url
            
            if is_helm_repo:
                # Helm repository - use 'chart' field
                manifest_content = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app_name}
  namespace: {namespace}
spec:
  project: default
  source:
    repoURL: {repo_url}
    chart: {chart_path}
    targetRevision: "*"
    helm: {{}}
  destination:
    server: {destination_cluster}
    namespace: {destination_namespace}
  syncPolicy:
    syncOptions:
    - CreateNamespace=true
"""
            else:
                # Git repository - use 'path' field
                manifest_content = f"""apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {app_name}
  namespace: {namespace}
spec:
  project: default
  source:
    repoURL: {repo_url}
    path: {chart_path}
    targetRevision: HEAD
    helm: {{}}
  destination:
    server: {destination_cluster}
    namespace: {destination_namespace}
  syncPolicy:
    syncOptions:
    - CreateNamespace=true
"""
            
            # Add sync policy if automated
            if automated:
                manifest_content = manifest_content.replace(
                    "syncPolicy:",
                    f"""syncPolicy:
    automated:
      selfHeal: {self_heal}
      prune: {prune}"""
                )
            
            manifest_name = f"{app_name}.yaml"
            
            # Save to Git repository
            if gitops_repo:
                try:
                    gitops = GitOpsManager(
                        repo_url=gitops_repo,
                        branch=gitops_branch,
                        manifests_path=gitops_path,
                        git_username=git_username,
                        git_token=git_token
                    )
                    
                    with console.status("[bold yellow]Committing manifest to Git...[/bold yellow]"):
                        success, message = gitops.commit_manifest(
                            manifest_content=manifest_content,
                            manifest_name=manifest_name,
                            commit_message=f"Add ArgoCD Application: {app_name}"
                        )
                    
                    if success:
                        Formatters.print_success(message)
                    else:
                        Formatters.print_warning(f"GitOps commit failed: {message}")
                except Exception as e:
                    Formatters.print_warning(f"GitOps operation failed: {str(e)}")
            
            # Save locally
            if save_manifest:
                try:
                    gitops = GitOpsManager(repo_url="")  # Dummy URL for local save
                    success, message = gitops.save_manifest_locally(
                        manifest_content=manifest_content,
                        manifest_name=manifest_name
                    )
                    if success:
                        Formatters.print_success(message)
                    else:
                        Formatters.print_warning(message)
                except Exception as e:
                    Formatters.print_warning(f"Local save failed: {str(e)}")
        
        # Display next steps
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print(f"1. Monitor workflow: [bold]argocd-cli workflows status {workflow_name}[/bold]")
        console.print(f"2. View logs: [bold]argocd-cli workflows logs {workflow_name}[/bold]")
        console.print(f"3. List all workflows: [bold]argocd-cli workflows list[/bold]\n")
        
    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        raise click.ClickException(f"Workflow submission error: {str(e)}")


@submit.command("appset")
@click.option(
    "--appset-name",
    required=True,
    help="Name of the ArgoCD ApplicationSet to create"
)
@click.option(
    "--app-namespace",
    default="argocd",
    help="Namespace where the ApplicationSet will be created",
    show_default=True
)
@click.option(
    "--repo-url",
    required=True,
    help="Git repository URL or Helm repository URL containing the chart"
)
@click.option(
    "--chart-path",
    required=True,
    help="Path to Helm chart in repository or chart name"
)
@click.option(
    "--environments",
    required=True,
    help="JSON string or file path containing environment configurations (e.g., '[{\"name\":\"dev\",\"cluster\":\"...\",\"namespace\":\"dev\"}]')"
)
@click.option(
    "--generator-type",
    type=click.Choice(["list", "git"], case_sensitive=False),
    default="list",
    help="Generator type for ApplicationSet",
    show_default=True
)
@click.option(
    "--sync-policy",
    type=click.Choice(["manual", "auto", "auto-prune", "auto-heal"], case_sensitive=False),
    default="manual",
    help="Sync policy for generated Applications",
    show_default=True
)
@click.pass_context
def submit_appset(
    ctx,
    appset_name: str,
    app_namespace: str,
    repo_url: str,
    chart_path: str,
    environments: str,
    generator_type: str,
    sync_policy: str
):
    """
    Submit a workflow to create an ArgoCD ApplicationSet for multi-environment deployment.
    
    This command submits a workflow that will:
    - Validate inputs and environments
    - Validate all target clusters and namespaces
    - Generate an ApplicationSet manifest with appropriate generators
    - Apply the ApplicationSet to the cluster
    - Wait for Applications to be generated
    
    Prerequisites:
    - Argo Workflows installed and running
    - WorkflowTemplate 'create-argocd-applicationset' exists
    - Sufficient cluster permissions
    
    Examples:
    
      # Create ApplicationSet with inline JSON
      argocd-cli workflows submit appset \\
        --appset-name my-appset \\
        --repo-url https://github.com/myorg/charts \\
        --chart-path charts/my-app \\
        --environments '[{"name":"dev","cluster":"https://kubernetes.default.svc","namespace":"dev"},{"name":"prod","cluster":"https://kubernetes.default.svc","namespace":"prod"}]'
      
      # Create ApplicationSet from JSON file
      argocd-cli workflows submit appset \\
        --appset-name my-appset \\
        --repo-url https://github.com/myorg/charts \\
        --chart-path charts/my-app \\
        --environments @environments.json \\
        --generator-type list \\
        --sync-policy auto
    """
    # Get workflow namespace from context
    workflow_namespace = ctx.obj.get('workflows_namespace', 'argo')
    # Use app_namespace for the ApplicationSet resource namespace
    namespace = app_namespace
    
    console.print("\n[bold cyan]Submitting ApplicationSet Creation Workflow...[/bold cyan]\n")
    
    try:
        import json
        import os
        
        # Initialize validator and workflow client
        validator = Validator()
        client = WorkflowClient(namespace=workflow_namespace)
        
        # Validate cluster access
        with console.status("[bold yellow]Validating cluster access...[/bold yellow]"):
            if not validator.validate_cluster_access():
                Formatters.print_error("Cannot access Kubernetes cluster")
                console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
                console.print("• Verify kubectl is configured: [bold]kubectl cluster-info[/bold]")
                console.print("• Check kubeconfig: [bold]kubectl config view[/bold]\n")
                raise click.ClickException("Cluster access validation failed")
        
        Formatters.print_success("Cluster access validated")
        
        # Parse environments JSON
        environments_data = None
        with console.status("[bold yellow]Parsing environments configuration...[/bold yellow]"):
            try:
                # Check if environments is a file path (starts with @)
                if environments.startswith('@'):
                    file_path = environments[1:]
                    if not os.path.exists(file_path):
                        Formatters.print_error(f"Environments file not found: {file_path}")
                        raise click.ClickException(f"File not found: {file_path}")
                    
                    with open(file_path, 'r') as f:
                        environments_data = json.load(f)
                else:
                    # Parse as JSON string
                    environments_data = json.loads(environments)
                
                # Validate environments data structure
                if not isinstance(environments_data, list):
                    raise ValueError("Environments must be a JSON array")
                
                if len(environments_data) == 0:
                    raise ValueError("At least one environment must be specified")
                
                # Validate each environment has required fields
                for idx, env in enumerate(environments_data):
                    if not isinstance(env, dict):
                        raise ValueError(f"Environment {idx} must be a JSON object")
                    
                    required_fields = ["name", "cluster", "namespace"]
                    missing_fields = [f for f in required_fields if f not in env]
                    if missing_fields:
                        raise ValueError(
                            f"Environment '{env.get('name', idx)}' missing required fields: {', '.join(missing_fields)}"
                        )
                
            except json.JSONDecodeError as e:
                Formatters.print_error(f"Invalid JSON format: {str(e)}")
                console.print("\n[bold yellow]Tip:[/bold yellow] Environments must be valid JSON")
                console.print("Example: '[{\"name\":\"dev\",\"cluster\":\"https://kubernetes.default.svc\",\"namespace\":\"dev\"}]'\n")
                raise click.ClickException("Invalid environments JSON format")
            except ValueError as e:
                Formatters.print_error(f"Invalid environments configuration: {str(e)}")
                raise click.ClickException(str(e))
            except Exception as e:
                Formatters.print_error(f"Failed to parse environments: {str(e)}")
                raise click.ClickException(str(e))
        
        Formatters.print_success(f"Parsed {len(environments_data)} environment(s)")
        
        # Parse sync policy
        automated = sync_policy in ["auto", "auto-prune", "auto-heal"]
        prune = sync_policy == "auto-prune"
        self_heal = sync_policy == "auto-heal"
        
        # Build workflow parameters
        parameters = {
            "appset_name": appset_name,
            "namespace": namespace,
            "repo_url": repo_url,
            "chart_path": chart_path,
            "generator_type": generator_type,
            "environments": json.dumps(environments_data),
            "sync_automated": str(automated).lower(),
            "sync_prune": str(prune).lower(),
            "sync_self_heal": str(self_heal).lower(),
        }
        
        # Validate required parameters
        with console.status("[bold yellow]Validating parameters...[/bold yellow]"):
            required_params = ["appset_name", "namespace", "repo_url", "chart_path", 
                             "generator_type", "environments"]
            try:
                validator.validate_parameters(required_params, parameters)
            except Exception as e:
                Formatters.print_error(f"Parameter validation failed: {str(e)}")
                raise click.ClickException(str(e))
        
        Formatters.print_success("Parameters validated")
        
        # Validate Git URL if it's a Git repository (not a Helm repository)
        # Check if it's actually a Git URL by looking for .git or known Git hosting patterns
        is_git_repo = (
            repo_url.endswith('.git') or
            'github.com' in repo_url or
            'gitlab.com' in repo_url or
            'bitbucket.org' in repo_url or
            repo_url.startswith('git@') or
            repo_url.startswith('git://') or
            repo_url.startswith('ssh://')
        )
        
        if is_git_repo:
            with console.status("[bold yellow]Validating repository URL...[/bold yellow]"):
                try:
                    validator.validate_git_url(repo_url)
                    Formatters.print_success("Repository URL validated")
                except Exception as e:
                    Formatters.print_error(f"Repository URL validation failed: {str(e)}")
                    raise click.ClickException(str(e))
        
        # Display submission summary
        console.print("\n[bold cyan]Workflow Submission Summary:[/bold cyan]")
        console.print(f"  ApplicationSet Name: [bold]{appset_name}[/bold]")
        console.print(f"  Namespace: [bold]{namespace}[/bold]")
        console.print(f"  Repository: [bold]{repo_url}[/bold]")
        console.print(f"  Chart Path: [bold]{chart_path}[/bold]")
        console.print(f"  Generator Type: [bold]{generator_type}[/bold]")
        console.print(f"  Sync Policy: [bold]{sync_policy}[/bold]")
        console.print(f"  Environments: [bold]{len(environments_data)}[/bold]")
        
        # Display environment details
        console.print("\n[bold cyan]Target Environments:[/bold cyan]")
        for env in environments_data:
            console.print(f"  • {env['name']}: {env['cluster']} / {env['namespace']}")
        console.print()
        
        # Submit workflow
        with console.status("[bold yellow]Submitting workflow to Argo Workflows...[/bold yellow]"):
            try:
                workflow_name = client.submit_workflow(
                    template_name="create-argocd-applicationset",
                    parameters=parameters
                )
            except Exception as e:
                Formatters.print_error(f"Failed to submit workflow: {str(e)}")
                console.print("\n[bold yellow]Troubleshooting:[/bold yellow]")
                console.print("• Verify Argo Workflows is running: [bold]kubectl get pods -n argo[/bold]")
                console.print("• Check WorkflowTemplate exists: [bold]argocd-cli workflows templates list[/bold]")
                console.print("• Create templates if missing: [bold]argocd-cli workflows templates create[/bold]\n")
                raise click.ClickException(f"Workflow submission failed: {str(e)}")
        
        Formatters.print_success(f"Workflow submitted: {workflow_name}")
        
        # Get initial workflow status
        with console.status("[bold yellow]Retrieving workflow status...[/bold yellow]"):
            try:
                status = client.get_workflow_status(workflow_name)
                console.print(f"\n[bold green]✓ Workflow Created Successfully[/bold green]\n")
                console.print(f"  Workflow Name: [bold]{workflow_name}[/bold]")
                console.print(f"  Status: [bold]{status.phase}[/bold]")
                console.print(f"  Progress: [bold]{status.progress}[/bold]")
                if status.started_at:
                    console.print(f"  Started: [bold]{status.started_at.strftime('%Y-%m-%d %H:%M:%S')}[/bold]")
                
                # Display expected Applications count
                console.print(f"\n  Expected Applications: [bold]{len(environments_data)}[/bold]")
                console.print(f"  ApplicationSet will generate Applications for: [bold]{', '.join([e['name'] for e in environments_data])}[/bold]")
                
            except Exception as e:
                # Don't fail if we can't get status, workflow was submitted successfully
                Formatters.print_warning(f"Workflow submitted but status unavailable: {str(e)}")
        
        # Display next steps
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print(f"1. Monitor workflow: [bold]argocd-cli workflows status {workflow_name}[/bold]")
        console.print(f"2. View logs: [bold]argocd-cli workflows logs {workflow_name}[/bold]")
        console.print(f"3. List all workflows: [bold]argocd-cli workflows list[/bold]")
        console.print(f"4. Check generated Applications: [bold]kubectl get applications -n {namespace}[/bold]\n")
        
    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        raise click.ClickException(f"Workflow submission error: {str(e)}")


@workflows.command("list")
@click.option(
    "--label",
    "-l",
    multiple=True,
    help="Filter by label (format: key=value). Can be specified multiple times."
)
@click.pass_context
def list_workflows(ctx, label: tuple):
    """
    List all workflows in the cluster with their status.
    
    Displays a table showing workflow names, execution status, progress,
    start times, and durations. Supports filtering by namespace and labels.
    
    Prerequisites:
    - kubectl configured with cluster access
    - Argo Workflows installed in the cluster
    
    Examples:
    
      # List all workflows in default namespace
      argocd-cli workflows list
      
      # List workflows in specific namespace
      argocd-cli workflows list -n my-namespace
      
      # Filter by label
      argocd-cli workflows list -l app=myapp -l env=prod
    """
    # Get namespace from context
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    console.print("\n[bold cyan]Listing Workflows...[/bold cyan]\n")
    
    try:
        # Initialize workflow client
        client = WorkflowClient(namespace=namespace)
        
        # Parse labels
        labels = {}
        if label:
            for label_str in label:
                if '=' in label_str:
                    key, value = label_str.split('=', 1)
                    labels[key.strip()] = value.strip()
                else:
                    Formatters.print_warning(f"Ignoring invalid label format: {label_str}")
        
        # List workflows
        with console.status(f"[bold yellow]Retrieving workflows from namespace '{namespace}'...[/bold yellow]"):
            workflows = client.list_workflows(namespace=namespace, labels=labels if labels else None)
        
        if not workflows:
            Formatters.print_warning(f"No workflows found in namespace '{namespace}'")
            if labels:
                console.print(f"\n[dim]Applied label filters: {', '.join([f'{k}={v}' for k, v in labels.items()])}[/dim]")
            console.print("\n[bold cyan]Tip:[/bold cyan] Submit a workflow using: [bold]argocd-cli workflows submit app[/bold]\n")
            return
        
        # Format and display workflows
        output = Formatters.format_workflow_list(workflows)
        console.print(output)
        
        # Display additional information
        filter_info = ""
        if labels:
            filter_info = f" (filtered by: {', '.join([f'{k}={v}' for k, v in labels.items()])})"
        console.print(f"\n[dim]Found {len(workflows)} workflow(s) in namespace '{namespace}'{filter_info}[/dim]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Error listing workflows[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Verify cluster access: [bold]kubectl cluster-info[/bold]")
        console.print("• Check namespace exists: [bold]kubectl get namespace argo[/bold]")
        console.print("• Verify Argo Workflows is installed: [bold]kubectl get crd workflows.argoproj.io[/bold]\n")
        raise click.ClickException(f"Failed to list workflows: {str(e)}")


@workflows.command("status")
@click.argument("workflow_name")
@click.option(
    "--watch",
    "-w",
    is_flag=True,
    help="Watch workflow status in real-time (updates every 2 seconds)"
)
@click.pass_context
def workflow_status(ctx, workflow_name: str, watch: bool):
    """
    Display detailed status for a specific workflow.
    
    Shows comprehensive information about a workflow including:
    - Overall workflow status and progress
    - Individual step status and duration
    - Error messages for failed steps
    - Real-time updates for running workflows (with --watch flag)
    
    Prerequisites:
    - kubectl configured with cluster access
    - Argo Workflows installed in the cluster
    
    Examples:
    
      # Get status of a specific workflow
      argocd-cli workflows status my-workflow-abc123
      
      # Watch workflow status in real-time
      argocd-cli workflows status my-workflow-abc123 --watch
      
      # Check workflow in different namespace
      argocd-cli workflows status my-workflow-abc123 -n my-namespace
    """
    # Get namespace from context
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    try:
        # Initialize workflow client
        client = WorkflowClient(namespace=namespace)
        
        if watch:
            # Watch mode - continuously update status
            console.print(f"\n[bold cyan]Watching Workflow Status (Press Ctrl+C to stop)...[/bold cyan]\n")
            
            try:
                import time
                while True:
                    # Clear screen (works on most terminals)
                    console.clear()
                    console.print(f"\n[bold cyan]Workflow Status (updating every 2s)[/bold cyan]\n")
                    
                    # Get and display status
                    status = client.get_workflow_status(workflow_name)
                    output = Formatters.format_workflow_status(status)
                    console.print(output)
                    
                    # Check if workflow is complete
                    if status.phase in ["Succeeded", "Failed", "Error"]:
                        console.print(f"\n[bold]Workflow completed with status: {status.phase}[/bold]")
                        break
                    
                    # Wait before next update
                    time.sleep(2)
            except KeyboardInterrupt:
                console.print("\n\n[dim]Stopped watching workflow status[/dim]\n")
        else:
            # Single status check
            console.print(f"\n[bold cyan]Retrieving Workflow Status...[/bold cyan]\n")
            
            with console.status(f"[bold yellow]Fetching status for workflow '{workflow_name}'...[/bold yellow]"):
                status = client.get_workflow_status(workflow_name)
            
            # Display status
            output = Formatters.format_workflow_status(status)
            console.print(output)
            
            # Display next steps based on status
            console.print("\n[bold cyan]Available Commands:[/bold cyan]")
            console.print(f"• View logs: [bold]argocd-cli workflows logs {workflow_name}[/bold]")
            
            if status.phase in ["Running", "Pending"]:
                console.print(f"• Watch status: [bold]argocd-cli workflows status {workflow_name} --watch[/bold]")
            
            if status.phase in ["Succeeded", "Failed", "Error"]:
                console.print(f"• Delete workflow: [bold]argocd-cli workflows delete {workflow_name}[/bold]")
            
            console.print()
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Error retrieving workflow status[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Verify workflow exists: [bold]argocd-cli workflows list[/bold]")
        console.print(f"• Check workflow name: [bold]kubectl get workflows -n {namespace}[/bold]")
        console.print("• Verify cluster access: [bold]kubectl cluster-info[/bold]\n")
        raise click.ClickException(f"Failed to get workflow status: {str(e)}")


@workflows.command("logs")
@click.argument("workflow_name")
@click.option(
    "--step",
    "-s",
    help="Filter logs by specific workflow step name"
)
@click.option(
    "--follow",
    "-f",
    is_flag=True,
    help="Stream logs in real-time for running workflows"
)
@click.pass_context
def workflow_logs(ctx, workflow_name: str, step: str, follow: bool):
    """
    Retrieve and display logs from a workflow.
    
    Shows logs from all workflow steps or a specific step. Logs are displayed
    with timestamps in chronological order, with syntax highlighting for
    errors, warnings, and success messages.
    
    Prerequisites:
    - kubectl configured with cluster access
    - Argo Workflows installed in the cluster
    
    Examples:
    
      # Get logs from all workflow steps
      argocd-cli workflows logs my-workflow-abc123
      
      # Get logs from a specific step
      argocd-cli workflows logs my-workflow-abc123 --step validate-inputs
      
      # Stream logs in real-time
      argocd-cli workflows logs my-workflow-abc123 --follow
      
      # Stream logs from specific step
      argocd-cli workflows logs my-workflow-abc123 -s create-application -f
    """
    # Get namespace from context
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    try:
        # Initialize workflow client
        client = WorkflowClient(namespace=namespace)
        
        if follow:
            # Stream logs in real-time
            step_info = f" from step '{step}'" if step else ""
            console.print(f"\n[bold cyan]Streaming Workflow Logs{step_info} (Press Ctrl+C to stop)...[/bold cyan]\n")
            
            try:
                for log_line in client.stream_workflow_logs(workflow_name, step=step, follow=True):
                    # Format and display each log line
                    formatted = Formatters.format_workflow_logs(log_line, highlight_errors=True)
                    console.print(formatted, end='')
            except KeyboardInterrupt:
                console.print("\n\n[dim]Stopped streaming logs[/dim]\n")
        else:
            # Get logs once
            step_info = f" from step '{step}'" if step else ""
            console.print(f"\n[bold cyan]Retrieving Workflow Logs{step_info}...[/bold cyan]\n")
            
            with console.status(f"[bold yellow]Fetching logs for workflow '{workflow_name}'...[/bold yellow]"):
                logs = client.get_workflow_logs(workflow_name, step=step)
            
            # Display logs with formatting
            if logs:
                output = Formatters.format_workflow_logs(logs, highlight_errors=True)
                console.print(output)
            else:
                Formatters.print_warning("No logs available yet")
                console.print("\n[bold cyan]Tip:[/bold cyan] Logs may not be available if the workflow hasn't started yet")
                console.print(f"Check workflow status: [bold]argocd-cli workflows status {workflow_name}[/bold]\n")
            
            # Display next steps
            console.print("\n[bold cyan]Available Commands:[/bold cyan]")
            console.print(f"• Check status: [bold]argocd-cli workflows status {workflow_name}[/bold]")
            console.print(f"• Stream logs: [bold]argocd-cli workflows logs {workflow_name} --follow[/bold]")
            console.print(f"• List all workflows: [bold]argocd-cli workflows list[/bold]")
            console.print()
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Error retrieving workflow logs[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Verify workflow exists: [bold]argocd-cli workflows list[/bold]")
        console.print(f"• Check workflow status: [bold]argocd-cli workflows status {workflow_name}[/bold]")
        console.print(f"• Verify pods are running: [bold]kubectl get pods -n {namespace} -l workflows.argoproj.io/workflow={workflow_name}[/bold]\n")
        raise click.ClickException(f"Failed to get workflow logs: {str(e)}")


@workflows.command("delete")
@click.argument("workflow_name", required=False)
@click.option(
    "--label",
    "-l",
    multiple=True,
    help="Delete workflows by label selector (format: key=value). Can be specified multiple times."
)
@click.option(
    "--all",
    "-a",
    is_flag=True,
    help="Delete all workflows in the namespace (use with caution)"
)
@click.option(
    "--retain-logs",
    is_flag=True,
    help="Retain workflow pods to preserve logs after deletion"
)
@click.option(
    "--yes",
    "-y",
    is_flag=True,
    help="Skip confirmation prompt"
)
@click.pass_context
def delete_workflow(ctx, workflow_name: str, label: tuple, all: bool, retain_logs: bool, yes: bool):
    """
    Delete workflows from the cluster.
    
    This command can delete:
    - A specific workflow by name
    - Multiple workflows matching label selectors
    - All workflows in a namespace (with --all flag)
    
    By default, associated pods are deleted. Use --retain-logs to keep pods
    and preserve logs for troubleshooting.
    
    Prerequisites:
    - kubectl configured with cluster access
    - Argo Workflows installed in the cluster
    - Sufficient permissions to delete workflows
    
    Examples:
    
      # Delete a specific workflow
      argocd-cli workflows delete my-workflow-abc123
      
      # Delete workflows by label
      argocd-cli workflows delete -l app=myapp -l env=dev
      
      # Delete all workflows in namespace (with confirmation)
      argocd-cli workflows delete --all
      
      # Delete workflow and retain logs
      argocd-cli workflows delete my-workflow-abc123 --retain-logs
      
      # Delete without confirmation prompt
      argocd-cli workflows delete my-workflow-abc123 --yes
    """
    # Get namespace from context
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    console.print("\n[bold cyan]Deleting Workflows...[/bold cyan]\n")
    
    try:
        # Initialize workflow client
        client = WorkflowClient(namespace=namespace)
        
        # Validate input - must provide either workflow_name, labels, or --all
        if not workflow_name and not label and not all:
            Formatters.print_error("Must specify either a workflow name, label selectors (-l), or --all flag")
            console.print("\n[bold yellow]Examples:[/bold yellow]")
            console.print("• Delete specific workflow: [bold]argocd-cli workflows delete my-workflow-abc123[/bold]")
            console.print("• Delete by label: [bold]argocd-cli workflows delete -l app=myapp[/bold]")
            console.print("• Delete all: [bold]argocd-cli workflows delete --all[/bold]\n")
            raise click.ClickException("Invalid arguments")
        
        # Parse labels
        labels = {}
        if label:
            for label_str in label:
                if '=' in label_str:
                    key, value = label_str.split('=', 1)
                    labels[key.strip()] = value.strip()
                else:
                    Formatters.print_warning(f"Ignoring invalid label format: {label_str}")
        
        # Determine workflows to delete
        workflows_to_delete = []
        
        if workflow_name:
            # Delete specific workflow by name
            with console.status(f"[bold yellow]Checking workflow '{workflow_name}'...[/bold yellow]"):
                try:
                    status = client.get_workflow_status(workflow_name)
                    workflows_to_delete = [{"name": workflow_name, "phase": status.phase}]
                except Exception as e:
                    Formatters.print_error(f"Workflow '{workflow_name}' not found: {str(e)}")
                    raise click.ClickException(f"Workflow not found: {workflow_name}")
        
        elif labels or all:
            # Delete by label selector or all workflows
            with console.status(f"[bold yellow]Finding workflows to delete...[/bold yellow]"):
                workflows = client.list_workflows(namespace=namespace, labels=labels if labels else None)
                
                if not workflows:
                    filter_info = ""
                    if labels:
                        filter_info = f" matching labels: {', '.join([f'{k}={v}' for k, v in labels.items()])}"
                    elif all:
                        filter_info = f" in namespace '{namespace}'"
                    
                    Formatters.print_warning(f"No workflows found{filter_info}")
                    console.print("\n[bold cyan]Tip:[/bold cyan] List workflows using: [bold]argocd-cli workflows list[/bold]\n")
                    return
                
                for wf in workflows:
                    wf_name = wf.get("metadata", {}).get("name")
                    wf_phase = wf.get("status", {}).get("phase", "Unknown")
                    if wf_name:
                        workflows_to_delete.append({"name": wf_name, "phase": wf_phase})
        
        # Display workflows to be deleted
        console.print(f"[bold yellow]Found {len(workflows_to_delete)} workflow(s) to delete:[/bold yellow]\n")
        
        from rich.table import Table
        table = Table(show_header=True, header_style="bold cyan")
        table.add_column("Workflow Name", style="white")
        table.add_column("Status", style="white")
        
        for wf in workflows_to_delete:
            # Color-code status
            phase = wf["phase"]
            if phase == "Succeeded":
                status_display = f"[green]{phase}[/green]"
            elif phase == "Failed" or phase == "Error":
                status_display = f"[red]{phase}[/red]"
            elif phase == "Running":
                status_display = f"[yellow]{phase}[/yellow]"
            else:
                status_display = phase
            
            table.add_row(wf["name"], status_display)
        
        console.print(table)
        console.print()
        
        # Display deletion options
        if retain_logs:
            console.print("[bold yellow]Note:[/bold yellow] Workflow pods will be retained to preserve logs")
        else:
            console.print("[bold yellow]Note:[/bold yellow] Workflow pods will be deleted (logs will be lost)")
        
        console.print()
        
        # Confirmation prompt
        if not yes:
            confirm = click.confirm(
                f"Are you sure you want to delete {len(workflows_to_delete)} workflow(s)?",
                default=False
            )
            
            if not confirm:
                console.print("\n[dim]Deletion cancelled[/dim]\n")
                return
        
        # Delete workflows
        console.print()
        deleted_count = 0
        failed_count = 0
        
        with console.status("[bold yellow]Deleting workflows...[/bold yellow]"):
            for wf in workflows_to_delete:
                try:
                    client.delete_workflow(wf["name"], delete_pods=not retain_logs)
                    deleted_count += 1
                except Exception as e:
                    Formatters.print_error(f"Failed to delete workflow '{wf['name']}': {str(e)}")
                    failed_count += 1
        
        # Display results
        console.print()
        if deleted_count > 0:
            Formatters.print_success(f"Successfully deleted {deleted_count} workflow(s)")
        
        if failed_count > 0:
            Formatters.print_warning(f"Failed to delete {failed_count} workflow(s)")
        
        # Display next steps
        if deleted_count > 0:
            console.print("\n[bold cyan]Next Steps:[/bold cyan]")
            console.print("• List remaining workflows: [bold]argocd-cli workflows list[/bold]")
            
            if retain_logs:
                console.print(f"• View retained pods: [bold]kubectl get pods -n {namespace}[/bold]")
                console.print(f"• Clean up pods manually: [bold]kubectl delete pods -n {namespace} -l workflows.argoproj.io/completed=true[/bold]")
            
            console.print()
        
    except click.ClickException:
        raise
    except Exception as e:
        console.print(f"\n[bold red]✗ Error deleting workflows[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Verify cluster access: [bold]kubectl cluster-info[/bold]")
        console.print(f"• Check workflows exist: [bold]argocd-cli workflows list -n {namespace}[/bold]")
        console.print("• Verify permissions: [bold]kubectl auth can-i delete workflows.argoproj.io[/bold]\n")
        raise click.ClickException(f"Failed to delete workflows: {str(e)}")


@workflows.command()
@click.option(
    "--release-name",
    "-r",
    default="argo-workflows",
    help="Helm release name for Argo Workflows",
    show_default=True
)
@click.pass_context
def install(ctx, release_name: str):
    """
    Install Argo Workflows in the Kubernetes cluster.
    
    This command will:
    - Validate cluster accessibility
    - Install Argo Workflows using Helm
    - Configure RBAC permissions for workflow execution
    - Display the UI access URL
    
    Prerequisites:
    - kubectl configured with cluster access
    - Helm 3.x installed
    - Sufficient cluster permissions
    """
    # Get namespace from context
    namespace = ctx.obj.get('workflows_namespace', 'argo')
    
    console.print("\n[bold cyan]Installing Argo Workflows...[/bold cyan]\n")
    
    try:
        installer = WorkflowsInstaller()
        
        # Perform installation
        with console.status("[bold yellow]Installing Argo Workflows via Helm...[/bold yellow]"):
            success, message = installer.install_argo_workflows(namespace, release_name)
        
        if success:
            console.print(f"\n[bold green]✓ Success![/bold green]\n")
            console.print(message)
            console.print("\n[bold cyan]Next Steps:[/bold cyan]")
            console.print("1. Access the Argo Workflows UI using the URL above")
            console.print("2. Create workflow templates: [bold]argocd-cli workflows templates create[/bold]")
            console.print("3. Submit workflows: [bold]argocd-cli workflows submit app[/bold]\n")
        else:
            console.print(f"\n[bold red]✗ Installation Failed[/bold red]\n")
            console.print(f"[red]{message}[/red]\n")
            console.print("[bold yellow]Troubleshooting:[/bold yellow]")
            console.print("• Verify kubectl is configured: [bold]kubectl cluster-info[/bold]")
            console.print("• Check Helm installation: [bold]helm version[/bold]")
            console.print("• Verify cluster permissions: [bold]kubectl auth can-i create deployments --namespace argo[/bold]")
            console.print("• Check existing installation: [bold]helm list -n argo[/bold]\n")
            raise click.ClickException(message)
            
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        console.print("• Ensure you have a valid kubeconfig file")
        console.print("• Verify network connectivity to the cluster")
        console.print("• Check cluster resource availability")
        console.print("• Review logs: [bold]kubectl logs -n argo -l app.kubernetes.io/name=argo-workflows-server[/bold]\n")
        raise click.ClickException(f"Installation error: {str(e)}")


@cli.group()
def argocd():
    """Manage ArgoCD installation and configuration.
    
    This command group provides ArgoCD installation and management:
    
    - Install ArgoCD in your cluster
    - Check ArgoCD installation status
    - Get ArgoCD admin credentials
    
    ArgoCD is required for the Applications and ApplicationSets created
    by this CLI tool to function properly.
    """
    pass


@argocd.command()
@click.option(
    "--namespace",
    "-n",
    default="argocd",
    help="Kubernetes namespace for ArgoCD installation",
    show_default=True
)
@click.option(
    "--release-name",
    "-r",
    default="argocd",
    help="Helm release name for ArgoCD",
    show_default=True
)
@click.option(
    "--use-kubectl",
    is_flag=True,
    help="Use kubectl manifests instead of Helm"
)
@click.option(
    "--version",
    "-v",
    help="Specific ArgoCD version to install"
)
def install(namespace: str, release_name: str, use_kubectl: bool, version: str):
    """
    Install ArgoCD in the Kubernetes cluster.
    
    This command will:
    - Validate cluster accessibility
    - Install ArgoCD using Helm or kubectl
    - Display admin credentials
    - Show UI access URL
    
    Prerequisites:
    - kubectl configured with cluster access
    - Helm 3.x installed (if not using --use-kubectl)
    - Sufficient cluster permissions
    
    Examples:
    
      # Install with Helm (recommended)
      argocd-cli argocd install
      
      # Install in custom namespace
      argocd-cli argocd install -n my-argocd
      
      # Install using kubectl manifests
      argocd-cli argocd install --use-kubectl
      
      # Install specific version
      argocd-cli argocd install --version v2.9.0
    """
    from argocd_cli.argocd_installer import ArgoCDInstaller
    
    console.print("\n[bold cyan]Installing ArgoCD...[/bold cyan]\n")
    
    try:
        installer = ArgoCDInstaller()
        
        # Perform installation
        with console.status("[bold yellow]Installing ArgoCD...[/bold yellow]"):
            success, message = installer.install_argocd(
                namespace=namespace,
                release_name=release_name,
                use_helm=not use_kubectl,
                version=version
            )
        
        if success:
            console.print(f"\n[bold green]✓ Success![/bold green]\n")
            console.print(message)
            console.print("\n[bold cyan]Next Steps:[/bold cyan]")
            console.print("1. Access the ArgoCD UI using the URL above")
            console.print("2. Login with the admin credentials")
            console.print("3. Install Argo Workflows: [bold]argocd-cli workflows install[/bold]")
            console.print("4. Create workflow templates: [bold]argocd-cli workflows templates create[/bold]\n")
        else:
            console.print(f"\n[bold red]✗ Installation Failed[/bold red]\n")
            console.print(f"[red]{message}[/red]\n")
            console.print("[bold yellow]Troubleshooting:[/bold yellow]")
            console.print("• Verify kubectl is configured: [bold]kubectl cluster-info[/bold]")
            console.print("• Check Helm installation: [bold]helm version[/bold]")
            console.print("• Verify cluster permissions: [bold]kubectl auth can-i create deployments --namespace argocd[/bold]")
            console.print("• Check existing installation: [bold]argocd-cli argocd status[/bold]\n")
            raise click.ClickException(message)
            
    except Exception as e:
        console.print(f"\n[bold red]✗ Unexpected Error[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        raise click.ClickException(f"Installation error: {str(e)}")


@argocd.command()
@click.option(
    "--namespace",
    "-n",
    default="argocd",
    help="Kubernetes namespace to check",
    show_default=True
)
def status(namespace: str):
    """
    Check ArgoCD installation status.
    
    This command checks if ArgoCD is installed and running in the cluster.
    
    Examples:
    
      # Check default namespace
      argocd-cli argocd status
      
      # Check custom namespace
      argocd-cli argocd status -n my-argocd
    """
    from argocd_cli.argocd_installer import ArgoCDInstaller
    
    console.print("\n[bold cyan]Checking ArgoCD Status...[/bold cyan]\n")
    
    try:
        installer = ArgoCDInstaller()
        
        with console.status("[bold yellow]Checking installation...[/bold yellow]"):
            is_installed, message = installer.check_argocd_installed(namespace)
        
        if is_installed:
            Formatters.print_success(message)
            
            # Get admin password
            admin_password = installer.get_admin_password(namespace)
            console.print(f"\n[bold cyan]Admin Credentials:[/bold cyan]")
            console.print(f"  Username: [bold]admin[/bold]")
            console.print(f"  Password: [bold]{admin_password}[/bold]")
            
            # Get UI URL
            ui_url = installer.get_ui_url(namespace, "argocd-server")
            console.print(f"\n{ui_url}\n")
        else:
            Formatters.print_warning(message)
            console.print("\n[bold cyan]To install ArgoCD:[/bold cyan]")
            console.print("[bold]argocd-cli argocd install[/bold]\n")
            
    except Exception as e:
        console.print(f"\n[bold red]✗ Error[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        raise click.ClickException(f"Status check error: {str(e)}")


@cli.group()
def config():
    """Manage CLI configuration.
    
    Configuration is stored in ~/.argocd-cli/config.yaml and can be
    used to set default values for common options like namespace,
    cluster context, and output format.
    
    Configuration precedence (highest to lowest):
    1. Command-line options
    2. Environment variables
    3. Configuration file
    4. Built-in defaults
    """
    pass


@config.command("init")
def config_init():
    """Initialize configuration file with default values.
    
    Creates ~/.argocd-cli/config.yaml with default configuration.
    If the file already exists, it will not be overwritten.
    """
    from pathlib import Path
    
    config_obj = get_config()
    config_path = config_obj.config_path
    
    if config_path.exists():
        console.print(f"\n[bold yellow]Configuration file already exists:[/bold yellow] {config_path}\n")
        console.print("Use [bold]argocd-cli config set[/bold] to modify values")
        console.print("or [bold]argocd-cli config show[/bold] to view current configuration\n")
        return
    
    try:
        config_obj.create_default_config()
        console.print(f"\n[bold green]✓ Configuration file created:[/bold green] {config_path}\n")
        console.print("[bold cyan]Default Configuration:[/bold cyan]")
        console.print(f"  namespace: {config_obj.namespace}")
        console.print(f"  cluster_context: {config_obj.cluster_context or 'None (use current context)'}")
        console.print(f"  output_format: {config_obj.output_format}")
        console.print(f"  kubeconfig: {config_obj.kubeconfig or 'None (use default)'}")
        console.print("\n[bold cyan]Next Steps:[/bold cyan]")
        console.print("• View configuration: [bold]argocd-cli config show[/bold]")
        console.print("• Set values: [bold]argocd-cli config set namespace my-namespace[/bold]")
        console.print("• Edit file directly: [bold]$EDITOR ~/.argocd-cli/config.yaml[/bold]\n")
    except Exception as e:
        console.print(f"\n[bold red]✗ Failed to create configuration file[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        raise click.ClickException(f"Configuration initialization failed: {str(e)}")


@config.command("show")
def config_show():
    """Display current configuration.
    
    Shows the effective configuration including values from the config file,
    environment variables, and defaults.
    """
    config_obj = get_config()
    config_path = config_obj.config_path
    
    console.print(f"\n[bold cyan]Configuration File:[/bold cyan] {config_path}")
    
    if not config_path.exists():
        console.print("[bold yellow]Status:[/bold yellow] Not initialized")
        console.print("\n[bold cyan]Tip:[/bold cyan] Run [bold]argocd-cli config init[/bold] to create configuration file\n")
    else:
        console.print("[bold green]Status:[/bold green] Initialized")
    
    console.print("\n[bold cyan]Current Configuration:[/bold cyan]")
    console.print(f"  namespace: [bold]{config_obj.namespace}[/bold]")
    console.print(f"  cluster_context: [bold]{config_obj.cluster_context or 'None (use current context)'}[/bold]")
    console.print(f"  output_format: [bold]{config_obj.output_format}[/bold]")
    console.print(f"  kubeconfig: [bold]{config_obj.kubeconfig or 'None (use default)'}[/bold]")
    
    console.print("\n[bold cyan]Environment Variables:[/bold cyan]")
    env_vars = {
        'ARGO_NAMESPACE': os.getenv('ARGO_NAMESPACE'),
        'KUBE_CONTEXT': os.getenv('KUBE_CONTEXT'),
        'KUBECONFIG': os.getenv('KUBECONFIG'),
        'ARGOCD_CLI_OUTPUT_FORMAT': os.getenv('ARGOCD_CLI_OUTPUT_FORMAT'),
    }
    
    for key, value in env_vars.items():
        if value:
            console.print(f"  {key}: [bold]{value}[/bold]")
        else:
            console.print(f"  {key}: [dim]Not set[/dim]")
    
    console.print("\n[bold cyan]Available Commands:[/bold cyan]")
    console.print("• Modify configuration: [bold]argocd-cli config set KEY VALUE[/bold]")
    console.print("• Edit file directly: [bold]$EDITOR ~/.argocd-cli/config.yaml[/bold]\n")


@config.command("set")
@click.argument("key")
@click.argument("value")
def config_set(key: str, value: str):
    """Set a configuration value.
    
    Sets a configuration key to the specified value and saves to the
    configuration file.
    
    Examples:
    
      # Set default namespace
      argocd-cli config set namespace my-namespace
      
      # Set cluster context
      argocd-cli config set cluster_context prod-cluster
      
      # Set output format
      argocd-cli config set output_format json
      
      # Set kubeconfig path
      argocd-cli config set kubeconfig /path/to/kubeconfig
    """
    config_obj = get_config()
    
    # Validate key
    valid_keys = ['namespace', 'cluster_context', 'output_format', 'kubeconfig']
    if key not in valid_keys:
        console.print(f"\n[bold red]✗ Invalid configuration key:[/bold red] {key}\n")
        console.print(f"[bold cyan]Valid keys:[/bold cyan] {', '.join(valid_keys)}\n")
        raise click.ClickException(f"Invalid configuration key: {key}")
    
    # Validate value for specific keys
    if key == 'output_format' and value not in ['table', 'json', 'yaml']:
        console.print(f"\n[bold red]✗ Invalid output format:[/bold red] {value}\n")
        console.print("[bold cyan]Valid formats:[/bold cyan] table, json, yaml\n")
        raise click.ClickException(f"Invalid output format: {value}")
    
    try:
        # Set value
        config_obj.set(key, value)
        config_obj.save()
        
        console.print(f"\n[bold green]✓ Configuration updated[/bold green]\n")
        console.print(f"  {key}: [bold]{value}[/bold]")
        console.print(f"\n[dim]Configuration saved to: {config_obj.config_path}[/dim]\n")
        
    except Exception as e:
        console.print(f"\n[bold red]✗ Failed to update configuration[/bold red]\n")
        console.print(f"[red]{str(e)}[/red]\n")
        raise click.ClickException(f"Configuration update failed: {str(e)}")


@config.command("get")
@click.argument("key")
def config_get(key: str):
    """Get a configuration value.
    
    Retrieves and displays the value of a specific configuration key.
    
    Examples:
    
      # Get default namespace
      argocd-cli config get namespace
      
      # Get cluster context
      argocd-cli config get cluster_context
    """
    config_obj = get_config()
    
    # Validate key
    valid_keys = ['namespace', 'cluster_context', 'output_format', 'kubeconfig']
    if key not in valid_keys:
        console.print(f"\n[bold red]✗ Invalid configuration key:[/bold red] {key}\n")
        console.print(f"[bold cyan]Valid keys:[/bold cyan] {', '.join(valid_keys)}\n")
        raise click.ClickException(f"Invalid configuration key: {key}")
    
    value = config_obj.get(key)
    
    if value is None:
        console.print(f"\n{key}: [dim]Not set[/dim]\n")
    else:
        console.print(f"\n{key}: [bold]{value}[/bold]\n")


if __name__ == "__main__":
    cli()
