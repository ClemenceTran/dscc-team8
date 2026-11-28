targetScope = 'subscription'

@description('Notification email for the subscription budget')
param notificationEmail string = 'clemence.ntran@gmail.com'

resource subscriptionBudget 'Microsoft.Consumption/budgets@2023-05-01' = {
  name: 'budget-dscc-monthly'
  properties: {
    category: 'Cost'
    amount: 20
    timeGrain: 'Monthly'
    timePeriod: {
      startDate: '2026-10-01T00:00:00Z'
      endDate: '2027-09-30T00:00:00Z'
    }
    notifications: {
      actual_GreaterThan_50_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 50
        contactEmails: [
          notificationEmail
        ]
      }
      actual_GreaterThan_80_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 80
        contactEmails: [
          notificationEmail
        ]
      }
      actual_GreaterThan_100_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: [
          notificationEmail
        ]
      }
      forecasted_GreaterThan_100_Percent: {
        enabled: true
        operator: 'GreaterThan'
        threshold: 100
        contactEmails: [
          notificationEmail
        ]
      }
    }
  }
}

output subscriptionBudgetId string = subscriptionBudget.id