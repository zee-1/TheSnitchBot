Low-Cost Azure Architecture Breakdown
This document outlines the specific Azure services and plans chosen to implement your system architecture with a strong focus on minimizing costs by leveraging free tiers and consumption-based plans.

1. Edge Layer
Handles incoming traffic, security, and routing.

Component

Service Selection

Plan / Tier

Rationale & Key Considerations

CDN & WAF

Cloudflare (External)

Free Plan

Provides a world-class CDN, DDoS protection, and a Web Application Firewall at no cost. It's a powerful external service to place in front of your Azure resources.

API Gateway

Azure API Management

Consumption

Pay-per-execution model. The first 1 million calls are free each month, making it ideal for low-traffic APIs. It's serverless, so there are no idle costs.

2. Compute Layer
Where your application logic and microservices run.

Component

Service Selection

Plan / Tier

Rationale & Key Considerations

Event-Driven Services

Azure Functions

Consumption

Perfect for simple APIs and background tasks. You get 1 million executions free per month. If your code isn't running, you pay nothing.

Microservices & Backend

Azure Container Apps

Consumption

Ideal for running containerized applications (like your main API or ChromaDB). Includes a generous free monthly grant of vCPU and memory hours. Scales to zero.

3. Data & Storage Layer
Manages all persistent data, from databases to files.

Component

Service Selection

Plan / Tier

Rationale & Key Considerations

Primary Database

Azure Cosmos DB for PostgreSQL

Free Tier

Provides 1,000 RU/s and 25 GB of storage free every month. Uses the standard PostgreSQL API, avoiding vendor lock-in.

Vector Search

Self-Hosted ChromaDB

(Hosted on Azure Container Apps)

The most cost-effective way to run ChromaDB. The container runs on the free grant of Container Apps. Requires persistent storage using Azure Files.

File Storage

Azure Blob Storage

Standard

The "Always Free" tier includes 5 GB of LRS storage, which is sufficient for many initial projects.

Cache

(Deferred)

N/A

To minimize costs, a dedicated cache like Redis is initially omitted. The database will be fast enough for low traffic. Can be added later.

4. Communication Layer
Facilitates communication between services.

Component

Service Selection

Plan / Tier

Rationale & Key Considerations

Message Queue

Azure Service Bus

Standard

The Standard tier is required for Topics/Subscriptions. While not entirely free, it's very low-cost and the best choice for reliable messaging.

Service Discovery

(Handled by Container Apps)

N/A

The Azure Container Apps environment provides built-in DNS-based service discovery, so services can find each other by name without an extra component.

5. Security & Identity Layer
Secures the application, manages secrets, and handles user identity.

Component

Service Selection

Plan / Tier

Rationale & Key Considerations

Identity Provider

Microsoft Entra ID for customers

Free Tier

Manages user sign-up, sign-in, and profiles. The free tier supports up to 50,000 monthly active users.

Secret Manager

Azure Key Vault

Standard

While not free, it's incredibly cheap for low usage (pennies per month). Essential for securely storing secrets, keys, and connection strings.

6. Monitoring & DevOps Layer
Observability and deployment pipelines.

Component

Service Selection

Plan / Tier

Rationale & Key Considerations

Monitoring & Logging

Azure Monitor

Free Tier

Includes 5 GB of log data ingestion free per month. Provides metrics, logs, and basic alerting for all your services.

CI/CD Pipeline

GitHub Actions / Azure DevOps

Free Tiers

Both platforms offer excellent free tiers for individuals and small teams with enough build minutes for most projects.

Infrastructure as Code

Terraform

Open Source

The tool itself is free. You only pay for the Azure resources it creates. It's the industry standard for managing cloud infrastructure.

