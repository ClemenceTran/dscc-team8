
targetScope = 'resourceGroup'

@description('GitHub deployment identity names')
param githubIdentityName string = 'github-deploy-clem'
param secondaryGithubIdentityName string = 'id-github-clem'

@description('GitHub repository name')
param repositoryName string = 'ClemenceTran/dscc-team8'

var githubIssuer = 'https://token.actions.githubusercontent.com'
var githubAudience = [
  'api://AzureADTokenExchange'
]

resource githubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: githubIdentityName
  location: resourceGroup().location
}

resource secondaryGithubIdentity 'Microsoft.ManagedIdentity/userAssignedIdentities@2023-01-31' = {
  name: secondaryGithubIdentityName
  location: resourceGroup().location
}

// First credential for the primary deployment identity
resource githubMain 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubIdentity
  name: 'github-main'
  properties: {
    issuer: githubIssuer
    subject: 'repo:${repositoryName}:ref:refs/heads/main'
    audiences: githubAudience
  }
}

// Wait for github-main
resource githubProduction 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubIdentity
  name: 'github-production'
  properties: {
    issuer: githubIssuer
    subject: 'repo:${repositoryName}:environment:production'
    audiences: githubAudience
  }
  dependsOn: [
    githubMain
  ]
}

// Wait for github-production
resource githubProductionV2 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: githubIdentity
  name: 'github-production-v2'
  properties: {
    issuer: githubIssuer
    subject: 'repo:ClemenceTran@244707856/dscc-team8@1471586160:environment:production'
    audiences: githubAudience
  }
  dependsOn: [
    githubProduction
  ]
}

// OIDC credential for the secondary identity
resource githubMainSecondary 'Microsoft.ManagedIdentity/userAssignedIdentities/federatedIdentityCredentials@2023-01-31' = {
  parent: secondaryGithubIdentity
  name: 'github-main-id'
  properties: {
    issuer: githubIssuer
    subject: 'repo:ClemenceTran@244707856/dscc-team8@1470176501:environment:production'
    audiences: githubAudience
  }
}

// Preserve existing Contributor role assignments
resource primaryContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '894e6d8c-7b71-4fbd-917b-bdab6567ab2c'
  properties: {
    principalId: '88988394-bd9f-484f-8f97-4b114b3c1ee5'
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b24988ac-6180-42a0-ab88-20f7382dd24c'
    )
  }
}

resource secondaryContributor 'Microsoft.Authorization/roleAssignments@2022-04-01' = {
  name: '68896566-b945-482c-9103-6c8a125abf41'
  properties: {
    principalId: '73a38e03-c128-4149-924f-3d71a66c232c'
    principalType: 'ServicePrincipal'
    roleDefinitionId: subscriptionResourceId(
      'Microsoft.Authorization/roleDefinitions',
      'b24988ac-6180-42a0-ab88-20f7382dd24c'
    )
  }
}

output githubIdentityClientId string = githubIdentity.properties.clientId
output secondaryGithubIdentityClientId string = secondaryGithubIdentity.properties.clientId
