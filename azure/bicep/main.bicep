@description('The location where resources will be deployed')
param location string = resourceGroup().location

@description('Name of the Container App Environment')
param environmentName string = 'snitch-bot-env'

@description('Name of the Container App')
param containerAppName string = 'snitch-discord-bot'

@description('Container image to deploy')
param containerImage string

@description('Discord Bot Token')
@secure()
param discordToken string

@description('Discord Client ID')
param discordClientId string

@description('Discord Client Secret')
@secure()
param discordClientSecret string

@description('Azure Subscription ID')
param azureSubscriptionId string

@description('Azure Tenant ID')
param azureTenantId string

@description('Azure Client ID')
param azureClientId string

@description('Azure Client Secret')
@secure()
param azureClientSecret string

@description('Cosmos DB Connection String')
@secure()
param cosmosConnectionString string

@description('Groq API Key')
@secure()
param groqApiKey string

@description('Log Analytics Workspace ID')
param logAnalyticsWorkspaceId string

// Container Apps Environment
resource containerAppEnvironment 'Microsoft.App/managedEnvironments@2023-05-01' = {
  name: environmentName
  location: location
  properties: {
    appLogsConfiguration: {
      destination: 'log-analytics'
      logAnalyticsConfiguration: {
        customerId: logAnalyticsWorkspaceId
      }
    }
  }
}

// Container App
resource containerApp 'Microsoft.App/containerApps@2023-05-01' = {
  name: containerAppName
  location: location
  properties: {
    managedEnvironmentId: containerAppEnvironment.id
    configuration: {
      activeRevisionsMode: 'Single'
      secrets: [
        {
          name: 'discord-token'
          value: discordToken
        }
        {
          name: 'discord-client-secret'
          value: discordClientSecret
        }
        {
          name: 'azure-client-secret'
          value: azureClientSecret
        }
        {
          name: 'cosmos-connection-string'
          value: cosmosConnectionString
        }
        {
          name: 'groq-api-key'
          value: groqApiKey
        }
      ]
    }
    template: {
      containers: [
        {
          name: 'snitch-bot'
          image: containerImage
          resources: {
            cpu: json('0.5')
            memory: '1Gi'
          }
          env: [
            // Discord Configuration
            {
              name: 'DISCORD_TOKEN'
              secretRef: 'discord-token'
            }
            {
              name: 'DISCORD_CLIENT_ID'
              value: discordClientId
            }
            {
              name: 'DISCORD_CLIENT_SECRET'
              secretRef: 'discord-client-secret'
            }
            // Azure Configuration
            {
              name: 'AZURE_SUBSCRIPTION_ID'
              value: azureSubscriptionId
            }
            {
              name: 'AZURE_TENANT_ID'
              value: azureTenantId
            }
            {
              name: 'AZURE_CLIENT_ID'
              value: azureClientId
            }
            {
              name: 'AZURE_CLIENT_SECRET'
              secretRef: 'azure-client-secret'
            }
            // Cosmos DB Configuration
            {
              name: 'COSMOS_CONNECTION_STRING'
              secretRef: 'cosmos-connection-string'
            }
            {
              name: 'COSMOS_DATABASE_NAME'
              value: 'snitch'
            }
            {
              name: 'COSMOS_CONTAINER_OPERATIONAL'
              value: 'operational_data'
            }
            {
              name: 'COSMOS_CONTAINER_CONTENT'
              value: 'content_data'
            }
            // AI Configuration
            {
              name: 'GROQ_API_KEY'
              secretRef: 'groq-api-key'
            }
            {
              name: 'GROQ_MODEL_NAME'
              value: 'mixtral-8x7b-32768'
            }
            // Application Configuration
            {
              name: 'ENVIRONMENT'
              value: 'production'
            }
            {
              name: 'LOG_LEVEL'
              value: 'INFO'
            }
            {
              name: 'DEBUG'
              value: 'false'
            }
            {
              name: 'ENABLE_MOCK_SERVICES'
              value: 'false'
            }
            {
              name: 'MOCK_AI_RESPONSES'
              value: 'false'
            }
            // ChromaDB Configuration (local storage)
            {
              name: 'CHROMA_HOST'
              value: 'localhost'
            }
            {
              name: 'CHROMA_PORT'
              value: '8000'
            }
            {
              name: 'CHROMA_PERSIST_DIRECTORY'
              value: '/app/chroma_data'
            }
          ]
          volumeMounts: [
            {
              mountPath: '/app/chroma_data'
              volumeName: 'chroma-data'
            }
          ]
        }
      ]
      scale: {
        minReplicas: 1
        maxReplicas: 2
        rules: [
          {
            name: 'cpu-scaling'
            custom: {
              type: 'cpu'
              metadata: {
                type: 'Utilization'
                value: '70'
              }
            }
          }
        ]
      }
      volumes: [
        {
          name: 'chroma-data'
          storageType: 'AzureFile'
          storageName: 'chroma-storage'
        }
      ]
    }
  }
}

// Storage for ChromaDB data
resource storageAccount 'Microsoft.Storage/storageAccounts@2023-01-01' = {
  name: 'snitchbotchroma${uniqueString(resourceGroup().id)}'
  location: location
  sku: {
    name: 'Standard_LRS'
  }
  kind: 'StorageV2'
  properties: {
    accessTier: 'Hot'
  }
}

resource fileShare 'Microsoft.Storage/storageAccounts/fileServices/shares@2023-01-01' = {
  name: '${storageAccount.name}/default/chroma-data'
  properties: {
    shareQuota: 10
  }
}

// Output the Container App URL
output containerAppUrl string = 'https://${containerApp.properties.configuration.ingress.fqdn}'
output environmentId string = containerAppEnvironment.id