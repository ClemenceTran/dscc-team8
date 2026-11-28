
targetScope = 'resourceGroup'

@description('Azure region for the project resources')
param location string = resourceGroup().location

@description('Storage account name')
param storageAccountName string = 'stclempipe'

@description('Cosmos DB account name')
param cosmosAccountName string = 'cosmos-clem'

@description('Function App name')
param functionAppName string = 'func-clem'

@description('Log Analytics workspace name')
param logAnalyticsName string = 'log-clem'

@description('Application Insights name')
param appInsightsName string = 'appi-clem'

@description('Container Apps environment name')
param containerAppsEnvironmentName string = 'cae-clem'

@description('API Container App name')
param apiContainerAppName string = 'api-clem'

var projectName = 'dscc-team8'

// Storage infrastructure
module storageModule './modules/storage.bicep' = {
  name: 'storageDeployment'
  params: {
    storageAccountName: storageAccountName
    location: location
  }
}

// Cosmos DB infrastructure
module cosmosModule './modules/cosmos.bicep' = {
  name: 'cosmosDeployment'
  params: {
    cosmosAccountName: cosmosAccountName
  }
}

// GitHub Actions managed identities and OIDC credentials
module identityModule './modules/identity.bicep' = {
  name: 'identityDeployment'
}

// Function App infrastructure and permissions
module functionAppModule './modules/function-app.bicep' = {
  name: 'functionAppDeployment'
  params: {
    functionAppName: functionAppName
  }
}

// Event Grid: trigger dispatcher when a blob is uploaded
module eventGridModule './modules/event-grid.bicep' = {
  name: 'eventGridDeployment'
  params: {
    storageAccountName: storageAccountName
    functionAppName: functionAppName
  }
}

// Monitoring alerts and notification action group
module alertsModule './modules/alerts.bicep' = {
  name: 'alertsDeployment'
  params: {
    appInsightsName: appInsightsName
    actionGroupName: 'ag-api-clem'
    notificationEmail: 'ngocphuong.tran@edu.ece.fr'
  }
}

// Resource group cost budget
module budgetsModule './modules/budgets.bicep' = {
  name: 'budgetsDeployment'
  params: {
    actionGroupId: alertsModule.outputs.actionGroupId
    notificationEmail: 'ngocphuong.tran@edu.ece.fr'
  }
}

// Monitoring infrastructure
module monitoringModule './modules/monitoring.bicep' = {
  name: 'monitoringDeployment'
  params: {
    logAnalyticsName: logAnalyticsName
    appInsightsName: appInsightsName
    location: location
  }
}

// Container Apps infrastructure
module containerAppsModule './modules/container-apps.bicep' = {
  name: 'containerAppsDeployment'
  params: {
    environmentName: containerAppsEnvironmentName
    apiContainerAppName: apiContainerAppName
  }
}

// Deployment information
output deploymentRegion string = location
output project string = projectName

// Storage outputs
output storageAccountId string = storageModule.outputs.storageAccountId
output storageAccountName string = storageModule.outputs.storageAccountName
output blobEndpoint string = storageModule.outputs.blobEndpoint
output queueEndpoint string = storageModule.outputs.queueEndpoint

// Cosmos DB outputs
output cosmosAccountId string = cosmosModule.outputs.cosmosAccountId
output cosmosDatabaseName string = cosmosModule.outputs.databaseName
output cosmosContainerName string = cosmosModule.outputs.containerName

// GitHub identity outputs
output githubIdentityClientId string = identityModule.outputs.githubIdentityClientId
output secondaryGithubIdentityClientId string = identityModule.outputs.secondaryGithubIdentityClientId

// Function App outputs
output functionAppId string = functionAppModule.outputs.functionAppId
output functionPrincipalId string = functionAppModule.outputs.functionPrincipalId

// Monitoring outputs
output logAnalyticsId string = monitoringModule.outputs.logAnalyticsId
output appInsightsId string = monitoringModule.outputs.appInsightsId

// Container Apps outputs
output containerEnvironmentId string = containerAppsModule.outputs.containerEnvironmentId
output apiContainerAppId string = containerAppsModule.outputs.apiContainerAppId
output apiContainerAppFqdn string = containerAppsModule.outputs.apiContainerAppFqdn

// Event Grid outputs
output eventSubscriptionId string = eventGridModule.outputs.eventSubscriptionId
output eventSubscriptionName string = eventGridModule.outputs.eventSubscriptionName

// Alert outputs
output actionGroupId string = alertsModule.outputs.actionGroupId
output apiFailureAlertId string = alertsModule.outputs.alertId

output resourceGroupBudgetId string = budgetsModule.outputs.resourceGroupBudgetId
