#!/bin/bash

# Azure Environment Setup Script for Snitch Discord Bot
# This script sets up the required Azure resources before deployment

set -e

# Configuration
RESOURCE_GROUP="${RESOURCE_GROUP:-snitch-bot-rg}"
LOCATION="${LOCATION:-eastus}"
ACR_NAME="${ACR_NAME:-snitchbotacr}"
COSMOS_ACCOUNT_NAME="${COSMOS_ACCOUNT_NAME:-snitchbot-cosmos}"
STORAGE_ACCOUNT_NAME="${STORAGE_ACCOUNT_NAME:-snitchbotsa$(date +%s)}"
KEY_VAULT_NAME="${KEY_VAULT_NAME:-snitchbot-kv}"

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
    
    # Check if logged into Azure
    if ! az account show &> /dev/null; then
        log_error "Not logged into Azure. Run 'az login' first."
        exit 1
    fi
    
    log_info "Prerequisites check passed."
}

# Create resource group
create_resource_group() {
    log_info "Creating resource group: $RESOURCE_GROUP"
    
    az group create \
        --name "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --output none
    
    log_info "Resource group created successfully."
}

# Create Azure Container Registry
create_acr() {
    log_info "Creating Azure Container Registry: $ACR_NAME"
    
    az acr create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$ACR_NAME" \
        --sku Basic \
        --admin-enabled true \
        --output none
    
    log_info "Azure Container Registry created successfully."
}

# Create Cosmos DB account and database
create_cosmos_db() {
    log_info "Creating Cosmos DB account: $COSMOS_ACCOUNT_NAME"
    
    # Create Cosmos DB account
    az cosmosdb create \
        --resource-group "$RESOURCE_GROUP" \
        --name "$COSMOS_ACCOUNT_NAME" \
        --kind GlobalDocumentDB \
        --locations regionName="$LOCATION" failoverPriority=0 isZoneRedundant=False \
        --default-consistency-level "Session" \
        --enable-automatic-failover true \
        --enable-multiple-write-locations false \
        --output none
    
    log_info "Cosmos DB account created successfully."
    
    # Create database
    log_info "Creating Cosmos DB database: snitch"
    az cosmosdb sql database create \
        --account-name "$COSMOS_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --name "snitch" \
        --output none
    
    # Create containers
    log_info "Creating Cosmos DB containers..."
    
    # Operational data container
    az cosmosdb sql container create \
        --account-name "$COSMOS_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --database-name "snitch" \
        --name "operational_data" \
        --partition-key-path "/id" \
        --throughput 400 \
        --output none
    
    # Content data container
    az cosmosdb sql container create \
        --account-name "$COSMOS_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --database-name "snitch" \
        --name "content_data" \
        --partition-key-path "/id" \
        --throughput 400 \
        --output none
    
    log_info "Cosmos DB containers created successfully."
}

# Create storage account
create_storage_account() {
    log_info "Creating storage account: $STORAGE_ACCOUNT_NAME"
    
    az storage account create \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --sku Standard_LRS \
        --kind StorageV2 \
        --access-tier Hot \
        --output none
    
    log_info "Storage account created successfully."
}

# Create Key Vault
create_key_vault() {
    log_info "Creating Key Vault: $KEY_VAULT_NAME"
    
    az keyvault create \
        --name "$KEY_VAULT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --location "$LOCATION" \
        --enable-rbac-authorization false \
        --output none
    
    log_info "Key Vault created successfully."
}

# Create Log Analytics Workspace
create_log_analytics() {
    log_info "Creating Log Analytics Workspace..."
    
    az monitor log-analytics workspace create \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "snitch-bot-logs" \
        --location "$LOCATION" \
        --output none
    
    log_info "Log Analytics Workspace created successfully."
}

# Get connection strings and keys
get_connection_info() {
    log_info "Retrieving connection strings and keys..."
    
    echo "============================================"
    echo "Azure Resources Created Successfully!"
    echo "============================================"
    
    # Cosmos DB connection string
    echo "COSMOS_CONNECTION_STRING:"
    az cosmosdb keys list \
        --name "$COSMOS_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --type connection-strings \
        --query "connectionStrings[0].connectionString" \
        --output tsv
    echo
    
    # Storage account connection string
    echo "STORAGE_CONNECTION_STRING:"
    az storage account show-connection-string \
        --name "$STORAGE_ACCOUNT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query connectionString \
        --output tsv
    echo
    
    # Key Vault URL
    echo "KEY_VAULT_URL:"
    az keyvault show \
        --name "$KEY_VAULT_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query properties.vaultUri \
        --output tsv
    echo
    
    # ACR login server
    echo "CONTAINER_REGISTRY:"
    az acr show \
        --name "$ACR_NAME" \
        --resource-group "$RESOURCE_GROUP" \
        --query loginServer \
        --output tsv
    echo
    
    # Log Analytics Workspace ID
    echo "LOG_ANALYTICS_WORKSPACE_ID:"
    az monitor log-analytics workspace show \
        --resource-group "$RESOURCE_GROUP" \
        --workspace-name "snitch-bot-logs" \
        --query customerId \
        --output tsv
    echo
    
    echo "============================================"
    echo "Please update your .env file with these values."
    echo "Then run the deployment script: ./scripts/deploy.sh"
    echo "============================================"
}

# Store secrets in Key Vault (optional)
store_secrets() {
    if [[ -f ".env" ]]; then
        log_info "Found .env file. Storing secrets in Key Vault..."
        
        # Read .env file and store secrets
        while IFS='=' read -r key value; do
            # Skip comments and empty lines
            [[ $key =~ ^#.*$ ]] && continue
            [[ -z $key ]] && continue
            
            # Remove quotes if present
            value=$(echo "$value" | sed 's/^["'\'']\|["'\'']$//g')
            
            # Store in Key Vault if it looks like a secret
            if [[ $key =~ (TOKEN|SECRET|KEY|PASSWORD|CONNECTION) ]]; then
                az keyvault secret set \
                    --vault-name "$KEY_VAULT_NAME" \
                    --name "${key,,}" \
                    --value "$value" \
                    --output none 2>/dev/null || true
                log_info "Stored secret: $key"
            fi
        done < .env
        
        log_info "Secrets stored in Key Vault successfully."
    else
        log_warn ".env file not found. Skipping secret storage."
    fi
}

# Main setup function
main() {
    log_info "Starting Azure environment setup for Snitch Discord Bot..."
    
    check_prerequisites
    create_resource_group
    create_acr
    create_cosmos_db
    create_storage_account
    create_key_vault
    create_log_analytics
    get_connection_info
    
    # Ask if user wants to store secrets
    read -p "Store secrets from .env file in Key Vault? (y/N): " -n 1 -r
    echo
    if [[ $REPLY =~ ^[Yy]$ ]]; then
        store_secrets
    fi
    
    log_info "Azure environment setup completed successfully!"
}

# Show usage
usage() {
    echo "Usage: $0"
    echo
    echo "This script creates the following Azure resources:"
    echo "  - Resource Group"
    echo "  - Azure Container Registry"
    echo "  - Cosmos DB account with database and containers"
    echo "  - Storage Account"
    echo "  - Key Vault"
    echo "  - Log Analytics Workspace"
    echo
    echo "Environment variables (optional):"
    echo "  RESOURCE_GROUP      Resource group name (default: snitch-bot-rg)"
    echo "  LOCATION           Azure region (default: eastus)"
    echo "  ACR_NAME           Container registry name (default: snitchbotacr)"
    echo "  COSMOS_ACCOUNT_NAME Cosmos DB account name (default: snitchbot-cosmos)"
    echo "  STORAGE_ACCOUNT_NAME Storage account name (default: auto-generated)"
    echo "  KEY_VAULT_NAME     Key Vault name (default: snitchbot-kv)"
}

# Run main function if script is executed directly
if [[ "${BASH_SOURCE[0]}" == "${0}" ]]; then
    if [[ "$1" == "help" || "$1" == "-h" || "$1" == "--help" ]]; then
        usage
    else
        main "$@"
    fi
fi