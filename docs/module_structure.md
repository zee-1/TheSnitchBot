# Module Structure Plan - The Snitch Discord Bot

## Overview
This document outlines the modular architecture for "The Snitch" Discord bot, organized around Azure cloud components and the specific requirements from the SRS and technical plan.

## Core Architecture Principles
- **Serverless-First**: Leverage Azure Functions for event-driven processing
- **Cost-Optimized**: Use free tiers and consumption-based pricing
- **Modular Design**: Clear separation of concerns with independent modules
- **Data Isolation**: Server-specific data separation using server_id as partition key

## Module Organization

### 1. Core Infrastructure Modules

#### 1.1 Azure Functions Module (`src/functions/`)
**Purpose**: Serverless compute layer for all bot operations
**Components**:
- `timer-newsletter/` - Daily newsletter generation (Timer trigger)
- `discord-commands/` - Slash command handlers (HTTP trigger)
- `message-processor/` - Real-time message processing (Service Bus trigger)

**Azure Services Used**:
- Azure Functions (Consumption Plan)
- Function App hosting

#### 1.2 API Gateway Module (`src/gateway/`)
**Purpose**: Request routing and authentication
**Components**:
- `discord-webhook-handler.js` - Discord interaction endpoint
- `rate-limiter.js` - Request throttling
- `auth-validator.js` - Discord signature validation

**Azure Services Used**:
- Azure API Management (Consumption)

### 2. Data Layer Modules

#### 2.1 Database Module (`src/database/`)
**Purpose**: Data persistence and retrieval
**Components**:
- `cosmos-client.js` - Cosmos DB connection and operations
- `models/` - Data models and schemas
  - `server-config.js` - Server configuration model
  - `tips.js` - User tips model
  - `newsletter-history.js` - Newsletter tracking model
- `repositories/` - Data access layer
  - `server-repository.js`
  - `tips-repository.js`
  - `newsletter-repository.js`

**Azure Services Used**:
- Azure Cosmos DB for PostgreSQL (Free Tier)

#### 2.2 Vector Storage Module (`src/vector-db/`)
**Purpose**: Message embeddings and similarity search
**Components**:
- `chroma-client.js` - ChromaDB client and operations
- `embedding-service.js` - Text embedding generation
- `similarity-search.js` - Vector similarity operations
- `collection-manager.js` - Server-specific collection management

**Azure Services Used**:
- Azure Container Apps (hosting ChromaDB)
- Azure Files (persistent storage)

#### 2.3 Blob Storage Module (`src/storage/`)
**Purpose**: File storage and content delivery
**Components**:
- `blob-client.js` - Azure Blob operations
- `file-manager.js` - File upload/download utilities
- `content-cache.js` - Static content caching

**Azure Services Used**:
- Azure Blob Storage (Free Tier - 5GB)

### 3. AI Processing Modules

#### 3.1 LangChain Orchestration Module (`src/ai/`)
**Purpose**: AI workflow orchestration and prompt management
**Components**:
- `newsletter-pipeline.js` - Full RAG/CoT pipeline for newsletters
- `chains/` - Individual LangChain components
  - `news-desk-chain.js` - Story identification (Chain A)
  - `editor-chief-chain.js` - Story selection (Chain B)
  - `star-reporter-chain.js` - Article writing (Chain C)
- `prompts/` - Prompt templates
  - `newsletter-prompts.js`
  - `command-prompts.js`
  - `persona-prompts.js`

#### 3.2 Groq Integration Module (`src/groq/`)
**Purpose**: Fast AI inference service
**Components**:
- `groq-client.js` - Groq API client
- `inference-service.js` - AI model operations
- `response-parser.js` - Response formatting utilities

### 4. Discord Integration Modules

#### 4.1 Discord API Module (`src/discord/`)
**Purpose**: Discord platform integration
**Components**:
- `discord-client.js` - Discord API client
- `message-handler.js` - Message processing
- `command-handler.js` - Slash command processing
- `webhook-handler.js` - Discord webhook management

#### 4.2 Commands Module (`src/commands/`)
**Purpose**: Discord slash command implementations
**Components**:
- `breaking-news.js` - /breaking-news command
- `fact-check.js` - /fact-check command
- `leak.js` - /leak command
- `set-persona.js` - /set-persona command
- `set-news-channel.js` - /set-news-channel command
- `set-news-time.js` - /set-news-time command
- `submit-tip.js` - /submit-tip command

### 5. Background Services Modules

#### 5.1 Message Processing Module (`src/processors/`)
**Purpose**: Real-time message analysis and storage
**Components**:
- `message-indexer.js` - Message embedding and storage
- `controversy-scorer.js` - Controversy score calculation
- `activity-tracker.js` - User activity monitoring

#### 5.2 Communication Module (`src/messaging/`)
**Purpose**: Asynchronous service communication
**Components**:
- `service-bus-client.js` - Azure Service Bus operations
- `message-publisher.js` - Event publishing
- `message-subscriber.js` - Event consumption

**Azure Services Used**:
- Azure Service Bus (Standard)

### 6. Security & Configuration Modules

#### 6.1 Security Module (`src/security/`)
**Purpose**: Security and secret management
**Components**:
- `key-vault-client.js` - Azure Key Vault operations
- `secret-manager.js` - Secret retrieval and caching
- `auth-service.js` - Authentication utilities

**Azure Services Used**:
- Azure Key Vault (Standard)
- Microsoft Entra ID (Free Tier)

#### 6.2 Configuration Module (`src/config/`)
**Purpose**: Application configuration management
**Components**:
- `app-config.js` - Application settings
- `environment-config.js` - Environment-specific configs
- `feature-flags.js` - Feature toggles

### 7. Monitoring & Logging Modules

#### 7.1 Monitoring Module (`src/monitoring/`)
**Purpose**: Observability and performance tracking
**Components**:
- `logger.js` - Structured logging
- `metrics-collector.js` - Application metrics
- `health-checker.js` - Service health monitoring
- `alert-manager.js` - Alert handling

**Azure Services Used**:
- Azure Monitor (Free Tier)
- Application Insights

### 8. Utilities & Common Modules

#### 8.1 Shared Utilities Module (`src/utils/`)
**Purpose**: Common utilities and helpers
**Components**:
- `date-utils.js` - Date/time utilities
- `text-utils.js` - Text processing utilities
- `validation-utils.js` - Input validation
- `error-handler.js` - Error handling utilities

#### 8.2 Types Module (`src/types/`)
**Purpose**: TypeScript type definitions
**Components**:
- `discord-types.js` - Discord API types
- `database-types.js` - Database schema types
- `ai-types.js` - AI service types

## Project Structure

```
src/
├── functions/                 # Azure Functions
│   ├── timer-newsletter/
│   ├── discord-commands/
│   └── message-processor/
├── gateway/                   # API Gateway
├── database/                  # Data persistence
│   ├── models/
│   └── repositories/
├── vector-db/                 # Vector storage
├── storage/                   # Blob storage
├── ai/                        # AI processing
│   ├── chains/
│   └── prompts/
├── groq/                      # Groq integration
├── discord/                   # Discord API
├── commands/                  # Slash commands
├── processors/                # Background processing
├── messaging/                 # Service communication
├── security/                  # Security & secrets
├── config/                    # Configuration
├── monitoring/                # Observability
├── utils/                     # Shared utilities
└── types/                     # Type definitions

infrastructure/                # Terraform IaC
├── modules/
│   ├── functions/
│   ├── cosmos-db/
│   ├── container-apps/
│   ├── api-management/
│   ├── service-bus/
│   ├── key-vault/
│   └── monitoring/
├── environments/
│   ├── dev/
│   ├── staging/
│   └── prod/
└── main.tf

deployment/                    # Deployment scripts
├── github-actions/
├── terraform/
└── docker/

docs/                          # Documentation
├── api/
├── architecture/
└── deployment/

tests/                         # Test suites
├── unit/
├── integration/
└── e2e/
```

## Module Dependencies

### Core Dependencies Flow:
1. **Discord Commands** → **AI Processing** → **Database/Vector Storage**
2. **Timer Newsletter** → **AI Processing** → **Discord API**
3. **Message Processor** → **Vector Storage** → **Service Bus**
4. **All Modules** → **Security** (Key Vault access)
5. **All Modules** → **Monitoring** (Logging/metrics)

## Development Workflow

### 1. Local Development Setup
- Docker Compose for local ChromaDB
- Azure Functions Core Tools
- Azurite for local storage emulation
- Environment variables for API keys

### 2. Testing Strategy
- Unit tests for each module
- Integration tests for Azure services
- End-to-end tests for Discord workflows
- Mock services for external dependencies

### 3. Deployment Pipeline
- GitHub Actions for CI/CD
- Terraform for infrastructure provisioning
- Staging environment for testing
- Blue-green deployment for production

## Cost Optimization Strategy

### Free Tier Utilization:
- Azure Functions: 1M executions/month
- Cosmos DB: 1,000 RU/s + 25GB storage
- Blob Storage: 5GB LRS storage
- API Management: 1M calls/month
- Monitor: 5GB log ingestion/month
- Entra ID: 50K monthly active users

### Resource Scaling:
- Functions scale to zero when idle
- Container Apps scale to zero
- Database auto-scaling based on demand
- Service Bus queues for load distribution

## Security Considerations

### Data Protection:
- Server-specific data isolation
- Encryption at rest and in transit
- Secure secret management
- Regular security audits

### Access Control:
- Role-based access control
- Principle of least privilege
- API key rotation
- Audit logging

This modular structure ensures scalability, maintainability, and cost-effectiveness while leveraging Azure's free tiers and consumption-based pricing model.