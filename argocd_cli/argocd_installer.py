"""ArgoCD installation and setup functionality."""

import subprocess
import time
from typing import Optional, Tuple

from kubernetes import client, config
from kubernetes.client.rest import ApiException

from argocd_cli.exceptions import (
    ClusterAccessError,
    HelmError,
    NamespaceError,
    PermissionError as CLIPermissionError,
    KubernetesAPIError,
    TimeoutError as CLITimeoutError,
    handle_kubernetes_api_exception
)


class ArgoCDInstaller:
    """Handles installation and configuration of ArgoCD."""

    def __init__(self):
        """Initialize the installer with Kubernetes client.
        
        Raises:
            ClusterAccessError: If Kubernetes configuration cannot be loaded
        """
        try:
            config.load_kube_config()
        except config.ConfigException:
            try:
                config.load_incluster_config()
            except Exception as e:
                raise ClusterAccessError(f"Failed to load Kubernetes configuration: {str(e)}")
        except Exception as e:
            raise ClusterAccessError(f"Failed to initialize Kubernetes client: {str(e)}")
        
        try:
            self.core_v1 = client.CoreV1Api()
            self.apps_v1 = client.AppsV1Api()
        except Exception as e:
            raise ClusterAccessError(f"Failed to create Kubernetes API clients: {str(e)}")

    def validate_cluster_access(self) -> Tuple[bool, str]:
        """
        Validate that the cluster is accessible.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            self.core_v1.get_api_resources()
            return True, "Cluster is accessible"
        except ApiException as e:
            error = handle_kubernetes_api_exception(e, "access cluster")
            return False, f"Cannot access cluster: {error.message}"
        except Exception as e:
            return False, f"Cannot access cluster: {str(e)}"

    def check_helm_installed(self) -> Tuple[bool, str]:
        """
        Check if Helm is installed and accessible.
        
        Returns:
            Tuple of (success, message)
        """
        try:
            result = subprocess.run(
                ["helm", "version", "--short"],
                capture_output=True,
                text=True,
                timeout=10
            )
            if result.returncode == 0:
                return True, f"Helm is installed: {result.stdout.strip()}"
            
            error_msg = result.stderr.strip() if result.stderr else "Helm command failed"
            return False, f"Helm command failed: {error_msg}"
            
        except FileNotFoundError:
            return False, "Helm is not installed. Please install Helm from https://helm.sh/docs/intro/install/"
        except subprocess.TimeoutExpired:
            return False, "Helm command timed out after 10 seconds"
        except Exception as e:
            return False, f"Error checking Helm: {str(e)}"

    def install_argocd(
        self,
        namespace: str = "argocd",
        release_name: str = "argocd",
        use_helm: bool = True,
        version: Optional[str] = None
    ) -> Tuple[bool, str]:
        """
        Install ArgoCD using Helm or kubectl.
        
        Args:
            namespace: Kubernetes namespace for installation
            release_name: Helm release name (if using Helm)
            use_helm: Whether to use Helm (True) or kubectl manifests (False)
            version: Specific ArgoCD version to install
            
        Returns:
            Tuple of (success, message)
        """
        # Validate cluster access
        success, message = self.validate_cluster_access()
        if not success:
            return False, message

        # Create namespace if it doesn't exist
        try:
            self.core_v1.read_namespace(namespace)
        except ApiException as e:
            if e.status == 404:
                try:
                    ns = client.V1Namespace(
                        metadata=client.V1ObjectMeta(name=namespace)
                    )
                    self.core_v1.create_namespace(ns)
                except Exception as create_error:
                    return False, f"Failed to create namespace: {str(create_error)}"
            else:
                return False, f"Error checking namespace: {str(e)}"

        if use_helm:
            return self._install_with_helm(namespace, release_name, version)
        else:
            return self._install_with_kubectl(namespace, version)

    def _install_with_helm(
        self,
        namespace: str,
        release_name: str,
        version: Optional[str]
    ) -> Tuple[bool, str]:
        """Install ArgoCD using Helm."""
        # Check Helm installation
        success, message = self.check_helm_installed()
        if not success:
            return False, message

        try:
            # Add ArgoCD Helm repository
            subprocess.run(
                ["helm", "repo", "add", "argo", "https://argoproj.github.io/argo-helm"],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
            subprocess.run(
                ["helm", "repo", "update"],
                capture_output=True,
                text=True,
                timeout=30,
                check=True
            )
        except subprocess.CalledProcessError as e:
            return False, f"Failed to add ArgoCD Helm repository: {e.stderr}"
        except Exception as e:
            return False, f"Error adding Helm repository: {str(e)}"

        # Install ArgoCD
        try:
            helm_cmd = [
                "helm", "install", release_name, "argo/argo-cd",
                "--namespace", namespace,
                "--create-namespace",
                "--set", "server.service.type=LoadBalancer",
                "--wait",
                "--timeout", "5m"
            ]
            
            if version:
                helm_cmd.extend(["--version", version])
            
            result = subprocess.run(
                helm_cmd,
                capture_output=True,
                text=True,
                timeout=360
            )
            
            if result.returncode != 0:
                # Check if already installed
                if "already exists" in result.stderr:
                    return False, f"ArgoCD is already installed in namespace '{namespace}'"
                return False, f"Helm install failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Installation timed out. Check cluster resources and try again."
        except Exception as e:
            return False, f"Error during installation: {str(e)}"

        # Get admin password
        admin_password = self.get_admin_password(namespace)
        
        # Get UI access URL
        ui_url = self.get_ui_url(namespace, f"{release_name}-argocd-server")

        return True, f"""ArgoCD installed successfully in namespace '{namespace}'

Admin Credentials:
  Username: admin
  Password: {admin_password}

{ui_url}

Next Steps:
1. Access the ArgoCD UI using the URL above
2. Login with the admin credentials
3. Change the admin password: argocd account update-password
"""

    def _install_with_kubectl(
        self,
        namespace: str,
        version: Optional[str]
    ) -> Tuple[bool, str]:
        """Install ArgoCD using kubectl and manifests."""
        try:
            # Determine manifest URL
            if version:
                manifest_url = f"https://raw.githubusercontent.com/argoproj/argo-cd/{version}/manifests/install.yaml"
            else:
                manifest_url = "https://raw.githubusercontent.com/argoproj/argo-cd/stable/manifests/install.yaml"
            
            # Apply manifests
            result = subprocess.run(
                ["kubectl", "apply", "-n", namespace, "-f", manifest_url],
                capture_output=True,
                text=True,
                timeout=120
            )
            
            if result.returncode != 0:
                return False, f"kubectl apply failed: {result.stderr}"
            
            # Wait for deployments to be ready
            time.sleep(5)
            
            # Get admin password
            admin_password = self.get_admin_password(namespace)
            
            # Get UI access URL
            ui_url = self.get_ui_url(namespace, "argocd-server")

            return True, f"""ArgoCD installed successfully in namespace '{namespace}'

Admin Credentials:
  Username: admin
  Password: {admin_password}

{ui_url}

Next Steps:
1. Access the ArgoCD UI using the URL above
2. Login with the admin credentials
3. Change the admin password: argocd account update-password
"""
            
        except subprocess.TimeoutExpired:
            return False, "Installation timed out"
        except Exception as e:
            return False, f"Error during installation: {str(e)}"

    def get_admin_password(self, namespace: str) -> str:
        """
        Get the ArgoCD admin password from the secret.
        
        Args:
            namespace: Kubernetes namespace
            
        Returns:
            Admin password or error message
        """
        try:
            # Wait a bit for secret to be created
            time.sleep(2)
            
            # Try to get the initial admin password secret
            try:
                secret = self.core_v1.read_namespaced_secret(
                    "argocd-initial-admin-secret",
                    namespace
                )
                import base64
                password = base64.b64decode(secret.data.get("password", "")).decode("utf-8")
                return password
            except ApiException as e:
                if e.status == 404:
                    # Fallback: try to get from argocd-secret
                    try:
                        result = subprocess.run(
                            ["kubectl", "-n", namespace, "get", "secret", "argocd-initial-admin-secret",
                             "-o", "jsonpath={.data.password}"],
                            capture_output=True,
                            text=True,
                            timeout=10
                        )
                        if result.returncode == 0 and result.stdout:
                            import base64
                            return base64.b64decode(result.stdout).decode("utf-8")
                    except:
                        pass
                    
                    return "Run: kubectl -n argocd get secret argocd-initial-admin-secret -o jsonpath='{.data.password}' | base64 -d"
                raise
                
        except Exception as e:
            return f"Error retrieving password: {str(e)}"

    def get_ui_url(self, namespace: str, service_name: str) -> str:
        """
        Get the ArgoCD UI access URL.
        
        Args:
            namespace: Kubernetes namespace
            service_name: Service name
            
        Returns:
            UI access information
        """
        try:
            # Wait a bit for service to be ready
            time.sleep(2)
            
            service = self.core_v1.read_namespaced_service(service_name, namespace)
            
            if service.spec.type == "LoadBalancer":
                if service.status.load_balancer.ingress:
                    ingress = service.status.load_balancer.ingress[0]
                    host = ingress.hostname or ingress.ip
                    if host:
                        return f"UI Access: https://{host}"
                return f"UI Access: LoadBalancer pending... Run 'kubectl get svc -n {namespace} {service_name}' to check status"
            elif service.spec.type == "NodePort":
                node_port = None
                for port in service.spec.ports:
                    if port.name == "https" or port.port == 443:
                        node_port = port.node_port
                        break
                if node_port:
                    return f"UI Access: Use NodePort {node_port} or run 'kubectl port-forward -n {namespace} svc/{service_name} 8080:443'"
            
            return f"UI Access: Run 'kubectl port-forward -n {namespace} svc/{service_name} 8080:443' then visit https://localhost:8080"
                
        except Exception as e:
            return f"UI Access: Run 'kubectl port-forward -n {namespace} svc/{service_name} 8080:443' then visit https://localhost:8080"

    def check_argocd_installed(self, namespace: str = "argocd") -> Tuple[bool, str]:
        """
        Check if ArgoCD is already installed.
        
        Args:
            namespace: Kubernetes namespace to check
            
        Returns:
            Tuple of (is_installed, message)
        """
        try:
            # Check if namespace exists
            try:
                self.core_v1.read_namespace(namespace)
            except ApiException as e:
                if e.status == 404:
                    return False, f"Namespace '{namespace}' does not exist"
                raise
            
            # Check for ArgoCD server deployment
            try:
                deployments = self.apps_v1.list_namespaced_deployment(namespace)
                argocd_deployments = [d for d in deployments.items if "argocd-server" in d.metadata.name]
                
                if argocd_deployments:
                    deployment = argocd_deployments[0]
                    ready_replicas = deployment.status.ready_replicas or 0
                    replicas = deployment.spec.replicas or 0
                    
                    if ready_replicas == replicas and ready_replicas > 0:
                        return True, f"ArgoCD is installed and running in namespace '{namespace}'"
                    else:
                        return True, f"ArgoCD is installed but not fully ready ({ready_replicas}/{replicas} replicas)"
                
                return False, f"ArgoCD server deployment not found in namespace '{namespace}'"
                
            except ApiException as e:
                return False, f"Error checking deployments: {str(e)}"
                
        except Exception as e:
            return False, f"Error checking ArgoCD installation: {str(e)}"
