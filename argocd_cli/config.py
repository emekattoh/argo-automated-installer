"""Configuration management for ArgoCD CLI."""

import os
import yaml
from pathlib import Path
from typing import Dict, Any, Optional


class Config:
    """Manages CLI configuration from file and environment variables."""
    
    DEFAULT_CONFIG_PATH = Path.home() / ".argocd-cli" / "config.yaml"
    
    DEFAULT_CONFIG = {
        "namespace": "argo",
        "cluster_context": None,
        "output_format": "table",
        "kubeconfig": None,
    }
    
    def __init__(self, config_path: Optional[Path] = None):
        """Initialize configuration manager.
        
        Args:
            config_path: Path to configuration file. Defaults to ~/.argocd-cli/config.yaml
        """
        self.config_path = config_path or self.DEFAULT_CONFIG_PATH
        self.config = self._load_config()
    
    def _load_config(self) -> Dict[str, Any]:
        """Load configuration from file or create default config.
        
        Returns:
            Dictionary containing configuration values
        """
        # Start with default config
        config = self.DEFAULT_CONFIG.copy()
        
        # Load from file if it exists
        if self.config_path.exists():
            try:
                with open(self.config_path, 'r') as f:
                    file_config = yaml.safe_load(f) or {}
                    config.update(file_config)
            except Exception as e:
                # If config file is invalid, use defaults
                print(f"Warning: Failed to load config from {self.config_path}: {e}")
        
        # Override with environment variables
        if os.getenv('ARGO_NAMESPACE'):
            config['namespace'] = os.getenv('ARGO_NAMESPACE')
        
        if os.getenv('KUBE_CONTEXT'):
            config['cluster_context'] = os.getenv('KUBE_CONTEXT')
        
        if os.getenv('KUBECONFIG'):
            config['kubeconfig'] = os.getenv('KUBECONFIG')
        
        if os.getenv('ARGOCD_CLI_OUTPUT_FORMAT'):
            config['output_format'] = os.getenv('ARGOCD_CLI_OUTPUT_FORMAT')
        
        return config
    
    def get(self, key: str, default: Any = None) -> Any:
        """Get configuration value.
        
        Args:
            key: Configuration key
            default: Default value if key not found
            
        Returns:
            Configuration value or default
        """
        return self.config.get(key, default)
    
    def set(self, key: str, value: Any) -> None:
        """Set configuration value.
        
        Args:
            key: Configuration key
            value: Configuration value
        """
        self.config[key] = value
    
    def save(self) -> None:
        """Save configuration to file."""
        # Create config directory if it doesn't exist
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Write config to file
        with open(self.config_path, 'w') as f:
            yaml.dump(self.config, f, default_flow_style=False)
    
    def create_default_config(self) -> None:
        """Create default configuration file if it doesn't exist."""
        if not self.config_path.exists():
            self.config = self.DEFAULT_CONFIG.copy()
            self.save()
    
    @property
    def namespace(self) -> str:
        """Get default namespace."""
        return self.get('namespace', 'argo')
    
    @property
    def cluster_context(self) -> Optional[str]:
        """Get cluster context."""
        return self.get('cluster_context')
    
    @property
    def output_format(self) -> str:
        """Get output format."""
        return self.get('output_format', 'table')
    
    @property
    def kubeconfig(self) -> Optional[str]:
        """Get kubeconfig path."""
        return self.get('kubeconfig')


# Global config instance
_config_instance: Optional[Config] = None


def get_config(config_path: Optional[Path] = None) -> Config:
    """Get global configuration instance.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Config instance
    """
    global _config_instance
    
    if _config_instance is None:
        _config_instance = Config(config_path)
    
    return _config_instance


def load_config(config_path: Optional[Path] = None) -> Dict[str, Any]:
    """Load configuration and return as dictionary.
    
    Args:
        config_path: Optional path to configuration file
        
    Returns:
        Dictionary containing configuration values
    """
    config = get_config(config_path)
    return config.config.copy()
