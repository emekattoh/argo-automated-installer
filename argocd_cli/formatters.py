"""Output formatting and display utilities using rich library."""

from typing import List, Dict, Optional
from datetime import datetime
from io import StringIO
import re

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn
from rich.syntax import Syntax
from rich.text import Text
from rich import box

from argocd_cli.models import WorkflowStatus, WorkflowNode


class Formatters:
    """Output formatters for CLI display."""
    
    @staticmethod
    def _get_phase_color(phase: str) -> str:
        """Get color for workflow phase.
        
        Args:
            phase: Workflow phase (Running, Succeeded, Failed, Error, Pending)
            
        Returns:
            Color name for rich formatting
        """
        phase_colors = {
            "Running": "blue",
            "Succeeded": "green",
            "Failed": "red",
            "Error": "red",
            "Pending": "yellow",
            "Skipped": "dim",
            "Omitted": "dim"
        }
        return phase_colors.get(phase, "white")
    
    @staticmethod
    def _get_phase_icon(phase: str) -> str:
        """Get icon for workflow phase.
        
        Args:
            phase: Workflow phase
            
        Returns:
            Icon character
        """
        phase_icons = {
            "Running": "⏳",
            "Succeeded": "✓",
            "Failed": "✗",
            "Error": "✗",
            "Pending": "○",
            "Skipped": "⊘",
            "Omitted": "⊘"
        }
        return phase_icons.get(phase, "•")
    
    @staticmethod
    def _format_duration(started_at: datetime, finished_at: Optional[datetime] = None) -> str:
        """Format duration between start and finish times.
        
        Args:
            started_at: Start time
            finished_at: Finish time (None if still running)
            
        Returns:
            Formatted duration string
        """
        if finished_at:
            duration = finished_at - started_at
        else:
            # Make datetime.now() timezone-aware if started_at is timezone-aware
            now = datetime.now(started_at.tzinfo) if started_at.tzinfo else datetime.now()
            duration = now - started_at
        
        total_seconds = int(duration.total_seconds())
        hours = total_seconds // 3600
        minutes = (total_seconds % 3600) // 60
        seconds = total_seconds % 60
        
        if hours > 0:
            return f"{hours}h {minutes}m {seconds}s"
        elif minutes > 0:
            return f"{minutes}m {seconds}s"
        else:
            return f"{seconds}s"
    
    @staticmethod
    def format_workflow_list(workflows: List[Dict]) -> str:
        """Format a list of workflows as a table.
        
        Args:
            workflows: List of workflow objects (dict format from K8s API)
            
        Returns:
            Formatted table string
        """
        console = Console()
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        
        table = Table(
            title="Workflows",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        
        table.add_column("Name", style="white", no_wrap=True)
        table.add_column("Status", justify="center")
        table.add_column("Progress", justify="center")
        table.add_column("Started", style="dim")
        table.add_column("Duration", justify="right")
        
        for workflow in workflows:
            metadata = workflow.get("metadata", {})
            status = workflow.get("status", {})
            
            name = metadata.get("name", "N/A")
            phase = status.get("phase", "Unknown")
            progress = status.get("progress", "0/0")
            started_at_str = status.get("startedAt", "")
            finished_at_str = status.get("finishedAt", "")
            
            # Parse timestamps
            started_at = None
            finished_at = None
            if started_at_str:
                try:
                    started_at = datetime.fromisoformat(started_at_str.replace('Z', '+00:00'))
                except:
                    pass
            if finished_at_str:
                try:
                    finished_at = datetime.fromisoformat(finished_at_str.replace('Z', '+00:00'))
                except:
                    pass
            
            # Format status with color and icon
            color = Formatters._get_phase_color(phase)
            icon = Formatters._get_phase_icon(phase)
            status_text = Text(f"{icon} {phase}", style=color)
            
            # Format duration
            duration = "N/A"
            if started_at:
                duration = Formatters._format_duration(started_at, finished_at)
            
            # Format started time
            started_display = started_at.strftime("%Y-%m-%d %H:%M:%S") if started_at else "N/A"
            
            table.add_row(name, status_text, progress, started_display, duration)
        
        if not workflows:
            table.add_row("No workflows found", "", "", "", "")
        
        console.print(table)
        return buffer.getvalue()
    
    @staticmethod
    def format_workflow_status(status: WorkflowStatus) -> str:
        """Format workflow status with progress indicators.
        
        Args:
            status: Workflow status object
            
        Returns:
            Formatted status string
        """
        console = Console()
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        
        # Main status panel
        color = Formatters._get_phase_color(status.phase)
        icon = Formatters._get_phase_icon(status.phase)
        
        status_text = Text()
        status_text.append(f"{icon} ", style=color)
        status_text.append(f"Workflow: {status.name}\n", style="bold white")
        status_text.append(f"Namespace: {status.namespace}\n", style="dim")
        status_text.append(f"Status: ", style="dim")
        status_text.append(f"{status.phase}\n", style=f"bold {color}")
        status_text.append(f"Progress: {status.progress}\n", style="dim")
        status_text.append(f"Started: {status.started_at.strftime('%Y-%m-%d %H:%M:%S')}\n", style="dim")
        
        if status.finished_at:
            status_text.append(f"Finished: {status.finished_at.strftime('%Y-%m-%d %H:%M:%S')}\n", style="dim")
            duration = Formatters._format_duration(status.started_at, status.finished_at)
        else:
            duration = Formatters._format_duration(status.started_at)
        
        status_text.append(f"Duration: {duration}\n", style="dim")
        
        if status.message:
            status_text.append(f"Message: {status.message}\n", style="yellow")
        
        panel = Panel(status_text, title="Workflow Status", border_style=color)
        console.print(panel)
        
        # Workflow steps table
        if status.nodes:
            table = Table(
                title="Workflow Steps",
                box=box.ROUNDED,
                show_header=True,
                header_style="bold cyan"
            )
            
            table.add_column("Step", style="white")
            table.add_column("Type", style="dim")
            table.add_column("Status", justify="center")
            table.add_column("Duration", justify="right")
            table.add_column("Message", style="dim")
            
            for node in status.nodes:
                node_color = Formatters._get_phase_color(node.phase)
                node_icon = Formatters._get_phase_icon(node.phase)
                node_status = Text(f"{node_icon} {node.phase}", style=node_color)
                
                node_duration = Formatters._format_duration(node.started_at, node.finished_at)
                
                # Truncate long messages
                message = node.message[:50] + "..." if len(node.message) > 50 else node.message
                
                table.add_row(
                    node.display_name,
                    node.type,
                    node_status,
                    node_duration,
                    message
                )
            
            console.print(table)
        
        return buffer.getvalue()
    
    @staticmethod
    def format_workflow_logs(logs: str, highlight_errors: bool = True) -> str:
        """Format workflow logs with syntax highlighting.
        
        Args:
            logs: Raw log output
            highlight_errors: Whether to highlight errors and warnings
            
        Returns:
            Formatted log string with highlighting
        """
        console = Console()
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        
        if not logs:
            console.print("[dim]No logs available[/dim]")
            return buffer.getvalue()
        
        # Split logs into lines for processing
        lines = logs.split('\n')
        
        for line in lines:
            if not line.strip():
                console.print()
                continue
            
            # Highlight errors and warnings
            if highlight_errors:
                line_lower = line.lower()
                
                # Error patterns
                if any(pattern in line_lower for pattern in ['error', 'failed', 'exception', 'fatal']):
                    console.print(f"[bold red]{line}[/bold red]")
                    continue
                
                # Warning patterns
                elif any(pattern in line_lower for pattern in ['warning', 'warn', 'deprecated']):
                    console.print(f"[bold yellow]{line}[/bold yellow]")
                    continue
                
                # Success patterns
                elif any(pattern in line_lower for pattern in ['success', 'succeeded', 'completed', 'done']):
                    console.print(f"[bold green]{line}[/bold green]")
                    continue
                
                # Info patterns
                elif any(pattern in line_lower for pattern in ['info:', 'information:']):
                    console.print(f"[blue]{line}[/blue]")
                    continue
            
            # Check if line looks like JSON or YAML for syntax highlighting
            if line.strip().startswith('{') or line.strip().startswith('['):
                try:
                    syntax = Syntax(line, "json", theme="monokai", line_numbers=False)
                    console.print(syntax)
                    continue
                except:
                    pass
            
            # Check for timestamp patterns
            timestamp_pattern = r'^\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}'
            if re.match(timestamp_pattern, line):
                # Split timestamp from message
                parts = re.split(r'(\d{4}-\d{2}-\d{2}[T\s]\d{2}:\d{2}:\d{2}[^\s]*)', line, maxsplit=1)
                if len(parts) >= 3:
                    console.print(f"[dim]{parts[1]}[/dim] {parts[2]}")
                    continue
            
            # Default: print as-is
            console.print(line)
        
        return buffer.getvalue()
    
    @staticmethod
    def format_template_list(templates: List[Dict]) -> str:
        """Format a list of WorkflowTemplates as a table.
        
        Args:
            templates: List of WorkflowTemplate objects (dict format from K8s API)
            
        Returns:
            Formatted table string
        """
        console = Console()
        buffer = StringIO()
        console = Console(file=buffer, force_terminal=True)
        
        table = Table(
            title="Workflow Templates",
            box=box.ROUNDED,
            show_header=True,
            header_style="bold cyan"
        )
        
        table.add_column("Name", style="white", no_wrap=True)
        table.add_column("Description", style="dim")
        table.add_column("Parameters", justify="center")
        table.add_column("Created", style="dim")
        
        for template in templates:
            metadata = template.get("metadata", {})
            spec = template.get("spec", {})
            
            name = metadata.get("name", "N/A")
            
            # Get description from annotations or labels
            annotations = metadata.get("annotations", {})
            description = annotations.get("description", annotations.get("workflows.argoproj.io/description", ""))
            if not description:
                description = "No description"
            
            # Truncate long descriptions
            if len(description) > 60:
                description = description[:57] + "..."
            
            # Count parameters
            arguments = spec.get("arguments", {})
            parameters = arguments.get("parameters", [])
            param_count = len(parameters)
            
            # Get creation timestamp
            created_at_str = metadata.get("creationTimestamp", "")
            created_display = "N/A"
            if created_at_str:
                try:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    created_display = created_at.strftime("%Y-%m-%d %H:%M")
                except:
                    pass
            
            table.add_row(name, description, str(param_count), created_display)
        
        if not templates:
            table.add_row("No templates found", "", "", "")
        
        console.print(table)
        return buffer.getvalue()
    
    @staticmethod
    def print_success(message: str) -> None:
        """Print a success message.
        
        Args:
            message: Success message to display
        """
        console = Console()
        console.print(f"[bold green]✓[/bold green] {message}")
    
    @staticmethod
    def print_error(message: str) -> None:
        """Print an error message.
        
        Args:
            message: Error message to display
        """
        console = Console()
        console.print(f"[bold red]✗[/bold red] {message}")
    
    @staticmethod
    def print_warning(message: str) -> None:
        """Print a warning message.
        
        Args:
            message: Warning message to display
        """
        console = Console()
        console.print(f"[bold yellow]⚠[/bold yellow] {message}")
    
    @staticmethod
    def print_info(message: str) -> None:
        """Print an info message.
        
        Args:
            message: Info message to display
        """
        console = Console()
        console.print(f"[blue]ℹ[/blue] {message}")
