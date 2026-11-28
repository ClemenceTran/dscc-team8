
targetScope = 'resourceGroup'

@description('Container Apps environment name')
param environmentName string

@description('API Container App name')
param apiContainerAppName string

// Existing Container Apps environment.
// Preserve its current Log Analytics configuration.
resource containerEnvironment 'Microsoft.App/managedEnvironments@2024-03-01' existing = {
  name: environmentName
}

// Existing API Container App.
// Preserve its image, ingress, probes and secrets.
resource apiContainerApp 'Microsoft.App/containerApps@2024-03-01' existing = {
  name: apiContainerAppName
}

output containerEnvironmentId string = containerEnvironment.id
output apiContainerAppId string = apiContainerApp.id
output apiContainerAppFqdn string = apiContainerApp.properties.configuration.ingress.fqdn
