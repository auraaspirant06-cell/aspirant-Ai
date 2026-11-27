@description('Azure region for Aspirant AI deployment')
param location string = resourceGroup().location
param appPrefix string = 'aspirant-ai'

resource managedEnv 'Microsoft.App/managedEnvironments@2024-03-01' = {
  name: '${appPrefix}-env'
  location: location
}

resource apiApp 'Microsoft.App/containerApps@2024-03-01' = {
  name: '${appPrefix}-api'
  location: location
  properties: {
    managedEnvironmentId: managedEnv.id
    configuration: {
      ingress: {
        external: true
        targetPort: 8000
        transport: 'auto'
      }
    }
    template: {
      containers: [
        {
          name: 'backend'
          image: 'ghcr.io/aspirant-ai/backend:latest'
          resources: {
            cpu: json('1.0')
            memory: '2Gi'
          }
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 5
      }
    }
  }
}

output apiFqdn string = apiApp.properties.configuration.ingress.fqdn
