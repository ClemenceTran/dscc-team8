
targetScope = 'resourceGroup'

@description('Cosmos DB account name')
param cosmosAccountName string

// Existing Cosmos DB account — preserve its current configuration
resource cosmos 'Microsoft.DocumentDB/databaseAccounts@2024-05-15' existing = {
  name: cosmosAccountName
}

// SQL database
resource database 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases@2024-05-15' = {
  parent: cosmos
  name: 'pipeline'
  properties: {
    resource: {
      id: 'pipeline'
    }
  }
}

// Shared database throughput: 400 RU/s
resource databaseThroughput 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/throughputSettings@2024-05-15' = {
  parent: database
  name: 'default'
  properties: {
    resource: {
      throughput: 400
    }
  }
}

// Inference results container
resource container 'Microsoft.DocumentDB/databaseAccounts/sqlDatabases/containers@2024-05-15' = {
  parent: database
  name: 'inferences'
  properties: {
    resource: {
      id: 'inferences'
      partitionKey: {
        paths: [
          '/fileName'
        ]
        kind: 'Hash'
      }
      conflictResolutionPolicy: {
        mode: 'LastWriterWins'
        conflictResolutionPath: '/_ts'
      }
      indexingPolicy: {
        indexingMode: 'consistent'
        automatic: true
        includedPaths: [
          {
            path: '/*'
          }
        ]
        excludedPaths: [
          {
            path: '/"_etag"/?'
          }
        ]
      }
    }
  }
}

output cosmosAccountId string = cosmos.id
output cosmosAccountName string = cosmos.name
output databaseName string = database.name
output containerName string = container.name
