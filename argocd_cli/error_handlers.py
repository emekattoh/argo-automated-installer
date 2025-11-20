"""Error handling utilities for CLI commands."""

import click
from rich.console import Console
from functools import wraps

from argocd_cli.exceptions import (
    ArgoCDCLIError,
    ClusterAccessError,
    NamespaceError,
    ValidationError,
    WorkflowSubmissionError,
    WorkflowNotFoundError,
    TemplateError,
    HelmError,
    GitRepositoryError,
    KubernetesAPIError,
    WorkflowExecutionError,
    ConfigurationError,
    ResourceNotFoundError,
    PermissionError,
    TimeoutError
)

console = Console()


def handle_cli_errors(func):
    """Decorator to handle CLI errors with consistent formatting.
    
    This decorator catches all custom exceptions and formats them
    with error messages and troubleshooting guidance.
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except ArgoCDCLIError as e:
            # Handle all custom CLI errors
            console.print(f"\n[bold red]✗ Error[/bold red]\n")
            console.print(f"[red]{e.message}[/red]\n")
            
            # Display troubleshooting steps if available
            troubleshooting = e.get_troubleshooting_text()
            if troubleshooting:
                console.print(f"[bold yellow]{troubleshooting}[/bold yellow]\n")
            
            raise click.ClickException(e.message)
            
        except click.ClickException:
            # Re-raise Click exceptions (already formatted)
            raise
            
        except KeyboardInterrupt:
            console.print("\n\n[dim]Operation cancelled by user[/dim]\n")
            raise click.Abort()
            
        except Exception as e:
            # Handle unexpected errors
            console.print(f"\n[bold red]✗ Unexpected Error[/bold red]\n")
            console.print(f"[red]{str(e)}[/red]\n")
            console.print("[bold yellow]Troubleshooting:[/bold yellow]")
            console.print("• This is an unexpected error. Please report it if it persists.")
            console.print("• Check the error message above for details.")
            console.print("• Verify your environment and configuration.\n")
            raise click.ClickException(f"Unexpected error: {str(e)}")
    
    return wrapper


def format_error_message(error: Exception) -> str:
    """Format an error message for display.
    
    Args:
        error: The exception to format
        
    Returns:
        Formatted error message string
    """
    if isinstance(error, ArgoCDCLIError):
        return error.message
    elif isinstance(error, click.ClickException):
        return error.format_message()
    else:
        return str(error)


def print_error(message: str, troubleshooting: list = None):
    """Print an error message with optional troubleshooting steps.
    
    Args:
        message: Error message to display
        troubleshooting: Optional list of troubleshooting suggestions
    """
    console.print(f"\n[bold red]✗ Error[/bold red]\n")
    console.print(f"[red]{message}[/red]\n")
    
    if troubleshooting:
        console.print("[bold yellow]Troubleshooting:[/bold yellow]")
        for step in troubleshooting:
            console.print(f"• {step}")
        console.print()


def print_warning(message: str):
    """Print a warning message.
    
    Args:
        message: Warning message to display
    """
    console.print(f"[bold yellow]⚠ Warning:[/bold yellow] {message}")


def print_success(message: str):
    """Print a success message.
    
    Args:
        message: Success message to display
    """
    console.print(f"[bold green]✓ {message}[/bold green]")


def handle_validation_error(e: ValidationError, context: str = ""):
    """Handle validation errors with context-specific guidance.
    
    Args:
        e: The validation error
        context: Additional context about where the error occurred
    """
    message = e.message
    if context:
        message = f"{context}: {message}"
    
    print_error(message, e.troubleshooting)


def handle_kubernetes_error(e: KubernetesAPIError, operation: str = ""):
    """Handle Kubernetes API errors with operation-specific guidance.
    
    Args:
        e: The Kubernetes API error
        operation: Description of the operation that failed
    """
    message = e.message
    if operation:
        message = f"Failed to {operation}: {message}"
    
    print_error(message, e.troubleshooting)


def handle_workflow_error(e: Exception, workflow_name: str = ""):
    """Handle workflow-related errors.
    
    Args:
        e: The workflow error
        workflow_name: Name of the workflow involved
    """
    if isinstance(e, WorkflowNotFoundError):
        message = e.message
        if workflow_name and workflow_name not in message:
            message = f"Workflow '{workflow_name}' not found"
        print_error(message, e.troubleshooting)
    elif isinstance(e, WorkflowSubmissionError):
        print_error(e.message, e.troubleshooting)
    elif isinstance(e, WorkflowExecutionError):
        print_error(e.message, e.troubleshooting)
    else:
        print_error(f"Workflow error: {str(e)}")


def safe_execute(func, error_message: str = "Operation failed", **kwargs):
    """Safely execute a function with error handling.
    
    Args:
        func: Function to execute
        error_message: Error message to display if function fails
        **kwargs: Additional arguments to pass to the function
        
    Returns:
        Result of the function or None if it fails
    """
    try:
        return func(**kwargs)
    except ArgoCDCLIError as e:
        print_error(f"{error_message}: {e.message}", e.troubleshooting)
        return None
    except Exception as e:
        print_error(f"{error_message}: {str(e)}")
        return None
