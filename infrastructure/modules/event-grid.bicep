
targetScope = 'resourceGroup'

@description('Storage account name')
param storageAccountName string

@description('Function App name')
param functionAppName string

// Existing Storage account
resource storage 'Microsoft.Storage/storageAccounts@2023-05-01' existing = {
  name: storageAccountName
}

// Existing Function App
resource functionApp 'Microsoft.Web/sites@2022-03-01' existing = {
  name: functionAppName
}

// Existing dispatcher Function
resource dispatcher 'Microsoft.Web/sites/functions@2022-03-01' existing = {
  parent: functionApp
  name: 'dispatcher'
}

// Blob-created event subscription
resource eventSubscription 'Microsoft.EventGrid/eventSubscriptions@2022-06-15' = {
  name: 'es-input-dispatcher-clem'
  scope: storage
  properties: {
    destination: {
      endpointType: 'AzureFunction'
      properties: {
        resourceId: dispatcher.id
        maxEventsPerBatch: 1
        preferredBatchSizeInKilobytes: 64
      }
    }
    eventDeliverySchema: 'EventGridSchema'
    filter: {
      includedEventTypes: [
        'Microsoft.Storage.BlobCreated'
      ]
      subjectBeginsWith: '/blobServices/default/containers/input/blobs/'
      subjectEndsWith: ''
    }
    retryPolicy: {
      eventTimeToLiveInMinutes: 1440
      maxDeliveryAttempts: 30
    }
  }
}

output eventSubscriptionId string = eventSubscription.id
output eventSubscriptionName string = eventSubscription.name
