#!/bin/bash

# Azure Container Apps Deployment Script for Snitch Discord Bot
# This script builds the Docker image, pushes to Azure Container Registry,
# and deploys to Azure Container Apps

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-snitch-bot-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-snitchbotacr}"
IMAGE_NAME="snitch-discord-bot"
TAG="${TAG:-$(date +%Y%m%d-%H%M%S)}"
CONTAINER_APP_NAME="${CONTAINER_APP_NAME:-snitch-discord-bot}"
ENVIRONMENT_NAME="${ENVIRONMENT_NAME:-snitch-bot-env}"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check prerequisites
check_prerequisites() {
    log_info "Checking prerequisites..."
    
    if ! command -v az &> /dev/null; then
        log_error "Azure CLI is not installed. Please install it first."
        exit 1
    fi
    
    if ! command -v docker &> /dev/null; then
        log_error "Docker is not installed. Please install it first."
        exit 1
    fi
    
    # Check if logged into Azure
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Run 'az login' first."
        exit 1
    fi
    
    log_info "Prerequisites check passed."
}

# Create resource group if it doesn't exist
create_resource_group() {
    log_info "Creating resource group if it doesn't exist..."
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    log_info "Resource group '$RESOURCE_GROUP' is ready."
}

# Create Azure Container Registry if it doesn't exist
create_acr() {
    log_info "Creating Azure Container Registry if it doesn't exist..."
    
    if ! az acr show --name "$ACR_NAME" --resource-group "$RESOURCE_GROUP" &> /dev/null; then
        az acr create \
            --resource-group "$RESOURCE_GROUP" \
            --name "$ACR_NAME" \
            --sku Basic \
            --admin-enabled true \
            --output none
        log_info "Azure Container Registry '$ACR_NAME' created."
    else
        log_info "Azure Container Registry '$ACR_NAME' already exists."
    fi
}

# Build and push Docker image
build_and_push_image() {
    log_info "Building Docker image..."
    
    # Build the image
    docker build -t "$IMAGE_NAME:$TAG" .
    docker tag "$IMAGE_NAME:$TAG" "$IMAGE_NAME:latest"
    
    log_info "Logging into Azure Container Registry..."
    az acr login --name "$ACR_NAME"
    
    # Tag for ACR
    docker tag "$IMAGE_NAME:$TAG" "$ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG"
    docker tag "$IMAGE_NAME:latest" "$ACR_NAME.azurecr.io/$IMAGE_NAME:latest"
    
    log_info "Pushing image to Azure Container Registry..."
    docker push "$ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG"
    docker push "$ACR_NAME.azurecr.io/$IMAGE_NAME:latest"
    
    log_info "Image pushed successfully: $ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG"
}

# Deploy using Bicep
deploy_infrastructure() {
    log_info "Deploying infrastructure using Bicep..."
    
    # Check if required environment variables are set
    required_vars=(
        "DISCORD_TOKEN"
        "DISCORD_CLIENT_ID"
        "DISCORD_CLIENT_SECRET"
        "AZURE_CLIENT_SECRET"
        "COSMOS_CONNECTION_STRING"
        "GROQ_API_KEY"
    )
    
    for var in "${required_vars[@]}"; do
        if [[ -z "${!var}" ]]; then
            log_error "Required environment variable $var is not set."
            log_info "Please source your .env file or set the variables manually."
            exit 1
        fi
    done
    
    # Create Log Analytics Workspace first (if needed)
    log_info "Creating Log Analytics Workspace..."
    WORKSPACE_ID=$(az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "${CONTAINER_APP_NAME}-logs" \
        --location "$LOCATION" \
        --query customerId \
        --output tsv)
    
    # Deploy the Bicep template
    az deployment group create \
        --resource-group "$RESOURCE_GROUP" \
        --template-file azure/bicep/main.bicep \
        --parameters \
            environmentName="$ENVIRONMENT_NAME" \
            containerAppName="$CONTAINER_APP_NAME" \
            containerImage="$ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG" \
            discordToken="$DISCORD_TOKEN" \
            discordClientId="$DISCORD_CLIENT_ID" \
            discordClientSecret="$DISCORD_CLIENT_SECRET" \
            azureSubscriptionId="$AZURE_SUBSCRIPTION_ID" \
            azureTenantId="$AZURE_TENANT_ID" \
            azureClientId="$AZURE_CLIENT_ID" \
            azureClientSecret="$AZURE_CLIENT_SECRET" \
            cosmosConnectionString="$COSMOS_CONNECTION_STRING" \
            groqApiKey="$GROQ_API_KEY" \
            logAnalyticsWorkspaceId="$WORKSPACE_ID" \
        --output none
    
    log_info "Infrastructure deployed successfully."
}

# Get deployment information
get_deployment_info() {
    log_info "Getting deployment information..."
    
    # Get the Container App URL
    APP_URL=$(az containerapp show \
        --name "$CONTAINER_APP_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.configuration.ingress.fqdn \
        --output tsv 2>/dev/null || echo "No ingress configured")
    
    log_info "============================================"
    log_info "Deployment completed successfully!"
    log_info "============================================"
    log_info "Resource Group: $RESOURCE_GROUP"
    log_info "Container App: $CONTAINER_APP_NAME"
    log_info "Image: $ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG"
    if [[ "$APP_URL" != "No ingress configured" ]]; then
        log_info "App URL: https://$APP_URL"
    fi
    log_info "============================================"
    
    # Show how to view logs
    log_info "To view logs, run:"
    echo "az containerapp logs show --name $CONTAINER_APP_NAME --resource-group $RESOURCE_GROUP --follow"
}

# Clean up local Docker images
cleanup() {
    log_info "Cleaning up local Docker images..."
    docker rmi "$IMAGE_NAME:$TAG" "$IMAGE_NAME:latest" \
        "$ACR_NAME.azurecr.io/$IMAGE_NAME:$TAG" "$ACR_NAME.azurecr.io/$IMAGE_NAME:latest" \
        2>/dev/null || true
    log_info "Cleanup completed."
}

# Main deployment function
main() {
    log_info "Starting deployment of Snitch Discord Bot to Azure Container Apps..."
    
    check_prerequisites
    create_resource_group
    create_acr
    build_and_push_image
    deploy_infrastructure
    get_deployment_info
    
    log_info "Deployment completed successfully!"
    
    # Ask if user wants to clean up
    read -p "Clean up local Docker images? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        cleanup
    fi
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    main "$@"
fi