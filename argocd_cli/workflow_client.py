"""Kubernetes client wrapper for Argo Workflows API interactions."""

from typing import List, Dict, Optional
from dataclasses import dataclass
from datetime import datetime
from kubernetes import client, config
from kubernetes.client.rest import ApiException
import time

from argocd_cli.exceptions import (
    ClusterAccessError,
    WorkflowSubmissionError,
    WorkflowNotFoundError,
    WorkflowExecutionError,
    KubernetesAPIError,
    ResourceNotFoundError,
    TimeoutError as CLITimeoutError,
    handle_kubernetes_api_exception
)


@dataclass
class WorkflowStatus:
    """Represents the status of an Argo Workflow."""
    name: str
    namespace: str
    phase: str
    started_at: datetime
    finished_at: Optional[datetime]
    progress: str
    message: str
    nodes: List['WorkflowNode']


@dataclass
class WorkflowNode:
    """Represents a node in a workflow execution."""
    name: str
    display_name: str
    type: str
    phase: str
    message: str
    started_at: datetime
    finished_at: Optional[datetime]


class WorkflowClient:
    """Handles interaction with Argo Workflows API."""
    
    # Argo Workflows API constants
    GROUP = "argoproj.io"
    VERSION = "v1alpha1"
    WORKFLOW_PLURAL = "workflows"
    WORKFLOW_TEMPLATE_PLURAL = "workflowtemplates"
    
    def __init__(self, namespace: str = "argo"):
        """Initialize the workflow client.
        
        Args:
            namespace: Kubernetes namespace for workflows
            
        Raises:
            ClusterAccessError: If Kubernetes configuration cannot be loaded
        """
        self.namespace = namespace
        
        # Load Kubernetes configuration
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
        
        # Initialize Kubernetes API clients
        try:
            self.custom_api = client.CustomObjectsApi()
            self.core_api = client.CoreV1Api()
        except Exception as e:
            raise ClusterAccessError(f"Failed to create Kubernetes API clients: {str(e)}")
    
    def submit_workflow(self, template_name: str, parameters: Dict[str, str]) -> str:
        """Submit a workflow from a template.
        
        Args:
            template_name: Name of the WorkflowTemplate to use
            parameters: Parameters to pass to the workflow
            
        Returns:
            Name of the created workflow
            
        Raises:
            WorkflowSubmissionError: If workflow submission fails
            ResourceNotFoundError: If template doesn't exist
        """
        # Build workflow submission object
        workflow_body = {
            "apiVersion": f"{self.GROUP}/{self.VERSION}",
            "kind": "Workflow",
            "metadata": {
                "generateName": f"{template_name}-",
                "namespace": self.namespace
            },
            "spec": {
                "workflowTemplateRef": {
                    "name": template_name
                },
                "arguments": {
                    "parameters": [
                        {"name": key, "value": value}
                        for key, value in parameters.items()
                    ]
                }
            }
        }
        
        try:
            # Submit workflow to Kubernetes
            response = self.custom_api.create_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=self.namespace,
                plural=self.WORKFLOW_PLURAL,
                body=workflow_body
            )
            
            return response["metadata"]["name"]
        except ApiException as e:
            if e.status == 404:
                raise ResourceNotFoundError("WorkflowTemplate", template_name, self.namespace)
            elif e.status == 422:
                raise WorkflowSubmissionError(
                    f"Invalid workflow specification: {e.reason}",
                    template_name
                )
            error = handle_kubernetes_api_exception(e, "submit workflow", "Workflow")
            raise WorkflowSubmissionError(f"Failed to submit workflow: {error.message}", template_name)
        except Exception as e:
            raise WorkflowSubmissionError(f"Unexpected error submitting workflow: {str(e)}", template_name)
    
    def get_workflow_status(self, workflow_name: str) -> WorkflowStatus:
        """Get the status of a workflow.
        
        Args:
            workflow_name: Name of the workflow
            
        Returns:
            WorkflowStatus object with current status
            
        Raises:
            WorkflowNotFoundError: If workflow doesn't exist
            KubernetesAPIError: If workflow retrieval fails
        """
        try:
            # Get workflow from Kubernetes
            workflow = self.custom_api.get_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=self.namespace,
                plural=self.WORKFLOW_PLURAL,
                name=workflow_name
            )
            
            # Extract status information
            status = workflow.get("status", {})
            metadata = workflow.get("metadata", {})
            
            # Parse timestamps
            started_at = None
            if status.get("startedAt"):
                try:
                    started_at = datetime.fromisoformat(status["startedAt"].replace("Z", "+00:00"))
                except (ValueError, AttributeError) as e:
                    # Log warning but continue - timestamp parsing is not critical
                    pass
            
            finished_at = None
            if status.get("finishedAt"):
                try:
                    finished_at = datetime.fromisoformat(status["finishedAt"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass
            
            # Parse nodes
            nodes = []
            for node_id, node_data in status.get("nodes", {}).items():
                node_started_at = None
                if node_data.get("startedAt"):
                    try:
                        node_started_at = datetime.fromisoformat(node_data["startedAt"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass
                
                node_finished_at = None
                if node_data.get("finishedAt"):
                    try:
                        node_finished_at = datetime.fromisoformat(node_data["finishedAt"].replace("Z", "+00:00"))
                    except (ValueError, AttributeError):
                        pass
                
                nodes.append(WorkflowNode(
                    name=node_data.get("name", node_id),
                    display_name=node_data.get("displayName", node_data.get("name", node_id)),
                    type=node_data.get("type", "Unknown"),
                    phase=node_data.get("phase", "Unknown"),
                    message=node_data.get("message", ""),
                    started_at=node_started_at,
                    finished_at=node_finished_at
                ))
            
            return WorkflowStatus(
                name=metadata.get("name", workflow_name),
                namespace=metadata.get("namespace", self.namespace),
                phase=status.get("phase", "Unknown"),
                started_at=started_at,
                finished_at=finished_at,
                progress=status.get("progress", "0/0"),
                message=status.get("message", ""),
                nodes=nodes
            )
        except ApiException as e:
            if e.status == 404:
                raise WorkflowNotFoundError(workflow_name, self.namespace)
            error = handle_kubernetes_api_exception(e, "get workflow status", "Workflow")
            raise KubernetesAPIError(f"Failed to get workflow status: {error.message}", "Workflow", "get")
        except Exception as e:
            raise KubernetesAPIError(f"Unexpected error getting workflow status: {str(e)}", "Workflow", "get")
    
    def list_workflows(self, namespace: Optional[str] = None, labels: Optional[Dict[str, str]] = None) -> List[Dict]:
        """List workflows in a namespace.
        
        Args:
            namespace: Namespace to list workflows from (defaults to client namespace)
            labels: Optional label selectors for filtering
            
        Returns:
            List of workflow objects
            
        Raises:
            KubernetesAPIError: If workflow listing fails
        """
        target_namespace = namespace or self.namespace
        
        # Build label selector string
        label_selector = None
        if labels:
            label_selector = ",".join([f"{k}={v}" for k, v in labels.items()])
        
        try:
            # List workflows from Kubernetes
            response = self.custom_api.list_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=target_namespace,
                plural=self.WORKFLOW_PLURAL,
                label_selector=label_selector
            )
            
            return response.get("items", [])
        except ApiException as e:
            error = handle_kubernetes_api_exception(e, "list workflows", "Workflow")
            raise KubernetesAPIError(f"Failed to list workflows: {error.message}", "Workflow", "list")
        except Exception as e:
            raise KubernetesAPIError(f"Unexpected error listing workflows: {str(e)}", "Workflow", "list")
    
    def delete_workflow(self, workflow_name: str, delete_pods: bool = True) -> bool:
        """Delete a workflow.
        
        Args:
            workflow_name: Name of the workflow to delete
            delete_pods: Whether to delete associated pods (default: True)
            
        Returns:
            True if deletion was successful
            
        Raises:
            WorkflowNotFoundError: If workflow doesn't exist
            KubernetesAPIError: If workflow deletion fails
        """
        try:
            # Delete workflow from Kubernetes
            # Setting propagationPolicy to 'Background' will delete associated pods
            body = client.V1DeleteOptions(
                propagation_policy='Background' if delete_pods else 'Orphan'
            )
            
            self.custom_api.delete_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=self.namespace,
                plural=self.WORKFLOW_PLURAL,
                name=workflow_name,
                body=body
            )
            
            return True
        except ApiException as e:
            if e.status == 404:
                raise WorkflowNotFoundError(workflow_name, self.namespace)
            error = handle_kubernetes_api_exception(e, "delete workflow", "Workflow")
            raise KubernetesAPIError(f"Failed to delete workflow: {error.message}", "Workflow", "delete")
        except Exception as e:
            raise KubernetesAPIError(f"Unexpected error deleting workflow: {str(e)}", "Workflow", "delete")
    
    def delete_workflows_by_labels(self, labels: Dict[str, str], delete_pods: bool = True) -> int:
        """Delete workflows matching label selectors.
        
        Args:
            labels: Label selectors for filtering workflows to delete
            delete_pods: Whether to delete associated pods (default: True)
            
        Returns:
            Number of workflows deleted
            
        Raises:
            ApiException: If workflow deletion fails
        """
        try:
            # List workflows matching labels
            workflows = self.list_workflows(labels=labels)
            
            deleted_count = 0
            for workflow in workflows:
                workflow_name = workflow.get("metadata", {}).get("name")
                if workflow_name:
                    try:
                        self.delete_workflow(workflow_name, delete_pods=delete_pods)
                        deleted_count += 1
                    except Exception:
                        # Continue deleting other workflows even if one fails
                        pass
            
            return deleted_count
        except ApiException as e:
            raise Exception(f"Failed to delete workflows by labels: {e.reason}") from e
    
    def list_workflow_templates(self, namespace: Optional[str] = None) -> List[Dict]:
        """List available workflow templates.
        
        Args:
            namespace: Namespace to list templates from (defaults to client namespace)
            
        Returns:
            List of WorkflowTemplate objects
            
        Raises:
            KubernetesAPIError: If template listing fails
        """
        target_namespace = namespace or self.namespace
        
        try:
            # List workflow templates from Kubernetes
            response = self.custom_api.list_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=target_namespace,
                plural=self.WORKFLOW_TEMPLATE_PLURAL
            )
            
            return response.get("items", [])
        except ApiException as e:
            error = handle_kubernetes_api_exception(e, "list workflow templates", "WorkflowTemplate")
            raise KubernetesAPIError(f"Failed to list workflow templates: {error.message}", "WorkflowTemplate", "list")
        except Exception as e:
            raise KubernetesAPIError(f"Unexpected error listing workflow templates: {str(e)}", "WorkflowTemplate", "list")
    
    def get_workflow_logs(self, workflow_name: str, step: Optional[str] = None) -> str:
        """Get logs from a workflow.
        
        Args:
            workflow_name: Name of the workflow
            step: Optional specific step to get logs from
            
        Returns:
            Log output as string
            
        Raises:
            WorkflowNotFoundError: If workflow doesn't exist
            KubernetesAPIError: If log retrieval fails
        """
        try:
            # Get workflow to find pod names
            workflow = self.custom_api.get_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=self.namespace,
                plural=self.WORKFLOW_PLURAL,
                name=workflow_name
            )
            
            status = workflow.get("status", {})
            nodes = status.get("nodes", {})
            
            logs = []
            
            # If specific step is requested, find that node
            if step:
                target_nodes = {
                    node_id: node_data 
                    for node_id, node_data in nodes.items() 
                    if node_data.get("displayName") == step or node_data.get("name") == step
                }
            else:
                # Get all pod nodes
                target_nodes = {
                    node_id: node_data 
                    for node_id, node_data in nodes.items() 
                    if node_data.get("type") == "Pod"
                }
            
            # Retrieve logs from each pod
            for node_id, node_data in target_nodes.items():
                pod_name = node_data.get("id", node_id)
                display_name = node_data.get("displayName", node_data.get("name", pod_name))
                
                try:
                    # Get pod logs
                    pod_logs = self.core_api.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        container="main"  # Argo Workflows uses 'main' container
                    )
                    
                    logs.append(f"=== Logs from step: {display_name} ===")
                    logs.append(pod_logs)
                    logs.append("")
                except ApiException as e:
                    if e.status == 404:
                        logs.append(f"=== Step {display_name}: Pod not found or not started yet ===")
                    else:
                        logs.append(f"=== Step {display_name}: Failed to retrieve logs: {e.reason} ===")
                    logs.append("")
            
            return "\n".join(logs) if logs else "No logs available"
        except ApiException as e:
            if e.status == 404:
                raise WorkflowNotFoundError(workflow_name, self.namespace)
            error = handle_kubernetes_api_exception(e, "get workflow logs", "Workflow")
            raise KubernetesAPIError(f"Failed to get workflow logs: {error.message}", "Workflow", "get logs")
        except Exception as e:
            raise KubernetesAPIError(f"Unexpected error getting workflow logs: {str(e)}", "Workflow", "get logs")
    
    def stream_workflow_logs(self, workflow_name: str, step: Optional[str] = None, follow: bool = True):
        """Stream logs from a running workflow.
        
        Args:
            workflow_name: Name of the workflow
            step: Optional specific step to stream logs from
            follow: Whether to follow the log stream
            
        Yields:
            Log lines as they become available
            
        Raises:
            ApiException: If log streaming fails
        """
        try:
            # Get workflow to find pod names
            workflow = self.custom_api.get_namespaced_custom_object(
                group=self.GROUP,
                version=self.VERSION,
                namespace=self.namespace,
                plural=self.WORKFLOW_PLURAL,
                name=workflow_name
            )
            
            status = workflow.get("status", {})
            nodes = status.get("nodes", {})
            
            # Find target nodes
            if step:
                target_nodes = {
                    node_id: node_data 
                    for node_id, node_data in nodes.items() 
                    if node_data.get("displayName") == step or node_data.get("name") == step
                }
            else:
                target_nodes = {
                    node_id: node_data 
                    for node_id, node_data in nodes.items() 
                    if node_data.get("type") == "Pod" and node_data.get("phase") in ["Running", "Pending"]
                }
            
            # Stream logs from each pod
            for node_id, node_data in target_nodes.items():
                pod_name = node_data.get("id", node_id)
                display_name = node_data.get("displayName", node_data.get("name", pod_name))
                
                try:
                    yield f"=== Streaming logs from step: {display_name} ==="
                    
                    # Stream pod logs
                    log_stream = self.core_api.read_namespaced_pod_log(
                        name=pod_name,
                        namespace=self.namespace,
                        container="main",
                        follow=follow,
                        _preload_content=False
                    )
                    
                    for line in log_stream:
                        yield line.decode('utf-8').rstrip()
                    
                except ApiException as e:
                    if e.status == 404:
                        yield f"Step {display_name}: Pod not found or not started yet"
                    else:
                        yield f"Step {display_name}: Failed to stream logs: {e.reason}"
        except ApiException as e:
            raise Exception(f"Failed to stream workflow logs: {e.reason}") from e
