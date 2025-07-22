# LLM Interaction Flow

This diagram illustrates the high-level interaction between different services and the Large Language Model (LLM) to generate content. It shows how user commands or scheduled tasks trigger different Chain of Thoughts (CoT) and Retrieval-Augmented Generation (RAG) pipelines.

```mermaid
graph TD
    subgraph User Input
        direction LR
        LeakInput[Discord Command /leak]
        BreakingNewsInput[Discord Command /breaking-news]
        ScheduledTask[Scheduled Task e.g., Newsletter]
    end

    subgraph Data Sources
        direction RL
        ChromaDB[ChromaDB Vector Store]
        CosmosDB[Cosmos DB e.g., Server Persona]
        DiscordChannel[Discord Channel History]
    end

    subgraph AI Orchestration Layer
        direction TB
        AIService[AI Service / Pipeline]

        subgraph "Chain of Thoughts (CoT) for /leak command"
            direction TB
            LeakChain1[1. Context Analyzer Chain] --> LeakChain2[2. Content Planner Chain] --> LeakChain3[3. Leak Writer Chain]
        end

        subgraph "Simplified RAG/CoT for /breaking-news"
            direction TB
            BreakingNewsChain[1. Single-Shot Analyze & Write Chain]
        end

        subgraph "RAG/CoT Pipeline for Newsletter"
            direction TB
            NewsChain1[A. News Desk Chain] --> NewsChain2[B. Editor Chief Chain] --> NewsChain3[C. Star Reporter Chain]
        end
    end

    subgraph External Services
        GroqAPI[LLM via Groq API]
    end
    
    subgraph Final Output
        DiscordResponse[Post to Discord Channel]
    end

    %% Connections
    LeakInput --> AIService
    BreakingNewsInput --> AIService
    ScheduledTask --> AIService

    AIService -- "Retrieves recent messages" --> DiscordChannel
    AIService -- "Retrieves embeddings" --> ChromaDB
    AIService -- "Retrieves config" --> CosmosDB

    AIService --"Initiates /leak flow"--> LeakChain1
    AIService --"Initiates /breaking-news flow"--> BreakingNewsChain
    AIService --"Initiates Newsletter flow"--> NewsChain1

    LeakChain1 --"Analyzed Context"--> LeakChain2
    LeakChain2 --"Content Plan"--> LeakChain3
    
    NewsChain1 --"Potential Stories"--> NewsChain2
    NewsChain2 --"Selected Headline"--> NewsChain3

    LeakChain1 --> GroqAPI
    LeakChain2 --> GroqAPI
    LeakChain3 --> GroqAPI

    BreakingNewsChain --> GroqAPI
    
    NewsChain1 --> GroqAPI
    NewsChain2 --> GroqAPI
    NewsChain3 --> GroqAPI

    GroqAPI --"LLM Response"--> LeakChain1
    GroqAPI --"LLM Response"--> LeakChain2
    GroqAPI --"LLM Response"--> LeakChain3

    GroqAPI --"LLM Response"--> BreakingNewsChain

    GroqAPI --"LLM Response"--> NewsChain1
    GroqAPI --"LLM Response"--> NewsChain2
    GroqAPI --"LLM Response"--> NewsChain3

    LeakChain3 --"Final Content"--> DiscordResponse
    BreakingNewsChain --"Final Content"--> DiscordResponse
    NewsChain3 --"Final Newsletter"--> DiscordResponse
    
    %% Styling
    classDef userInput fill:#D6EAF8,stroke:#3498DB,stroke-width:2px;
    classDef service fill:#D5F5E3,stroke:#2ECC71,stroke-width:2px;
    classDef chain fill:#FEF9E7,stroke:#F1C40F,stroke-width:2px;
    classDef data fill:#FADBD8,stroke:#E74C3C,stroke-width:2px;
    classDef external fill:#EAECEE,stroke:#95A5A6,stroke-width:2px;
    classDef output fill:#E8DAEF,stroke:#8E44AD,stroke-width:2px;

    class LeakInput,BreakingNewsInput,ScheduledTask userInput;
    class AIService service;
    class LeakChain1,LeakChain2,LeakChain3,NewsChain1,NewsChain2,NewsChain3,BreakingNewsChain chain;
    class ChromaDB,CosmosDB,DiscordChannel data;
    class GroqAPI external;
    class DiscordResponse output;
```