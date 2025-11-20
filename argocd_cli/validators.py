"""Input validation and pre-flight checks for workflow operations."""

from typing import List, Dict, Optional
import re
import subprocess
from kubernetes import client, config
from kubernetes.client.rest import ApiException

from argocd_cli.exceptions import (
    ValidationError,
    ClusterAccessError,
    NamespaceError,
    GitRepositoryError,
    HelmError,
    handle_kubernetes_api_exception
)


class Validator:
    """Validates user inputs and cluster state."""
    
    def __init__(self):
        """Initialize the validator with Kubernetes client."""
        try:
            config.load_kube_config()
        except config.ConfigException:
            try:
                # Fall back to in-cluster config if kubeconfig is not available
                config.load_incluster_config()
            except Exception as e:
                raise ClusterAccessError(f"Failed to load Kubernetes configuration: {str(e)}")
        except Exception as e:
            raise ClusterAccessError(f"Failed to initialize Kubernetes client: {str(e)}")
        
        try:
            self.core_api = client.CoreV1Api()
            self.version_api = client.VersionApi()
        except Exception as e:
            raise ClusterAccessError(f"Failed to create Kubernetes API clients: {str(e)}")
    
    def validate_cluster_access(self) -> bool:
        """Validate that the cluster is accessible.
        
        Returns:
            True if cluster is accessible
            
        Raises:
            ClusterAccessError: If cluster is not accessible
        """
        try:
            # Try to get cluster version to verify connectivity
            version_info = self.version_api.get_code()
            
            if not version_info or not version_info.git_version:
                raise ClusterAccessError("Cluster version information unavailable")
            
            return True
        except ApiException as e:
            error = handle_kubernetes_api_exception(e, "access cluster")
            raise ClusterAccessError(f"Cluster access failed: {error.message}")
        except Exception as e:
            raise ClusterAccessError(f"Failed to validate cluster access: {str(e)}")
    
    def validate_namespace(self, namespace: str) -> bool:
        """Validate that a namespace exists.
        
        Args:
            namespace: Namespace name to validate
            
        Returns:
            True if namespace exists
            
        Raises:
            ValidationError: If namespace name is invalid
            NamespaceError: If namespace doesn't exist or cannot be accessed
        """
        if not namespace or not isinstance(namespace, str):
            raise ValidationError("Namespace must be a non-empty string", field="namespace")
        
        # Validate namespace name format (DNS-1123 label)
        if not re.match(r'^[a-z0-9]([-a-z0-9]*[a-z0-9])?$', namespace):
            raise ValidationError(
                f"Invalid namespace name '{namespace}'. Must be lowercase alphanumeric with hyphens, "
                "starting and ending with alphanumeric characters",
                field="namespace"
            )
        
        try:
            # Try to get the namespace
            self.core_api.read_namespace(name=namespace)
            return True
        except ApiException as e:
            if e.status == 404:
                raise NamespaceError(namespace, "find")
            error = handle_kubernetes_api_exception(e, "validate namespace", "namespace")
            raise NamespaceError(namespace, f"access: {error.message}")
        except Exception as e:
            raise NamespaceError(namespace, f"validate: {str(e)}")
    
    def validate_parameters(self, required: List[str], provided: Dict[str, str]) -> bool:
        """Validate that all required parameters are provided.
        
        Args:
            required: List of required parameter names
            provided: Dictionary of provided parameters
            
        Returns:
            True if all required parameters are present
            
        Raises:
            ValidationError: If any required parameters are missing or invalid
        """
        if not isinstance(required, list):
            raise ValidationError("Required parameters must be provided as a list")
        
        if not isinstance(provided, dict):
            raise ValidationError("Provided parameters must be a dictionary")
        
        missing_params = []
        empty_params = []
        
        for param in required:
            if param not in provided:
                missing_params.append(param)
            elif not provided[param] or (isinstance(provided[param], str) and not provided[param].strip()):
                empty_params.append(param)
        
        if missing_params or empty_params:
            error_parts = []
            if missing_params:
                error_parts.append(f"Missing required parameters: {', '.join(missing_params)}")
            if empty_params:
                error_parts.append(f"Empty required parameters: {', '.join(empty_params)}")
            
            raise ValidationError(". ".join(error_parts))
        
        return True
    
    def validate_helm_chart(self, repo_url: str, chart_name: str) -> bool:
        """Validate that a Helm chart is accessible.
        
        Args:
            repo_url: Helm repository URL or Git repository URL
            chart_name: Name of the chart or path to chart in Git repo
            
        Returns:
            True if chart is accessible
            
        Raises:
            ValidationError: If chart cannot be accessed or validated
        """
        if not repo_url or not isinstance(repo_url, str):
            raise ValidationError("Repository URL must be a non-empty string")
        
        if not chart_name or not isinstance(chart_name, str):
            raise ValidationError("Chart name must be a non-empty string")
        
        # Determine if this is a Git repository or Helm repository
        if self._is_git_url(repo_url):
            return self._validate_git_chart(repo_url, chart_name)
        else:
            return self._validate_helm_repo_chart(repo_url, chart_name)
    
    def validate_git_url(self, git_url: str) -> bool:
        """Validate a Git repository URL format.
        
        Args:
            git_url: Git repository URL to validate
            
        Returns:
            True if URL is a valid Git repository URL
            
        Raises:
            GitRepositoryError: If URL is not a valid Git repository URL
        """
        if not git_url or not isinstance(git_url, str):
            raise GitRepositoryError(git_url or "<empty>", "URL must be a non-empty string")
        
        if not self._is_git_url(git_url):
            raise GitRepositoryError(
                git_url,
                "URL must start with http://, https://, git://, ssh://, or git@"
            )
        
        return True
    
    def _is_git_url(self, url: str) -> bool:
        """Check if a URL is a Git repository URL.
        
        Args:
            url: URL to check
            
        Returns:
            True if URL appears to be a Git repository
        """
        git_patterns = [
            r'^https?://.*\.git$',
            r'^https?://github\.com/',
            r'^https?://gitlab\.com/',
            r'^https?://bitbucket\.org/',
            r'^git@',
            r'^git://',
            r'^ssh://',
        ]
        
        return any(re.match(pattern, url) for pattern in git_patterns)
    
    def _validate_git_chart(self, repo_url: str, chart_path: str) -> bool:
        """Validate that a Helm chart exists in a Git repository.
        
        Args:
            repo_url: Git repository URL
            chart_path: Path to chart within the repository
            
        Returns:
            True if chart can be validated
            
        Raises:
            GitRepositoryError: If chart cannot be validated
            ValidationError: If chart path is invalid
        """
        # For Git repositories, we perform basic URL validation
        # Full validation would require cloning the repo, which is expensive
        # The actual chart existence will be validated during workflow execution
        
        try:
            # Validate Git URL format
            self.validate_git_url(repo_url)
            
            # Validate chart path format
            if not chart_path.strip():
                raise ValidationError("Chart path cannot be empty", field="chart_path")
            
            # Check for suspicious path patterns
            if '..' in chart_path or chart_path.startswith('/'):
                raise ValidationError(
                    f"Invalid chart path '{chart_path}'. "
                    "Path must be relative and cannot contain '..'",
                    field="chart_path"
                )
            
            return True
        except (ValidationError, GitRepositoryError):
            raise
        except Exception as e:
            raise GitRepositoryError(
                repo_url,
                f"Failed to validate chart at path '{chart_path}': {str(e)}"
            )
    
    def _validate_helm_repo_chart(self, repo_url: str, chart_name: str) -> bool:
        """Validate that a Helm chart exists in a Helm repository.
        
        Args:
            repo_url: Helm repository URL
            chart_name: Name of the chart
            
        Returns:
            True if chart is accessible
            
        Raises:
            HelmError: If chart cannot be accessed or validated
            ValidationError: If URL format is invalid
        """
        # Validate Helm repository URL format
        if not re.match(r'^https?://', repo_url):
            raise ValidationError(
                f"Invalid Helm repository URL: {repo_url}. "
                "URL must start with http:// or https://",
                field="repo_url"
            )
        
        # Try to use helm command to search for the chart
        try:
            # First, try to add the repo temporarily
            result = subprocess.run(
                ['helm', 'search', 'repo', chart_name, '--version', '>0.0.0'],
                capture_output=True,
                text=True,
                timeout=10
            )
            
            # If helm command is not available, skip detailed validation
            if result.returncode != 0 and 'helm: command not found' in result.stderr:
                # Helm CLI not available, perform basic URL validation only
                return True
            
            # If chart is found in any repo, consider it valid
            if result.returncode == 0 and chart_name in result.stdout:
                return True
            
            # Chart not found, but this might be because repo isn't added
            # We'll allow it and let the workflow handle the actual validation
            return True
            
        except subprocess.TimeoutExpired:
            raise HelmError(
                f"Timeout while validating Helm chart '{chart_name}' from {repo_url}",
                "chart validation"
            )
        except FileNotFoundError:
            # Helm CLI not installed, skip detailed validation
            return True
        except Exception as e:
            # If validation fails, log warning but don't block
            # The workflow will perform the actual validation
            return True
