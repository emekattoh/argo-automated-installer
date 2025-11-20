from setuptools import setup, find_packages

setup(
    name="argocd-cli",
    version="0.1.0",
    packages=find_packages(),
    install_requires=[
        "kubernetes>=28.1.0",
        "PyYAML>=6.0",
        "click>=8.1.0",
        "rich>=13.7.0",
    ],
    entry_points={
        "console_scripts": [
            "argocd-cli=argocd_cli.cli:cli",
        ],
    },
    author="Your Name",
    description="ArgoCD CLI - Workflow-Based Application Automation",
    python_requires=">=3.8",
)
