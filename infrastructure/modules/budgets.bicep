
targetScope = 'resourceGroup'

@description('Action group resource ID')
param actionGroupId string

@description('Notification email')
param notificationEmail string = 'ngocphuong.tran@edu.ece.fr'

// Resource group monthly budget
resource resourceGroupBudget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'budget-dscc-clem'
  properties: {
    category: 'Cost'
    amount: 25
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-11-01T00:00:00Z'
      endDate: '2028-10-31T00:00:00Z'
    }
    notifications: {
      actual_GreaterThan_20_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 20
        contactEmails: [
          notificationEmail
        ]
        contactGroups: [
          actionGroupId
        ]
      }
      actual_GreaterThan_50_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        contactEmails: [
          notificationEmail
        ]
        contactGroups: [
          actionGroupId
        ]
      }
      actual_GreaterThan_80_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: [
          notificationEmail
        ]
        contactGroups: [
          actionGroupId
        ]
      }
    }
  }
}

output resourceGroupBudgetId string = resourceGroupBudget.id
