"""Generates WorkflowTemplate YAML definitions for Argo Workflows."""

import subprocess
import yaml
from typing import Dict, Any

from argocd_cli.exceptions import (
    TemplateError,
    ValidationError,
    KubernetesAPIError
)


class TemplateGenerator:
    """Generates WorkflowTemplate YAML definitions."""
    
    def __init__(self, namespace: str = "argo"):
        """Initialize the template generator.
        
        Args:
            namespace: Kubernetes namespace for templates
        """
        self.namespace = namespace
    
    def _validate_yaml(self, yaml_str: str) -> bool:
        """Validate YAML syntax.
        
        Args:
            yaml_str: YAML string to validate
            
        Returns:
            True if valid YAML
            
        Raises:
            ValidationError: If YAML is invalid
        """
        try:
            yaml.safe_load(yaml_str)
            return True
        except yaml.YAMLError as e:
            raise ValidationError(f"Invalid YAML syntax: {str(e)}", field="template_yaml")
    
    def generate_application_template(self) -> str:
        """Generate WorkflowTemplate for Application creation.
        
        Returns:
            YAML string of the WorkflowTemplate
        """
        template = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "WorkflowTemplate",
            "metadata": {
                "name": "create-argocd-application",
                "namespace": self.namespace
            },
            "spec": {
                "serviceAccountName": "argo-workflow-sa",
                "entrypoint": "create-application",
                "arguments": {
                    "parameters": [
                        {"name": "app_name"},
                        {"name": "namespace"},
                        {"name": "repo_url"},
                        {"name": "chart_path"},
                        {"name": "destination_cluster", "value": "https://kubernetes.default.svc"},
                        {"name": "destination_namespace"},
                        {"name": "values_file", "value": ""},
                        {"name": "sync_policy_automated", "value": "false"},
                        {"name": "sync_policy_self_heal", "value": "false"},
                        {"name": "sync_policy_prune", "value": "false"}
                    ]
                },
                "templates": [
                    {
                        "name": "create-application",
                        "steps": [
                            [{"name": "validate-inputs", "template": "validate-inputs"}],
                            [{"name": "create-namespace", "template": "create-namespace"}],
                            [{"name": "generate-manifest", "template": "generate-manifest"}],
                            [{"name": "apply-application", "template": "apply-application"}],
                            [{"name": "verify-creation", "template": "verify-creation"}]
                        ]
                    },
                    {
                        "name": "validate-inputs",
                        "script": {
                            "image": "alpine:3.18",
                            "command": ["sh"],
                            "source": """
if [ -z "{{workflow.parameters.app_name}}" ]; then
  echo "Error: app_name is required"
  exit 1
fi
if [ -z "{{workflow.parameters.namespace}}" ]; then
  echo "Error: namespace is required"
  exit 1
fi
if [ -z "{{workflow.parameters.repo_url}}" ]; then
  echo "Error: repo_url is required"
  exit 1
fi
if [ -z "{{workflow.parameters.chart_path}}" ]; then
  echo "Error: chart_path is required"
  exit 1
fi
if [ -z "{{workflow.parameters.destination_namespace}}" ]; then
  echo "Error: destination_namespace is required"
  exit 1
fi
echo "All required inputs validated successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "2"
                        }
                    },
                    {
                        "name": "create-namespace",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
kubectl create namespace {{workflow.parameters.namespace}} --dry-run=client -o yaml | kubectl apply -f -
echo "Namespace {{workflow.parameters.namespace}} ready"
"""
                        },
                        "retryStrategy": {
                            "limit": "2",
                            "retryPolicy": "OnError"
                        }
                    },
                    {
                        "name": "generate-manifest",
                        "script": {
                            "image": "alpine:3.18",
                            "command": ["sh"],
                            "source": """
# Detect if this is a Helm repository or Git repository
REPO_URL="{{workflow.parameters.repo_url}}"
CHART_PATH="{{workflow.parameters.chart_path}}"

# Check if it's a Helm repository
if echo "$REPO_URL" | grep -qE "(charts\\.|artifacthub\\.io|chartmuseum)"; then
  # Helm repository - use 'chart' field
  cat > /tmp/application.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{workflow.parameters.app_name}}
  namespace: {{workflow.parameters.namespace}}
spec:
  project: default
  source:
    repoURL: {{workflow.parameters.repo_url}}
    chart: {{workflow.parameters.chart_path}}
    targetRevision: "*"
    helm: {}
  destination:
    server: {{workflow.parameters.destination_cluster}}
    namespace: {{workflow.parameters.destination_namespace}}
  syncPolicy:
    automated:
      selfHeal: {{workflow.parameters.sync_policy_self_heal}}
      prune: {{workflow.parameters.sync_policy_prune}}
    syncOptions:
    - CreateNamespace=true
EOF
else
  # Git repository - use 'path' field
  cat > /tmp/application.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{workflow.parameters.app_name}}
  namespace: {{workflow.parameters.namespace}}
spec:
  project: default
  source:
    repoURL: {{workflow.parameters.repo_url}}
    path: {{workflow.parameters.chart_path}}
    targetRevision: HEAD
    helm: {}
  destination:
    server: {{workflow.parameters.destination_cluster}}
    namespace: {{workflow.parameters.destination_namespace}}
  syncPolicy:
    automated:
      selfHeal: {{workflow.parameters.sync_policy_self_heal}}
      prune: {{workflow.parameters.sync_policy_prune}}
    syncOptions:
    - CreateNamespace=true
EOF
fi

# Add valueFiles only if provided
if [ -n "{{workflow.parameters.values_file}}" ]; then
  sed -i 's/helm: {}/helm:\\n      valueFiles:\\n      - {{workflow.parameters.values_file}}/' /tmp/application.yaml
fi

if [ "{{workflow.parameters.sync_policy_automated}}" = "false" ]; then
  sed -i '/automated:/,/prune:/d' /tmp/application.yaml
fi

cat /tmp/application.yaml
"""
                        },
                        "retryStrategy": {
                            "limit": "2"
                        }
                    },
                    {
                        "name": "apply-application",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
# Detect if this is a Helm repository or Git repository
REPO_URL="{{workflow.parameters.repo_url}}"
CHART_PATH="{{workflow.parameters.chart_path}}"

# Check if it's a Helm repository (contains 'charts' in domain or common Helm repo patterns)
if echo "$REPO_URL" | grep -qE "(charts\\.|artifacthub\\.io|chartmuseum)"; then
  # Helm repository - use 'chart' field
  cat > /tmp/application.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{workflow.parameters.app_name}}
  namespace: {{workflow.parameters.namespace}}
spec:
  project: default
  source:
    repoURL: {{workflow.parameters.repo_url}}
    chart: {{workflow.parameters.chart_path}}
    targetRevision: "*"
    helm: {}
  destination:
    server: {{workflow.parameters.destination_cluster}}
    namespace: {{workflow.parameters.destination_namespace}}
  syncPolicy:
    automated:
      selfHeal: {{workflow.parameters.sync_policy_self_heal}}
      prune: {{workflow.parameters.sync_policy_prune}}
    syncOptions:
    - CreateNamespace=true
EOF
else
  # Git repository - use 'path' field
  cat > /tmp/application.yaml <<EOF
apiVersion: argoproj.io/v1alpha1
kind: Application
metadata:
  name: {{workflow.parameters.app_name}}
  namespace: {{workflow.parameters.namespace}}
spec:
  project: default
  source:
    repoURL: {{workflow.parameters.repo_url}}
    path: {{workflow.parameters.chart_path}}
    targetRevision: HEAD
    helm: {}
  destination:
    server: {{workflow.parameters.destination_cluster}}
    namespace: {{workflow.parameters.destination_namespace}}
  syncPolicy:
    automated:
      selfHeal: {{workflow.parameters.sync_policy_self_heal}}
      prune: {{workflow.parameters.sync_policy_prune}}
    syncOptions:
    - CreateNamespace=true
EOF
fi

# Add valueFiles only if provided
if [ -n "{{workflow.parameters.values_file}}" ]; then
  sed -i 's/helm: {}/helm:\\n      valueFiles:\\n      - {{workflow.parameters.values_file}}/' /tmp/application.yaml
fi

if [ "{{workflow.parameters.sync_policy_automated}}" = "false" ]; then
  sed -i '/automated:/,/prune:/d' /tmp/application.yaml
fi

kubectl apply -f /tmp/application.yaml
echo "Application {{workflow.parameters.app_name}} applied successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "3",
                            "retryPolicy": "OnError",
                            "backoff": {
                                "duration": "5s",
                                "factor": 2,
                                "maxDuration": "1m"
                            }
                        }
                    },
                    {
                        "name": "verify-creation",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
for i in 1 2 3 4 5; do
  if kubectl get application {{workflow.parameters.app_name}} -n {{workflow.parameters.namespace}} > /dev/null 2>&1; then
    echo "Application {{workflow.parameters.app_name}} verified successfully"
    exit 0
  fi
  echo "Waiting for application to be created... (attempt $i/5)"
  sleep 5
done
echo "Error: Application not found after verification"
exit 1
"""
                        },
                        "retryStrategy": {
                            "limit": "2"
                        }
                    }
                ]
            }
        }
        
        yaml_str = yaml.dump(template, default_flow_style=False, sort_keys=False)
        self._validate_yaml(yaml_str)
        return yaml_str

    def generate_applicationset_template(self) -> str:
        """Generate WorkflowTemplate for ApplicationSet creation.
        
        Returns:
            YAML string of the WorkflowTemplate
        """
        template = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "WorkflowTemplate",
            "metadata": {
                "name": "create-argocd-applicationset",
                "namespace": self.namespace
            },
            "spec": {
                "serviceAccountName": "argo-workflow-sa",
                "entrypoint": "create-applicationset",
                "arguments": {
                    "parameters": [
                        {"name": "appset_name"},
                        {"name": "repo_url"},
                        {"name": "chart_path"},
                        {"name": "generator_type", "value": "list"},
                        {"name": "environments"},  # JSON array of environments
                        {"name": "sync_policy_automated", "value": "false"},
                        {"name": "sync_policy_self_heal", "value": "false"},
                        {"name": "sync_policy_prune", "value": "false"}
                    ]
                },
                "templates": [
                    {
                        "name": "create-applicationset",
                        "steps": [
                            [{"name": "validate-inputs", "template": "validate-inputs"}],
                            [{"name": "validate-environments", "template": "validate-environments"}],
                            [{"name": "generate-manifest", "template": "generate-manifest"}],
                            [{"name": "apply-applicationset", "template": "apply-applicationset"}]
                        ]
                    },
                    {
                        "name": "validate-inputs",
                        "script": {
                            "image": "alpine:3.18",
                            "command": ["sh"],
                            "source": """
if [ -z "{{workflow.parameters.appset_name}}" ]; then
  echo "Error: appset_name is required"
  exit 1
fi
if [ -z "{{workflow.parameters.repo_url}}" ]; then
  echo "Error: repo_url is required"
  exit 1
fi
if [ -z "{{workflow.parameters.chart_path}}" ]; then
  echo "Error: chart_path is required"
  exit 1
fi
if [ -z "{{workflow.parameters.environments}}" ]; then
  echo "Error: environments is required"
  exit 1
fi
if [ "{{workflow.parameters.generator_type}}" != "list" ] && [ "{{workflow.parameters.generator_type}}" != "git" ]; then
  echo "Error: generator_type must be 'list' or 'git'"
  exit 1
fi
echo "All required inputs validated successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "2"
                        }
                    },
                    {
                        "name": "validate-environments",
                        "script": {
                            "image": "alpine:3.18",
                            "command": ["sh"],
                            "source": """
apk add --no-cache jq

echo "{{workflow.parameters.environments}}" | jq -e '.' > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Error: environments must be valid JSON"
  exit 1
fi

env_count=$(echo "{{workflow.parameters.environments}}" | jq 'length')
if [ "$env_count" -eq 0 ]; then
  echo "Error: at least one environment is required"
  exit 1
fi

echo "{{workflow.parameters.environments}}" | jq -c '.[]' | while read env; do
  name=$(echo "$env" | jq -r '.name')
  cluster=$(echo "$env" | jq -r '.cluster_url')
  namespace=$(echo "$env" | jq -r '.namespace')
  
  if [ -z "$name" ] || [ "$name" = "null" ]; then
    echo "Error: environment name is required"
    exit 1
  fi
  if [ -z "$cluster" ] || [ "$cluster" = "null" ]; then
    echo "Error: cluster_url is required for environment $name"
    exit 1
  fi
  if [ -z "$namespace" ] || [ "$namespace" = "null" ]; then
    echo "Error: namespace is required for environment $name"
    exit 1
  fi
  
  echo "Environment $name validated successfully"
done

echo "All environments validated successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "2"
                        }
                    },
                    {
                        "name": "generate-manifest",
                        "script": {
                            "image": "alpine:3.18",
                            "command": ["sh"],
                            "source": r"""
apk add --no-cache jq

cat > /tmp/applicationset.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: {{workflow.parameters.appset_name}}
  namespace: argocd
spec:
  generators:
  - list:
      elements: []
  template:
    metadata:
      name: '{{workflow.parameters.appset_name}}-{{name}}'
    spec:
      project: default
      source:
        repoURL: {{workflow.parameters.repo_url}}
        path: {{workflow.parameters.chart_path}}
        targetRevision: HEAD
        helm:
          valueFiles:
          - '{{values_file}}'
      destination:
        server: '{{cluster_url}}'
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          selfHeal: {{workflow.parameters.sync_policy_self_heal}}
          prune: {{workflow.parameters.sync_policy_prune}}
        syncOptions:
        - CreateNamespace=true
EOF

if [ "{{workflow.parameters.sync_policy_automated}}" = "false" ]; then
  sed -i '/automated:/,/prune:/d' /tmp/applicationset.yaml
fi

# Generate elements from environments JSON
elements=$(echo '{{workflow.parameters.environments}}' | jq -c '[.[] | {name: .name, cluster_url: .cluster_url, namespace: .namespace, values_file: (.values_file // "values.yaml")}]')

# Insert elements into YAML using a temporary file
temp_yaml=$(cat /tmp/applicationset.yaml)
echo "$temp_yaml" | sed "s/elements: \[\]/elements: $elements/" > /tmp/applicationset.yaml

cat /tmp/applicationset.yaml
"""
                        },
                        "retryStrategy": {
                            "limit": "2"
                        }
                    },
                    {
                        "name": "apply-applicationset",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": r"""
apk add --no-cache jq

cat > /tmp/applicationset.yaml <<'EOF'
apiVersion: argoproj.io/v1alpha1
kind: ApplicationSet
metadata:
  name: {{workflow.parameters.appset_name}}
  namespace: argocd
spec:
  generators:
  - list:
      elements: []
  template:
    metadata:
      name: '{{workflow.parameters.appset_name}}-{{name}}'
    spec:
      project: default
      source:
        repoURL: {{workflow.parameters.repo_url}}
        path: {{workflow.parameters.chart_path}}
        targetRevision: HEAD
        helm:
          valueFiles:
          - '{{values_file}}'
      destination:
        server: '{{cluster_url}}'
        namespace: '{{namespace}}'
      syncPolicy:
        automated:
          selfHeal: {{workflow.parameters.sync_policy_self_heal}}
          prune: {{workflow.parameters.sync_policy_prune}}
        syncOptions:
        - CreateNamespace=true
EOF

if [ "{{workflow.parameters.sync_policy_automated}}" = "false" ]; then
  sed -i '/automated:/,/prune:/d' /tmp/applicationset.yaml
fi

# Generate elements from environments JSON
elements=$(echo '{{workflow.parameters.environments}}' | jq -c '[.[] | {name: .name, cluster_url: .cluster_url, namespace: .namespace, values_file: (.values_file // "values.yaml")}]')

# Insert elements into YAML
temp_yaml=$(cat /tmp/applicationset.yaml)
echo "$temp_yaml" | sed "s/elements: \[\]/elements: $elements/" > /tmp/applicationset.yaml

kubectl apply -f /tmp/applicationset.yaml
echo "ApplicationSet {{workflow.parameters.appset_name}} applied successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "3",
                            "retryPolicy": "OnError",
                            "backoff": {
                                "duration": "5s",
                                "factor": 2,
                                "maxDuration": "1m"
                            }
                        }
                    }
                ]
            }
        }
        
        yaml_str = yaml.dump(template, default_flow_style=False, sort_keys=False)
        self._validate_yaml(yaml_str)
        return yaml_str

    def generate_infrastructure_template(self) -> str:
        """Generate WorkflowTemplate for infrastructure provisioning.
        
        Returns:
            YAML string of the WorkflowTemplate
        """
        template = {
            "apiVersion": "argoproj.io/v1alpha1",
            "kind": "WorkflowTemplate",
            "metadata": {
                "name": "provision-infrastructure",
                "namespace": self.namespace
            },
            "spec": {
                "serviceAccountName": "argo-workflow-sa",
                "entrypoint": "provision-infrastructure",
                "arguments": {
                    "parameters": [
                        {"name": "namespace"},
                        {"name": "secrets", "value": "[]"},  # JSON array of secrets
                        {"name": "configmaps", "value": "[]"},  # JSON array of configmaps
                        {"name": "custom_scripts", "value": ""}  # Optional custom scripts
                    ]
                },
                "templates": [
                    {
                        "name": "provision-infrastructure",
                        "steps": [
                            [{"name": "create-namespace", "template": "create-namespace"}],
                            [{"name": "create-secrets", "template": "create-secrets"}],
                            [{"name": "create-configmaps", "template": "create-configmaps"}],
                            [{"name": "execute-custom-scripts", "template": "execute-custom-scripts", "when": "{{workflow.parameters.custom_scripts}} != ''"}]
                        ]
                    },
                    {
                        "name": "create-namespace",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
if [ -z "{{workflow.parameters.namespace}}" ]; then
  echo "Error: namespace is required"
  exit 1
fi

kubectl create namespace {{workflow.parameters.namespace}} --dry-run=client -o yaml | kubectl apply -f -
echo "Namespace {{workflow.parameters.namespace}} created successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "2",
                            "retryPolicy": "OnError"
                        }
                    },
                    {
                        "name": "create-secrets",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
apk add --no-cache jq

secrets='{{workflow.parameters.secrets}}'

if [ "$secrets" = "[]" ] || [ -z "$secrets" ]; then
  echo "No secrets to create"
  exit 0
fi

echo "$secrets" | jq -e '.' > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Error: secrets must be valid JSON"
  exit 1
fi

echo "$secrets" | jq -c '.[]' | while read secret; do
  name=$(echo "$secret" | jq -r '.name')
  type=$(echo "$secret" | jq -r '.type // "Opaque"')
  data=$(echo "$secret" | jq -r '.data')
  
  if [ -z "$name" ] || [ "$name" = "null" ]; then
    echo "Error: secret name is required"
    exit 1
  fi
  
  echo "Creating secret: $name"
  
  # Build kubectl command
  cmd="kubectl create secret generic $name -n {{workflow.parameters.namespace}} --dry-run=client -o yaml"
  
  # Add data fields
  echo "$data" | jq -r 'to_entries[] | "--from-literal=\\(.key)=\\(.value)"' | while read arg; do
    cmd="$cmd $arg"
  done
  
  eval "$cmd" | kubectl apply -f -
  
  if [ $? -eq 0 ]; then
    echo "Secret $name created successfully"
  else
    echo "Error creating secret $name"
    exit 1
  fi
done

echo "All secrets created successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "2",
                            "retryPolicy": "OnError"
                        }
                    },
                    {
                        "name": "create-configmaps",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
apk add --no-cache jq

configmaps='{{workflow.parameters.configmaps}}'

if [ "$configmaps" = "[]" ] || [ -z "$configmaps" ]; then
  echo "No configmaps to create"
  exit 0
fi

echo "$configmaps" | jq -e '.' > /dev/null 2>&1
if [ $? -ne 0 ]; then
  echo "Error: configmaps must be valid JSON"
  exit 1
fi

echo "$configmaps" | jq -c '.[]' | while read cm; do
  name=$(echo "$cm" | jq -r '.name')
  data=$(echo "$cm" | jq -r '.data')
  
  if [ -z "$name" ] || [ "$name" = "null" ]; then
    echo "Error: configmap name is required"
    exit 1
  fi
  
  echo "Creating configmap: $name"
  
  # Build kubectl command
  cmd="kubectl create configmap $name -n {{workflow.parameters.namespace}} --dry-run=client -o yaml"
  
  # Add data fields
  echo "$data" | jq -r 'to_entries[] | "--from-literal=\\(.key)=\\(.value)"' | while read arg; do
    cmd="$cmd $arg"
  done
  
  eval "$cmd" | kubectl apply -f -
  
  if [ $? -eq 0 ]; then
    echo "ConfigMap $name created successfully"
  else
    echo "Error creating configmap $name"
    exit 1
  fi
done

echo "All configmaps created successfully"
"""
                        },
                        "retryStrategy": {
                            "limit": "2",
                            "retryPolicy": "OnError"
                        }
                    },
                    {
                        "name": "execute-custom-scripts",
                        "script": {
                            "image": "bitnami/kubectl:latest",
                            "command": ["sh"],
                            "source": """
if [ -z "{{workflow.parameters.custom_scripts}}" ]; then
  echo "No custom scripts to execute"
  exit 0
fi

echo "Executing custom scripts..."
echo "{{workflow.parameters.custom_scripts}}" > /tmp/custom_script.sh
chmod +x /tmp/custom_script.sh

/tmp/custom_script.sh

if [ $? -eq 0 ]; then
  echo "Custom scripts executed successfully"
else
  echo "Error executing custom scripts"
  exit 1
fi
"""
                        },
                        "retryStrategy": {
                            "limit": "2",
                            "retryPolicy": "OnError"
                        }
                    }
                ]
            }
        }
        
        yaml_str = yaml.dump(template, default_flow_style=False, sort_keys=False)
        self._validate_yaml(yaml_str)
        return yaml_str
    
    def apply_template(self, template_yaml: str) -> bool:
        """Apply a WorkflowTemplate to the cluster.
        
        Args:
            template_yaml: YAML string of the template
            
        Returns:
            True if application was successful
            
        Raises:
            ValidationError: If YAML is invalid
            TemplateError: If template application fails
            KubernetesAPIError: If kubectl command fails
        """
        # Validate YAML before applying
        try:
            self._validate_yaml(template_yaml)
        except ValidationError:
            raise
        
        try:
            # Apply the template using kubectl
            result = subprocess.run(
                ["kubectl", "apply", "-f", "-"],
                input=template_yaml.encode(),
                capture_output=True,
                check=True,
                timeout=30
            )
            
            print(result.stdout.decode())
            return True
            
        except subprocess.CalledProcessError as e:
            error_msg = e.stderr.decode() if e.stderr else str(e)
            
            # Parse common kubectl errors
            if "forbidden" in error_msg.lower():
                raise TemplateError(f"Permission denied: {error_msg}")
            elif "not found" in error_msg.lower():
                raise TemplateError(f"Resource not found: {error_msg}")
            elif "invalid" in error_msg.lower():
                raise ValidationError(f"Invalid template specification: {error_msg}")
            else:
                raise TemplateError(f"Failed to apply template: {error_msg}")
                
        except subprocess.TimeoutExpired:
            raise TemplateError("Template application timed out after 30 seconds")
            
        except FileNotFoundError:
            raise KubernetesAPIError(
                "kubectl command not found. Please ensure kubectl is installed and in PATH.",
                "WorkflowTemplate",
                "apply"
            )
        except Exception as e:
            raise TemplateError(f"Unexpected error applying template: {str(e)}")
