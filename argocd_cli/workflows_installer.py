"""Argo Workflows installation and setup functionality."""

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


class WorkflowsInstaller:
    """Handles installation and configuration of Argo Workflows."""

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
            self.rbac_v1 = client.RbacAuthorizationV1Api()
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

    def install_argo_workflows(
        self,
        namespace: str = "argo",
        release_name: str = "argo-workflows"
    ) -> Tuple[bool, str]:
        """
        Install Argo Workflows using Helm.
        
        Args:
            namespace: Kubernetes namespace for installation
            release_name: Helm release name
            
        Returns:
            Tuple of (success, message)
        """
        # Validate cluster access
        success, message = self.validate_cluster_access()
        if not success:
            return False, message

        # Check Helm installation
        success, message = self.check_helm_installed()
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

        # Add Argo Helm repository
        try:
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
            return False, f"Failed to add Argo Helm repository: {e.stderr}"
        except Exception as e:
            return False, f"Error adding Helm repository: {str(e)}"

        # Install Argo Workflows
        try:
            result = subprocess.run(
                [
                    "helm", "install", release_name, "argo/argo-workflows",
                    "--namespace", namespace,
                    "--create-namespace",
                    "--set", "server.serviceType=LoadBalancer",
                    "--wait",
                    "--timeout", "5m"
                ],
                capture_output=True,
                text=True,
                timeout=360
            )
            
            if result.returncode != 0:
                # Check if already installed
                if "already exists" in result.stderr:
                    return False, f"Argo Workflows is already installed in namespace '{namespace}'"
                return False, f"Helm install failed: {result.stderr}"
                
        except subprocess.TimeoutExpired:
            return False, "Installation timed out. Check cluster resources and try again."
        except Exception as e:
            return False, f"Error during installation: {str(e)}"

        # Configure RBAC
        rbac_success, rbac_message = self.configure_rbac(namespace)
        if not rbac_success:
            return False, f"Installation succeeded but RBAC configuration failed: {rbac_message}"

        # Get UI access URL
        ui_url = self.get_ui_url(namespace, release_name)

        return True, f"Argo Workflows installed successfully in namespace '{namespace}'\n{rbac_message}\n{ui_url}"

    def configure_rbac(self, namespace: str) -> Tuple[bool, str]:
        """
        Configure RBAC for Argo Workflows.
        
        Args:
            namespace: Kubernetes namespace
            
        Returns:
            Tuple of (success, message)
        """
        sa_name = "argo-workflow-sa"
        role_name = "argo-workflow-role"
        binding_name = "argo-workflow-binding"

        try:
            # Create ServiceAccount
            sa = client.V1ServiceAccount(
                metadata=client.V1ObjectMeta(
                    name=sa_name,
                    namespace=namespace
                )
            )
            try:
                self.core_v1.create_namespaced_service_account(namespace, sa)
            except ApiException as e:
                if e.status != 409:  # Ignore if already exists
                    raise

            # Create ClusterRole
            cluster_role = client.V1ClusterRole(
                metadata=client.V1ObjectMeta(name=role_name),
                rules=[
                    client.V1PolicyRule(
                        api_groups=["argoproj.io"],
                        resources=["applications", "applicationsets"],
                        verbs=["create", "update", "delete", "get", "list", "patch"]
                    ),
                    client.V1PolicyRule(
                        api_groups=["argoproj.io"],
                        resources=["workflowtaskresults"],
                        verbs=["create", "get", "list", "patch"]
                    ),
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=["namespaces", "secrets", "configmaps"],
                        verbs=["create", "update", "delete", "get", "list", "patch"]
                    ),
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=["pods", "pods/log"],
                        verbs=["get", "list", "watch"]
                    ),
                    client.V1PolicyRule(
                        api_groups=[""],
                        resources=["serviceaccounts"],
                        verbs=["get", "list"]
                    )
                ]
            )
            try:
                self.rbac_v1.create_cluster_role(cluster_role)
            except ApiException as e:
                if e.status != 409:  # Ignore if already exists
                    raise

            # Create ClusterRoleBinding
            cluster_role_binding = client.V1ClusterRoleBinding(
                metadata=client.V1ObjectMeta(name=binding_name),
                role_ref=client.V1RoleRef(
                    api_group="rbac.authorization.k8s.io",
                    kind="ClusterRole",
                    name=role_name
                ),
                subjects=[
                    client.RbacV1Subject(
                        kind="ServiceAccount",
                        name=sa_name,
                        namespace=namespace
                    )
                ]
            )
            try:
                self.rbac_v1.create_cluster_role_binding(cluster_role_binding)
            except ApiException as e:
                if e.status != 409:  # Ignore if already exists
                    raise

            return True, f"RBAC configured: ServiceAccount '{sa_name}', ClusterRole '{role_name}'"

        except Exception as e:
            return False, f"RBAC configuration error: {str(e)}"

    def get_ui_url(self, namespace: str, release_name: str) -> str:
        """
        Get the Argo Workflows UI access URL.
        
        Args:
            namespace: Kubernetes namespace
            release_name: Helm release name
            
        Returns:
            UI access information
        """
        service_name = f"{release_name}-argo-workflows-server"
        
        try:
            # Wait a bit for service to be ready
            time.sleep(2)
            
            service = self.core_v1.read_namespaced_service(service_name, namespace)
            
            if service.spec.type == "LoadBalancer":
                if service.status.load_balancer.ingress:
                    ingress = service.status.load_balancer.ingress[0]
                    host = ingress.hostname or ingress.ip
                    if host:
                        return f"UI Access: http://{host}:2746"
                return f"UI Access: LoadBalancer pending... Run 'kubectl get svc -n {namespace} {service_name}' to check status"
            elif service.spec.type == "NodePort":
                node_port = service.spec.ports[0].node_port
                return f"UI Access: Use NodePort {node_port} or run 'kubectl port-forward -n {namespace} svc/{service_name} 2746:2746'"
            else:
                return f"UI Access: Run 'kubectl port-forward -n {namespace} svc/{service_name} 2746:2746' then visit http://localhost:2746"
                
        except Exception as e:
            return f"UI Access: Run 'kubectl port-forward -n {namespace} svc/{service_name} 2746:2746' then visit http://localhost:2746"
