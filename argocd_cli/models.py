"""Data models for workflow operations and ArgoCD configurations."""

from dataclasses import dataclass, field
from datetime import datetime
from typing import Dict, List, Optional


@dataclass
class WorkflowSubmission:
    """Request model for submitting a workflow to Argo Workflows."""
    template_name: str
    parameters: Dict[str, str]
    namespace: str = "argo"
    labels: Optional[Dict[str, str]] = None
    generate_name: Optional[str] = None


@dataclass
class WorkflowNode:
    """Represents a single node (step) in a workflow execution."""
    name: str
    display_name: str
    type: str  # Pod, Container, Steps, DAG
    phase: str  # Pending, Running, Succeeded, Failed, Error
    message: str
    started_at: datetime
    finished_at: Optional[datetime] = None


@dataclass
class WorkflowStatus:
    """Status information for a workflow execution."""
    name: str
    namespace: str
    phase: str  # Running, Succeeded, Failed, Error
    started_at: datetime
    finished_at: Optional[datetime]
    progress: str  # e.g., "2/5"
    message: str
    nodes: List[WorkflowNode] = field(default_factory=list)


@dataclass
class SyncPolicy:
    """ArgoCD sync policy configuration."""
    automated: bool = False
    self_heal: bool = False
    prune: bool = False


@dataclass
class ApplicationConfig:
    """Configuration for creating an ArgoCD Application."""
    name: str
    namespace: str
    repo_url: str
    chart_path: str
    destination_cluster: str
    destination_namespace: str
    values_file: Optional[str] = None
    helm_parameters: Optional[Dict[str, str]] = None
    sync_policy: Optional[SyncPolicy] = None


@dataclass
class Environment:
    """Environment configuration for ApplicationSet deployment."""
    name: str
    cluster_url: str
    namespace: str
    values_file: Optional[str] = None
    helm_parameters: Optional[Dict[str, str]] = None


@dataclass
class ApplicationSetConfig:
    """Configuration for creating an ArgoCD ApplicationSet."""
    name: str
    repo_url: str
    chart_path: str
    generator_type: str  # "list" or "git"
    environments: List[Environment]
    sync_policy: Optional[SyncPolicy] = None
