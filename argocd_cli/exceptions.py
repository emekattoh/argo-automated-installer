"""Custom exceptions for ArgoCD CLI with detailed error messages and troubleshooting guidance."""


class ArgoCDCLIError(Exception):
    """Base exception for all ArgoCD CLI errors."""
    
    def __init__(self, message: str, troubleshooting: list = None):
        """Initialize exception with message and optional troubleshooting steps.
        
        Args:
            message: Error message describing what went wrong
            troubleshooting: List of troubleshooting suggestions
        """
        self.message = message
        self.troubleshooting = troubleshooting or []
        super().__init__(self.message)
    
    def get_troubleshooting_text(self) -> str:
        """Get formatted troubleshooting text.
        
        Returns:
            Formatted string with troubleshooting steps
        """
        if not self.troubleshooting:
            return ""
        
        lines = ["Troubleshooting:"]
        for step in self.troubleshooting:
            lines.append(f"• {step}")
        return "\n".join(lines)


class ClusterAccessError(ArgoCDCLIError):
    """Raised when cluster access validation fails."""
    
    def __init__(self, message: str = "Cannot access Kubernetes cluster"):
        troubleshooting = [
            "Verify kubectl is configured: kubectl cluster-info",
            "Check kubeconfig file: kubectl config view",
            "Verify cluster connectivity: kubectl get nodes",
            "Ensure you have valid credentials: kubectl auth whoami",
            "Check if cluster is reachable: ping <cluster-endpoint>"
        ]
        super().__init__(message, troubleshooting)


class NamespaceError(ArgoCDCLIError):
    """Raised when namespace operations fail."""
    
    def __init__(self, namespace: str, operation: str = "access"):
        message = f"Failed to {operation} namespace '{namespace}'"
        troubleshooting = [
            f"Check if namespace exists: kubectl get namespace {namespace}",
            f"Create namespace: kubectl create namespace {namespace}",
            f"List all namespaces: kubectl get namespaces",
            f"Verify permissions: kubectl auth can-i get namespaces"
        ]
        super().__init__(message, troubleshooting)


class ValidationError(ArgoCDCLIError):
    """Raised when input validation fails."""
    
    def __init__(self, message: str, field: str = None):
        self.field = field
        troubleshooting = [
            "Review the command help: argocd-cli <command> --help",
            "Check parameter format and values",
            "Ensure all required parameters are provided"
        ]
        super().__init__(message, troubleshooting)


class WorkflowSubmissionError(ArgoCDCLIError):
    """Raised when workflow submission fails."""
    
    def __init__(self, message: str, template_name: str = None):
        self.template_name = template_name
        troubleshooting = [
            "Verify Argo Workflows is running: kubectl get pods -n argo",
            "Check WorkflowTemplate exists: argocd-cli workflows templates list",
            "Create templates if missing: argocd-cli workflows templates create",
            "Verify RBAC permissions: kubectl auth can-i create workflows.argoproj.io",
            "Check Argo Workflows controller logs: kubectl logs -n argo -l app=workflow-controller"
        ]
        if template_name:
            troubleshooting.insert(1, f"Verify template '{template_name}' exists: kubectl get workflowtemplate {template_name} -n argo")
        super().__init__(message, troubleshooting)


class WorkflowNotFoundError(ArgoCDCLIError):
    """Raised when a workflow cannot be found."""
    
    def __init__(self, workflow_name: str, namespace: str = "argo"):
        message = f"Workflow '{workflow_name}' not found in namespace '{namespace}'"
        troubleshooting = [
            f"List all workflows: argocd-cli workflows list -n {namespace}",
            f"Check workflow name spelling",
            f"Verify namespace: kubectl get workflows -n {namespace}",
            f"Check if workflow was deleted: kubectl get workflows --all-namespaces | grep {workflow_name}"
        ]
        super().__init__(message, troubleshooting)


class TemplateError(ArgoCDCLIError):
    """Raised when template operations fail."""
    
    def __init__(self, message: str, template_type: str = None):
        self.template_type = template_type
        troubleshooting = [
            "Verify Argo Workflows is installed: kubectl get crd workflowtemplates.argoproj.io",
            "Check cluster permissions: kubectl auth can-i create workflowtemplates.argoproj.io -n argo",
            "Review Argo Workflows logs: kubectl logs -n argo -l app=workflow-controller",
            "Validate YAML syntax if using custom templates"
        ]
        super().__init__(message, troubleshooting)


class HelmError(ArgoCDCLIError):
    """Raised when Helm operations fail."""
    
    def __init__(self, message: str, operation: str = "operation"):
        troubleshooting = [
            "Verify Helm is installed: helm version",
            "Check Helm repository: helm repo list",
            "Update Helm repositories: helm repo update",
            "Verify chart exists: helm search repo <chart-name>",
            "Check Helm permissions: helm list --all-namespaces"
        ]
        super().__init__(message, troubleshooting)


class GitRepositoryError(ArgoCDCLIError):
    """Raised when Git repository validation fails."""
    
    def __init__(self, repo_url: str, reason: str = ""):
        message = f"Invalid or inaccessible Git repository: {repo_url}"
        if reason:
            message += f" - {reason}"
        
        troubleshooting = [
            "Verify repository URL format (https://, git@, ssh://)",
            "Check repository accessibility: git ls-remote <repo-url>",
            "Ensure repository exists and is not private (or credentials are configured)",
            "Verify network connectivity to Git server",
            "Check if repository requires authentication"
        ]
        super().__init__(message, troubleshooting)


class KubernetesAPIError(ArgoCDCLIError):
    """Raised when Kubernetes API operations fail."""
    
    def __init__(self, message: str, resource_type: str = None, operation: str = None):
        self.resource_type = resource_type
        self.operation = operation
        
        troubleshooting = [
            "Verify cluster connectivity: kubectl cluster-info",
            "Check API server status: kubectl get --raw /healthz",
            "Verify RBAC permissions: kubectl auth can-i <verb> <resource>",
            "Check resource quotas: kubectl describe resourcequota -n <namespace>",
            "Review API server logs if you have access"
        ]
        
        if resource_type and operation:
            troubleshooting.insert(0, f"Verify permissions for {operation} on {resource_type}: kubectl auth can-i {operation} {resource_type}")
        
        super().__init__(message, troubleshooting)


class WorkflowExecutionError(ArgoCDCLIError):
    """Raised when workflow execution encounters errors."""
    
    def __init__(self, workflow_name: str, phase: str, message: str = ""):
        error_msg = f"Workflow '{workflow_name}' {phase.lower()}"
        if message:
            error_msg += f": {message}"
        
        troubleshooting = [
            f"Check workflow status: argocd-cli workflows status {workflow_name}",
            f"View workflow logs: argocd-cli workflows logs {workflow_name}",
            f"Inspect workflow details: kubectl describe workflow {workflow_name} -n argo",
            "Check pod events: kubectl get events -n argo --sort-by='.lastTimestamp'",
            "Verify workflow template parameters are correct",
            "Check resource availability in cluster: kubectl top nodes"
        ]
        super().__init__(error_msg, troubleshooting)


class ConfigurationError(ArgoCDCLIError):
    """Raised when configuration is invalid or missing."""
    
    def __init__(self, message: str, config_path: str = None):
        self.config_path = config_path
        troubleshooting = [
            "Check configuration file format (YAML)",
            "Verify configuration file permissions",
            "Review configuration documentation",
            "Use default configuration: rm ~/.argocd-cli/config.yaml"
        ]
        
        if config_path:
            troubleshooting.insert(0, f"Check configuration file: cat {config_path}")
        
        super().__init__(message, troubleshooting)


class ResourceNotFoundError(ArgoCDCLIError):
    """Raised when a Kubernetes resource cannot be found."""
    
    def __init__(self, resource_type: str, resource_name: str, namespace: str = None):
        message = f"{resource_type} '{resource_name}' not found"
        if namespace:
            message += f" in namespace '{namespace}'"
        
        troubleshooting = [
            f"List all {resource_type}s: kubectl get {resource_type}",
            f"Check resource name spelling",
            "Verify you're using the correct namespace",
            f"Search across all namespaces: kubectl get {resource_type} --all-namespaces"
        ]
        
        if namespace:
            troubleshooting.insert(0, f"List {resource_type}s in namespace: kubectl get {resource_type} -n {namespace}")
        
        super().__init__(message, troubleshooting)


class PermissionError(ArgoCDCLIError):
    """Raised when user lacks required permissions."""
    
    def __init__(self, operation: str, resource: str = None):
        message = f"Insufficient permissions to {operation}"
        if resource:
            message += f" {resource}"
        
        troubleshooting = [
            "Check your RBAC permissions: kubectl auth can-i --list",
            f"Verify specific permission: kubectl auth can-i {operation} {resource or '<resource>'}",
            "Contact your cluster administrator for required permissions",
            "Check if you're using the correct kubeconfig context",
            "Verify your service account has necessary roles"
        ]
        super().__init__(message, troubleshooting)


class TimeoutError(ArgoCDCLIError):
    """Raised when an operation times out."""
    
    def __init__(self, operation: str, timeout_seconds: int = None):
        message = f"Operation timed out: {operation}"
        if timeout_seconds:
            message += f" (timeout: {timeout_seconds}s)"
        
        troubleshooting = [
            "Check cluster responsiveness: kubectl get nodes",
            "Verify network connectivity",
            "Check if cluster is under heavy load: kubectl top nodes",
            "Increase timeout if operation is expected to take longer",
            "Check for stuck resources: kubectl get pods --all-namespaces | grep -v Running"
        ]
        super().__init__(message, troubleshooting)


def handle_kubernetes_api_exception(e: Exception, operation: str = "operation", resource_type: str = None) -> ArgoCDCLIError:
    """Convert Kubernetes API exceptions to custom exceptions with context.
    
    Args:
        e: The original exception
        operation: Description of the operation being performed
        resource_type: Type of Kubernetes resource involved
        
    Returns:
        Appropriate custom exception with troubleshooting guidance
    """
    from kubernetes.client.rest import ApiException
    
    if isinstance(e, ApiException):
        if e.status == 401:
            return PermissionError("authenticate", "cluster")
        elif e.status == 403:
            return PermissionError(operation, resource_type)
        elif e.status == 404:
            if resource_type:
                return ResourceNotFoundError(resource_type, "unknown")
            return KubernetesAPIError(f"Resource not found during {operation}", resource_type, operation)
        elif e.status == 409:
            return KubernetesAPIError(f"Resource conflict during {operation} - resource may already exist", resource_type, operation)
        elif e.status == 422:
            return ValidationError(f"Invalid resource specification: {e.reason}")
        elif e.status >= 500:
            return KubernetesAPIError(f"Kubernetes API server error during {operation}: {e.reason}", resource_type, operation)
        else:
            return KubernetesAPIError(f"API error during {operation}: {e.reason} (status: {e.status})", resource_type, operation)
    
    # For non-API exceptions, return generic error
    return KubernetesAPIError(f"Unexpected error during {operation}: {str(e)}", resource_type, operation)
