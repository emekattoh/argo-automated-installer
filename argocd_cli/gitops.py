"""GitOps functionality for storing ArgoCD manifests in Git repositories."""

import os
import subprocess
import tempfile
from typing import Optional, Tuple
from pathlib import Path


class GitOpsManager:
    """Manages GitOps operations for ArgoCD manifests."""
    
    def __init__(
        self,
        repo_url: str,
        branch: str = "main",
        manifests_path: str = "argocd-manifests",
        git_username: Optional[str] = None,
        git_token: Optional[str] = None
    ):
        """Initialize GitOps manager.
        
        Args:
            repo_url: Git repository URL for storing manifests
            branch: Git branch to use (default: main)
            manifests_path: Path within repo for manifests (default: argocd-manifests)
            git_username: Git username for authentication
            git_token: Git token/password for authentication
        """
        self.repo_url = repo_url
        self.branch = branch
        self.manifests_path = manifests_path
        self.git_username = git_username or os.getenv("GIT_USERNAME")
        self.git_token = git_token or os.getenv("GIT_TOKEN")
        
    def _get_authenticated_url(self) -> str:
        """Get repository URL with authentication credentials.
        
        Returns:
            Authenticated Git URL
        """
        if self.git_username and self.git_token:
            # Convert https://github.com/user/repo.git to https://user:token@github.com/user/repo.git
            if self.repo_url.startswith("https://"):
                url_parts = self.repo_url.replace("https://", "").split("/", 1)
                return f"https://{self.git_username}:{self.git_token}@{url_parts[0]}/{url_parts[1]}"
        return self.repo_url
    
    def commit_manifest(
        self,
        manifest_content: str,
        manifest_name: str,
        commit_message: Optional[str] = None,
        create_pr: bool = False
    ) -> Tuple[bool, str]:
        """Commit ArgoCD manifest to Git repository.
        
        Args:
            manifest_content: YAML content of the manifest
            manifest_name: Name of the manifest file (e.g., my-app.yaml)
            commit_message: Custom commit message
            create_pr: Whether to create a pull request instead of direct commit
            
        Returns:
            Tuple of (success, message)
        """
        with tempfile.TemporaryDirectory() as tmpdir:
            try:
                repo_path = Path(tmpdir) / "repo"
                
                # Clone repository
                auth_url = self._get_authenticated_url()
                result = subprocess.run(
                    ["git", "clone", "--depth", "1", "--branch", self.branch, auth_url, str(repo_path)],
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    # Try to clone and create branch if it doesn't exist
                    result = subprocess.run(
                        ["git", "clone", "--depth", "1", auth_url, str(repo_path)],
                        capture_output=True,
                        text=True,
                        timeout=60
                    )
                    if result.returncode != 0:
                        return False, f"Failed to clone repository: {result.stderr}"
                    
                    # Create and checkout new branch
                    subprocess.run(
                        ["git", "checkout", "-b", self.branch],
                        cwd=repo_path,
                        capture_output=True,
                        text=True
                    )
                
                # Create manifests directory if it doesn't exist
                manifests_dir = repo_path / self.manifests_path
                manifests_dir.mkdir(parents=True, exist_ok=True)
                
                # Write manifest file
                manifest_file = manifests_dir / manifest_name
                manifest_file.write_text(manifest_content)
                
                # Configure git user if not set
                subprocess.run(
                    ["git", "config", "user.email", "argocd-cli@automated.local"],
                    cwd=repo_path,
                    capture_output=True
                )
                subprocess.run(
                    ["git", "config", "user.name", "ArgoCD CLI"],
                    cwd=repo_path,
                    capture_output=True
                )
                
                # Add and commit
                subprocess.run(
                    ["git", "add", str(manifest_file.relative_to(repo_path))],
                    cwd=repo_path,
                    check=True
                )
                
                if not commit_message:
                    commit_message = f"Add/Update ArgoCD manifest: {manifest_name}"
                
                result = subprocess.run(
                    ["git", "commit", "-m", commit_message],
                    cwd=repo_path,
                    capture_output=True,
                    text=True
                )
                
                if result.returncode != 0 and "nothing to commit" in result.stdout:
                    return True, f"Manifest {manifest_name} already up to date in Git"
                
                # Push to remote
                if create_pr:
                    # Create a feature branch for PR
                    pr_branch = f"argocd-manifest-{manifest_name.replace('.yaml', '')}"
                    subprocess.run(
                        ["git", "checkout", "-b", pr_branch],
                        cwd=repo_path,
                        capture_output=True
                    )
                    push_branch = pr_branch
                else:
                    push_branch = self.branch
                
                result = subprocess.run(
                    ["git", "push", "origin", push_branch],
                    cwd=repo_path,
                    capture_output=True,
                    text=True,
                    timeout=60
                )
                
                if result.returncode != 0:
                    return False, f"Failed to push to repository: {result.stderr}"
                
                success_msg = f"Successfully committed {manifest_name} to {self.repo_url}"
                if create_pr:
                    success_msg += f"\nBranch '{pr_branch}' created. Create PR manually on GitHub."
                
                return True, success_msg
                
            except subprocess.TimeoutExpired:
                return False, "Git operation timed out"
            except Exception as e:
                return False, f"Error during Git operation: {str(e)}"
    
    def save_manifest_locally(
        self,
        manifest_content: str,
        manifest_name: str,
        local_path: str = "./argocd-manifests"
    ) -> Tuple[bool, str]:
        """Save manifest to local filesystem.
        
        Args:
            manifest_content: YAML content of the manifest
            manifest_name: Name of the manifest file
            local_path: Local directory path
            
        Returns:
            Tuple of (success, message)
        """
        try:
            output_dir = Path(local_path)
            output_dir.mkdir(parents=True, exist_ok=True)
            
            manifest_file = output_dir / manifest_name
            manifest_file.write_text(manifest_content)
            
            return True, f"Manifest saved to {manifest_file.absolute()}"
        except Exception as e:
            return False, f"Failed to save manifest locally: {str(e)}"
