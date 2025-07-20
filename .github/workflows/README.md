# GitHub Actions Workflows

This directory contains GitHub Actions workflows for automated deployment of the Snitch Discord Bot.

## Azure App Service Workflow

The `azure-app-service.yml` workflow automatically deploys the bot to Azure App Service when code is pushed to the main branch.

### Required GitHub Secrets

Set these secrets in your GitHub repository settings:

#### Azure Authentication
- `AZURE_CLIENT_ID` - Service Principal Client ID
- `AZURE_TENANT_ID` - Azure Tenant ID  
- `AZURE_SUBSCRIPTION_ID` - Azure Subscription ID
- `AZURE_RESOURCE_GROUP` - Resource group name (e.g., "snitch-bot-rg")

#### Discord Configuration
- `DISCORD_TOKEN` - Bot token from Discord Developer Portal
- `DISCORD_CLIENT_ID` - Application ID
- `DISCORD_CLIENT_SECRET` - Client secret

#### Azure Services
- `AZURE_CLIENT_SECRET` - Service Principal Client Secret (for Azure SDK access)
- `COSMOS_CONNECTION_STRING` - Cosmos DB connection string
- `GROQ_API_KEY` - Groq AI API key

### Setup Instructions

1. **Create a Service Principal:**
   ```bash
   az ad sp create-for-rbac \
     --name "snitch-bot-github-actions" \
     --role contributor \
     --scopes /subscriptions/{subscription-id}/resourceGroups/{resource-group} \
     --sdk-auth
   ```

2. **Add secrets to GitHub:**
   - Go to your repository → Settings → Secrets and variables → Actions
   - Add each secret with the exact names listed above

3. **Create Azure App Service:**
   ```bash
   az webapp create \
     --resource-group snitch-bot-rg \
     --plan snitch-bot-plan \
     --name thesnitchbot \
     --runtime "PYTHON|3.11" \
     --deployment-source-url https://github.com/yourusername/yourrepo
   ```

4. **Configure App Service Plan:**
   ```bash
   az appservice plan create \
     --name snitch-bot-plan \
     --resource-group snitch-bot-rg \
     --sku B1 \
     --is-linux
   ```

### Workflow Stages

1. **Build Stage:**
   - Checks out code
   - Sets up Python 3.11
   - Installs dependencies
   - Runs tests (optional)
   - Creates deployment package

2. **Deploy Stage:**
   - Downloads build artifact
   - Authenticates with Azure
   - Deploys to App Service
   - Configures startup command

3. **Post-Deploy Stage:**
   - Sets environment variables
   - Restarts the app service
   - Performs health checks

### Customization

#### Changing the App Name
Update the `APP_NAME` environment variable in the workflow:
```yaml
env:
  APP_NAME: 'your-app-name'
```

#### Adding Tests
Uncomment and modify the test step:
```yaml
- name: Run tests
  run: |
    python -m pytest tests/
    python -m flake8 src/
```

#### Different Branch
Change the trigger branch:
```yaml
on:
  push:
    branches:
      - production  # Change from 'main'
```

### Monitoring

- View deployment logs in GitHub Actions tab
- Check App Service logs in Azure Portal
- Monitor application insights (if configured)

### Troubleshooting

#### Common Issues

1. **Authentication Failures:**
   - Verify service principal has correct permissions
   - Check that all Azure secrets are correctly set

2. **Deployment Failures:**
   - Check Python version compatibility
   - Verify requirements.txt includes all dependencies
   - Ensure startup.py is executable

3. **Runtime Errors:**
   - Check App Service logs in Azure Portal
   - Verify environment variables are set correctly
   - Check Discord token validity

#### Debug Steps

1. **Enable debug logging:**
   ```yaml
   - name: Debug Azure CLI
     run: az account show
   ```

2. **Check environment variables:**
   ```yaml
   - name: Debug environment
     run: |
       echo "Resource Group: ${{ secrets.AZURE_RESOURCE_GROUP }}"
       echo "App Name: ${{ env.APP_NAME }}"
   ```

3. **Test local deployment:**
   ```bash
   # Test the deployment package locally
   unzip release.zip -d test-deploy
   cd test-deploy
   python startup.py
   ```

### Security Notes

- Never commit secrets to the repository
- Use GitHub encrypted secrets for sensitive data
- Regularly rotate service principal credentials
- Monitor resource access logs

### Cost Considerations

- B1 App Service Plan: ~$13/month
- Consider scaling down to F1 (free) for development
- Monitor usage to optimize costs

For more information, see the [Azure App Service documentation](https://docs.microsoft.com/en-us/azure/app-service/).