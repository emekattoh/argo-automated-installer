# argocd_cli.py
import click
import subprocess
import yaml

class ArgocdCLI:
    def __init__(self, namespace, release_name):
        self.namespace = namespace
        self.release_name = release_name
    
    def run_cmd(self, cmd):
        result = subprocess.run(cmd, shell=True, capture_output=True, text=True)
        if result.returncode != 0:
            raise Exception(f"Command failed: {result.stderr}")
        return result.stdout

    def install(self, values_file, ha, version):
        print(f"Installing ArgoCD in namespace '{self.namespace}'...")
        
        # Add repo
        self.run_cmd("helm repo add argo https://argoproj.github.io/argo-helm")
        self.run_cmd("helm repo update")
        
        # Create namespace
        subprocess.run(f"kubectl create namespace {self.namespace}", shell=True)
        
        # Build install command
        cmd = f"helm install {self.release_name} argo/argo-cd --namespace {self.namespace}"
        
        if values_file:
            cmd += f" --values {values_file}"
        
        if version:
            cmd += f" --version {version}"
        
        if ha:
            # Add HA-specific values
            cmd += " --set redis-ha.enabled=true --set controller.replicas=3"
        
        self.run_cmd(cmd)
        print("✅ ArgoCD installed successfully!")

@click.group()
def cli():
    """ArgoCD Installation Automation Tool"""
    pass

@cli.command()
@click.option('--namespace', '-n', default='argocd', help='Kubernetes namespace')
@click.option('--release-name', '-r', default='argocd', help='Helm release name')
@click.option('--values', '-f', help='Values file path')
@click.option('--ha', is_flag=True, help='Install in HA mode')
@click.option('--version', '-v', help='Chart version')
def install(namespace, release_name, values, ha, version):
    """Install ArgoCD using Helm"""
    installer = ArgocdCLI(namespace, release_name)
    installer.install(values, ha, version)

@cli.command()
@click.option('--namespace', '-n', default='argocd')
def uninstall(namespace):
    """Uninstall ArgoCD"""
    click.confirm(f'Are you sure you want to uninstall ArgoCD from {namespace}?', abort=True)
    subprocess.run(f"helm uninstall argocd --namespace {namespace}", shell=True)
    subprocess.run(f"kubectl delete namespace {namespace}", shell=True)
    print("✅ ArgoCD uninstalled")

if __name__ == '__main__':
    cli()