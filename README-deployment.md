# Snitch Discord Bot - Azure Container Apps Deployment

This document explains how to deploy the Snitch Discord Bot to Azure Container Apps.

## Prerequisites

1. **Azure CLI** - Install from [here](https://docs.microsoft.com/en-us/cli/azure/install-azure-cli)
2. **Docker** - Install from [here](https://docs.docker.com/get-docker/)
3. **Azure Subscription** - You need an active Azure subscription
4. **Environment Variables** - Copy `.env.example` to `.env` and fill in your values

## Quick Start

### 1. Login to Azure
```bash
az login
```

### 2. Set up your environment file
```bash
cp .env.example .env
# Edit .env with your actual values (Discord tokens, Cosmos DB, etc.)
```

### 3. Set up Azure resources (first time only)
```bash
./scripts/setup-azure.sh
```

This will create:
- Resource Group
- Azure Container Registry
- Cosmos DB with database and containers
- Storage Account for ChromaDB data
- Key Vault for secrets
- Log Analytics Workspace for monitoring

### 4. Deploy the application
```bash
./scripts/deploy.sh
```

This will:
- Build the Docker image
- Push it to Azure Container Registry
- Deploy to Azure Container Apps using Bicep templates

## Local Development

### Build and run locally
```bash
./scripts/build.sh run
```

### View logs
```bash
./scripts/build.sh logs
```

### Stop local services
```bash
./scripts/build.sh stop
```

### Clean up local containers
```bash
./scripts/build.sh clean
```

## Azure Resources Created

### Resource Group: `snitch-bot-rg`
Contains all the bot-related resources.

### Azure Container Registry: `snitchbotacr`
Stores the Docker images for the bot.

### Cosmos DB: `snitchbot-cosmos`
- Database: `snitch`
- Containers:
  - `operational_data` - Server configs, newsletters, user data
  - `content_data` - Messages, tips, analysis results

### Container App Environment: `snitch-bot-env`
Provides the runtime environment with logging and monitoring.

### Container App: `snitch-discord-bot`
The main application with:
- 0.5 CPU, 1GB memory
- Auto-scaling (1-2 replicas)
- Persistent storage for ChromaDB

## Environment Variables

The bot requires these environment variables:

### Discord Configuration
- `DISCORD_TOKEN` - Bot token from Discord Developer Portal
- `DISCORD_CLIENT_ID` - Application ID
- `DISCORD_CLIENT_SECRET` - Client secret

### Azure Configuration
- `AZURE_SUBSCRIPTION_ID` - Your Azure subscription ID
- `AZURE_TENANT_ID` - Your Azure tenant ID
- `AZURE_CLIENT_ID` - Service principal client ID
- `AZURE_CLIENT_SECRET` - Service principal client secret

### Database Configuration
- `COSMOS_CONNECTION_STRING` - Cosmos DB connection string
- `COSMOS_DATABASE_NAME` - Database name (default: snitch)
- `COSMOS_CONTAINER_OPERATIONAL` - Operational data container
- `COSMOS_CONTAINER_CONTENT` - Content data container

### AI Configuration
- `GROQ_API_KEY` - API key for Groq AI service
- `GROQ_MODEL_NAME` - Model to use (default: mixtral-8x7b-32768)

## Monitoring and Logging

### View container logs
```bash
az containerapp logs show \
  --name snitch-discord-bot \
  --resource-group snitch-bot-rg \
  --follow
```

### Monitor resource usage
```bash
az containerapp show \
  --name snitch-discord-bot \
  --resource-group snitch-bot-rg \
  --query properties.template.containers[0].resources
```

## Scaling

The bot automatically scales based on CPU usage:
- Min replicas: 1
- Max replicas: 2
- Scale trigger: 70% CPU utilization

To manually scale:
```bash
az containerapp update \
  --name snitch-discord-bot \
  --resource-group snitch-bot-rg \
  --min-replicas 1 \
  --max-replicas 3
```

## Troubleshooting

### Check container status
```bash
az containerapp show \
  --name snitch-discord-bot \
  --resource-group snitch-bot-rg \
  --query properties.runningStatus
```

### View recent deployments
```bash
az containerapp revision list \
  --name snitch-discord-bot \
  --resource-group snitch-bot-rg \
  --output table
```

### Restart the application
```bash
az containerapp restart \
  --name snitch-discord-bot \
  --resource-group snitch-bot-rg
```

### Check Cosmos DB connectivity
```bash
az cosmosdb show \
  --name snitchbot-cosmos \
  --resource-group snitch-bot-rg \
  --query documentEndpoint
```

## Security

- Secrets are stored securely in the Container App environment
- The container runs as a non-root user
- Cosmos DB uses connection strings with authentication
- ACR uses admin credentials for image pulls

## Cost Optimization

- Container Apps charges based on vCPU-seconds and memory usage
- Cosmos DB containers are provisioned with 400 RU/s each (minimum)
- Storage account uses Standard LRS (cheapest option)
- Log Analytics has pay-as-you-go pricing

Estimated monthly cost: $20-50 USD (depending on usage)

## Updates and Deployments

To deploy a new version:
1. Make your code changes
2. Run `./scripts/deploy.sh` again
3. The script will build a new image with timestamp tag
4. Azure Container Apps will perform a blue-green deployment

## Cleanup

To remove all resources:
```bash
az group delete --name snitch-bot-rg --yes --no-wait
```

**Warning**: This will permanently delete all data and cannot be undone.

## Support

For issues with deployment:
1. Check the container logs first
2. Verify all environment variables are set correctly
3. Ensure Azure resources are created successfully
4. Check Discord bot permissions and token validity