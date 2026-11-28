
targetScope = 'resourceGroup'

@description('Application Insights resource name')
param appInsightsName string = 'appi-clem'

@description('Alert action group name')
param actionGroupName string = 'ag-api-clem'

@description('Notification email address')
param notificationEmail string = 'ngocphuong.tran@edu.ece.fr'

// Existing Application Insights
resource appInsights 'Microsoft.Insights/components@2020-02-02' existing = {
  name: appInsightsName
}

// Action group
resource actionGroup 'Microsoft.Insights/actionGroups@2023-01-01' = {
  name: actionGroupName
  location: 'global'
  properties: {
    groupShortName: 'apiclem'
    enabled: true
    emailReceivers: [
      {
        name: 'clem-email'
        emailAddress: notificationEmail
        useCommonAlertSchema: false
      }
    ]
  }
}

// Scheduled query alert
resource apiFailureAlert 'Microsoft.Insights/scheduledQueryRules@2023-12-01' = {
  name: 'alert-api-failures-clem'
  location: 'germanywestcentral'
  properties: {
    displayName: 'alert-api-failures-clem'
    description: 'Notify when the churn API records HTTP 4xx or 5xx prediction requests'
    checkWorkspaceAlertsStorageConfigured: false
    skipQueryValidation: false
    severity: 2
    enabled: true
    evaluationFrequency: 'PT5M'
    windowSize: 'PT5M'
    scopes: [
      appInsights.id
    ]
    criteria: {
      allOf: [
        {
          query: 'customMetrics | where timestamp > ago(5m) | where name == \'churn_predict_requests\' | extend status=tostring(customDimensions.status) | summarize FailedRequests=sumif(value, status startswith \'4\' or status startswith \'5\')'
          timeAggregation: 'Total'
          metricMeasureColumn: 'FailedRequests'
          operator: 'GreaterThan'
          threshold: 0
          failingPeriods: {
            numberOfEvaluationPeriods: 1
            minFailingPeriodsToAlert: 1
          }
        }
      ]
    }
    actions: {
      actionGroups: [
        actionGroup.id
      ]
    }
    autoMitigate: true
  }
}

output actionGroupId string = actionGroup.id
output alertId string = apiFailureAlert.id
