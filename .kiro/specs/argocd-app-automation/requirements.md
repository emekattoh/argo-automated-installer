# Requirements Document

## Introduction

This feature automates the creation and management of ArgoCD Applications and ApplicationSets from Helm charts. Developers will provide a Helm chart reference, and the Python CLI tool will automatically generate and deploy the necessary ArgoCD resources to run the application in a Kubernetes cluster.

## Glossary

- **ArgoCD_CLI**: The Python command-line tool that automates ArgoCD operations
- **Application**: An ArgoCD resource that represents a single deployment of a Helm chart to a specific cluster and namespace
- **ApplicationSet**: An ArgoCD resource that generates multiple Applications from templates using generators
- **Helm_Chart**: A package format for Kubernetes applications that contains templates and configuration
- **Developer**: A user who wants to deploy applications using the ArgoCD_CLI
- **Git_Repository**: A version control repository containing Helm charts or application manifests
- **Sync_Policy**: Configuration that defines how ArgoCD synchronizes the desired state with the cluster
- **Destination_Cluster**: The Kubernetes cluster where the application will be deployed

## Requirements

### Requirement 1

**User Story:** As a Developer, I want to create an ArgoCD Application from a Helm chart with minimal input, so that I can quickly deploy my application without writing YAML manifests.

#### Acceptance Criteria

1. WHEN the Developer provides a Helm chart repository URL and chart name, THE ArgoCD_CLI SHALL create an ArgoCD Application resource
2. WHEN the Developer provides a Git repository URL containing a Helm chart, THE ArgoCD_CLI SHALL create an ArgoCD Application resource that references the chart path
3. THE ArgoCD_CLI SHALL prompt the Developer for required parameters including application name, destination namespace, and destination cluster
4. WHEN optional parameters are not provided, THE ArgoCD_CLI SHALL use sensible default values for sync policy and project settings
5. WHEN the Application resource is created successfully, THE ArgoCD_CLI SHALL display the application name and access URL

### Requirement 2

**User Story:** As a Developer, I want to create an ArgoCD ApplicationSet that deploys to multiple environments, so that I can manage multi-environment deployments from a single configuration.

#### Acceptance Criteria

1. WHEN the Developer provides a Helm chart reference and multiple target environments, THE ArgoCD_CLI SHALL create an ApplicationSet resource with appropriate generators
2. THE ArgoCD_CLI SHALL support list generators for explicitly defined environments
3. THE ArgoCD_CLI SHALL support Git directory generators for discovering applications from repository structure
4. WHEN environment-specific values are provided, THE ArgoCD_CLI SHALL configure the ApplicationSet template to use the correct values per environment
5. WHEN the ApplicationSet is created successfully, THE ArgoCD_CLI SHALL display the number of Applications that will be generated

### Requirement 3

**User Story:** As a Developer, I want to specify custom Helm values for my application, so that I can configure the deployment according to my requirements.

#### Acceptance Criteria

1. WHEN the Developer provides a values file path, THE ArgoCD_CLI SHALL configure the Application to use the specified values file
2. WHEN the Developer provides inline value overrides, THE ArgoCD_CLI SHALL configure the Application with the specified parameter values
3. THE ArgoCD_CLI SHALL validate that the values file exists and is valid YAML before creating the Application
4. WHEN multiple values sources are provided, THE ArgoCD_CLI SHALL configure the Application to merge values in the correct precedence order
5. THE ArgoCD_CLI SHALL support both local file paths and Git repository paths for values files

### Requirement 4

**User Story:** As a Developer, I want to configure sync policies for my application, so that I can control how ArgoCD manages the deployment lifecycle.

#### Acceptance Criteria

1. WHEN the Developer enables automated sync, THE ArgoCD_CLI SHALL configure the Application with automated sync policy enabled
2. WHEN the Developer enables self-healing, THE ArgoCD_CLI SHALL configure the Application to automatically correct drift from desired state
3. WHEN the Developer enables auto-pruning, THE ArgoCD_CLI SHALL configure the Application to remove resources that are no longer defined
4. THE ArgoCD_CLI SHALL provide command-line flags for each sync policy option with clear descriptions
5. WHEN no sync policy is specified, THE ArgoCD_CLI SHALL configure the Application with manual sync as the default

### Requirement 5

**User Story:** As a Developer, I want to list and view my deployed applications, so that I can monitor the status of my deployments.

#### Acceptance Criteria

1. WHEN the Developer requests a list of applications, THE ArgoCD_CLI SHALL display all Applications in the specified namespace with their sync status
2. WHEN the Developer requests details for a specific application, THE ArgoCD_CLI SHALL display the application configuration, health status, and sync status
3. THE ArgoCD_CLI SHALL display the source repository, target cluster, and namespace for each application
4. THE ArgoCD_CLI SHALL indicate whether each application is in sync, out of sync, or has errors
5. THE ArgoCD_CLI SHALL format the output in a readable table format with color-coded status indicators

### Requirement 6

**User Story:** As a Developer, I want to update an existing application configuration, so that I can modify deployment settings without recreating the application.

#### Acceptance Criteria

1. WHEN the Developer provides updated Helm values, THE ArgoCD_CLI SHALL update the Application resource with the new values
2. WHEN the Developer changes the target revision or branch, THE ArgoCD_CLI SHALL update the Application source configuration
3. WHEN the Developer modifies sync policies, THE ArgoCD_CLI SHALL update the Application sync policy configuration
4. THE ArgoCD_CLI SHALL validate that the application exists before attempting to update it
5. WHEN the update is successful, THE ArgoCD_CLI SHALL display a confirmation message with the updated configuration

### Requirement 7

**User Story:** As a Developer, I want to delete applications and applicationsets, so that I can clean up deployments that are no longer needed.

#### Acceptance Criteria

1. WHEN the Developer requests to delete an Application, THE ArgoCD_CLI SHALL prompt for confirmation before deletion
2. WHEN the Developer confirms deletion, THE ArgoCD_CLI SHALL remove the Application resource from ArgoCD
3. THE ArgoCD_CLI SHALL provide an option to cascade delete, removing both the Application resource and deployed Kubernetes resources
4. WHEN the Developer deletes an ApplicationSet, THE ArgoCD_CLI SHALL warn about the number of Applications that will be affected
5. WHEN deletion is successful, THE ArgoCD_CLI SHALL display a confirmation message

### Requirement 8

**User Story:** As a Developer, I want the CLI to validate my inputs before creating resources, so that I can catch configuration errors early.

#### Acceptance Criteria

1. WHEN the Developer provides a Git repository URL, THE ArgoCD_CLI SHALL verify that the repository is accessible
2. WHEN the Developer provides a Helm chart path, THE ArgoCD_CLI SHALL verify that the chart exists in the repository
3. WHEN the Developer provides a destination cluster, THE ArgoCD_CLI SHALL verify that the cluster is registered in ArgoCD
4. WHEN the Developer provides a namespace, THE ArgoCD_CLI SHALL verify that the namespace exists or offer to create it
5. IF validation fails, THEN THE ArgoCD_CLI SHALL display a clear error message explaining the issue and suggested resolution
