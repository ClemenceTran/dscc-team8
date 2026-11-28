
targetScope = 'resourceGroup'

@description('Storage account name')
param storageAccountName string

@description('Azure region')
param location string

resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' = {
  name: storageAccountName
  location: location
  kind: 'StorageV2'
  sku: {
    name: 'Standard_LRS'
  }
  properties: {
    supportsHttpsTrafficOnly: true
    minimumTlsVersion: 'TLS1_2'
    allowBlobPublicAccess: false
  }
}

resource blobService 'Microsoft.Storage/storageAccounts/blobServices@2023-05-01' = {
  parent: storage
  name: 'default'
  properties: {
    isVersioningEnabled: true
    deleteRetentionPolicy: {
      enabled: false
      allowPermanentDelete: false
    }
  }
}

var containerNames = [
  'input'
  'output'
  'rejected'
  'models'
]

resource containers 'Microsoft.Storage/storageAccounts/blobServices/containers@2023-05-01' = [for containerName in containerNames: {
  parent: blobService
  name: containerName
  properties: {
    publicAccess: 'None'
    defaultEncryptionScope: '$account-encryption-key'
    denyEncryptionScopeOverride: false
  }
}]

// Existing Queue service — do not modify its configuration
resource inferenceQueue 'Microsoft.Storage/storageAccounts/queueServices@2023-05-01' existing = {
  parent: storage
  name: 'default'
}

// Existing inference queue — preserve existing messages and settings
resource queue 'Microsoft.Storage/storageAccounts/queueServices/queues@2023-05-01' existing = {
  parent: inferenceQueue
  name: 'inference-requests'
}

output storageAccountId string = storage.id
output storageAccountName string = storage.name
output blobEndpoint string = storage.properties.primaryEndpoints.blob
output queueEndpoint string = storage.properties.primaryEndpoints.queue
output containerNames array = containerNames
output queueName string = queue.name
