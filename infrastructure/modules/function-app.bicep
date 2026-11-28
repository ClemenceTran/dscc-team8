
targetScope = 'resourceGroup'

@description('Function App name')
param functionAppName string

// Existing Function App: preserve its runtime configuration,
// application settings, deployment storage and CORS.
resource functionApp 'Microsoft.Web/sites@2024-04-01' existing = {
  name: functionAppName
}

// Existing Storage account
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: 'stclempipe'
}

// Existing Cosmos DB account
resource cosmosAccount 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: 'cosmos-clem'
}

// Existing Function App system-assigned identity principal ID
var functionPrincipalId = '49dd6971-08b6-4a69-836d-3a16a766b6cd'

// Storage Blob Data Owner
resource blobDataOwner 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '933d5df9-ade2-4f29-bea8-5c2ab5fd1aed'
  scope: storageAccount
  properties: {
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b7e6dc6d-f1e8-4753-8033-0f276bb0955b'
    )
  }
}

// Storage Queue Data Contributor
resource queueDataContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: 'a7a2912c-5af2-4639-83c2-1aaee3f770e5'
  scope: storageAccount
  properties: {
    principalId: functionPrincipalId
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      '974c5e8b-45b9-4653-ba55-5f855dd0fb88'
    )
  }
}

// Cosmos DB Built-in Data Contributor
resource cosmosDataContributor 'Microsoft.DocumentDB/databaseAccounts/sqlRoleAssignments@2024-05-15' = {
  parent: cosmosAccount
  name: 'd9510528-aef9-4fd5-bf0a-7c59673f8448'
  properties: {
    principalId: functionPrincipalId
    roleDefinitionId: '${cosmosAccount.id}/sqlRoleDefinitions/00000000-0000-0000-0000-000000000002'
    scope: cosmosAccount.id
  }
}

output functionAppId string = functionApp.id
output functionPrincipalId string = functionPrincipalId
output functionDefaultHostName string = functionApp.properties.defaultHostName
