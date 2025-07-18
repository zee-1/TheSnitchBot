Software Requirements Specification: The Snitch
Version: 1.0
Date: July 18, 2025
Status: Draft

1. Introduction
1.1 Purpose
This document provides a detailed specification of the requirements for the Discord bot "The Snitch". It is intended for developers, project managers, and testers to understand the full scope of the project, including its features, constraints, and quality attributes.

1.2 Scope
The Snitch is an AI-powered Discord bot designed to enhance community engagement by acting as a "spicy AI reporter." It will analyze server conversations to automatically generate newsletters, breaking news reports, and other interactive content. The system will be hosted on Microsoft Azure and will leverage the Groq API for fast AI inference, LangChain for orchestration, and ChromaDB for vector storage.

1.3 Definitions, Acronyms, and Abbreviations
SRS: Software Requirements Specification

AI: Artificial Intelligence

LLM: Large Language Model

RAG: Retrieval-Augmented Generation

CoT: Chain of Thought

API: Application Programming Interface

DB: Database

2. Overall Description
2.1 Product Perspective
The Snitch is a standalone, serverless application that interacts with the Discord platform via its API. It relies on external services, including Microsoft Azure (Functions, Cosmos DB), Groq (AI Inference), and ChromaDB (Vector Storage).

2.2 User Classes and Characteristics
Server Administrator (Admin): Users with administrative permissions on a Discord server. They are responsible for inviting the bot and configuring its settings (e.g., newsletter channel, time, persona).

Server Member (User): General users of a Discord server who can interact with the bot's public commands and consume its generated content.

2.3 Operating Environment
The bot will operate exclusively within the Discord platform.

The backend infrastructure will be hosted entirely on Microsoft Azure.

A persistent internet connection is required for communication between Azure, Discord, and the Groq API.

3. System Features (Functional Requirements)
3.1 Newsletter Generation
REQ-NL-01: The system shall automatically generate and post a "Newsletter" to a designated channel on a daily schedule.

REQ-NL-02: Server Admins must be able to set the specific time of day for the newsletter dispatch.

REQ-NL-03: The newsletter content must be generated based on an analysis of the server's public messages from the preceding 24 hours.

REQ-NL-04: The newsletter's writing style must conform to the currently configured server persona.

REQ-NL-05: The system shall use a RAG and CoT pipeline to identify key events, select a headline story, and write the final article.

REQ-NL-06: The system shall store message embeddings in a server-specific ChromaDB collection to ensure data isolation.

3.2 /breaking-news Command
REQ-BN-01: Any Server Member must be able to invoke the /breaking-news command.

REQ-BN-02: The command shall trigger an immediate analysis of the last ~50-100 messages in the current channel.

REQ-BN-03: The system shall generate and post a single-paragraph "breaking news" bulletin based on the analysis.

REQ-BN-04: The bulletin's tone must match the server's configured persona.

3.3 /fact-check Command
REQ-FC-01: Any Server Member must be able to invoke the /fact-check command on a specific message.

REQ-FC-02: The system shall analyze the specified message content and provide a humorous, non-authoritative verdict.

REQ-FC-03: The response must be one of three predefined categories: "True," "False," or "Needs Investigation," represented by corresponding emojis and text.

3.4 /leak Command
REQ-LK-01: Any Server Member must be able to invoke the /leak command.

REQ-LK-02: The system shall generate a harmless, humorous, and clearly fabricated "secret" about a random, recently active user.

3.5 Controversy Score
REQ-CS-01: The system shall calculate a "Controversy Score" for messages as they are processed for the newsletter.

REQ-CS-02: The score shall be based on a combination of metrics, including reply velocity, reaction counts, and keyword analysis.

REQ-CS-03: This score must be used as a factor in the "News Desk" (Chain A) logic to help identify newsworthy events.

3.6 Configuration
REQ-CFG-01: Server Admins must be able to change the bot's active persona using a /set-persona command.

REQ-CFG-02: Server Admins must be able to set the newsletter destination channel using a /set-news-channel command.

REQ-CFG-03: Server Admins must be able to set the newsletter time using a /set-news-time command.

3.7 Tip Submission
REQ-TIP-01: Any Server Member must be able to anonymously submit a "tip" to the bot using the /submit-tip command or via Direct Message.

REQ-TIP-02: Submitted tips must be stored in the Cosmos DB tips collection, associated with the server_id.

4. Non-Functional Requirements
PERF-01 (Performance): All slash command interactions (/breaking-news, /fact-check, etc.) must receive a response from the bot in under 3 seconds.

PERF-02 (Performance): The daily newsletter generation process for a single server should complete within 2 minutes to avoid overlapping with other tasks.

SCAL-01 (Scalability): The architecture must support operating on thousands of Discord servers concurrently without significant degradation in performance.

REL-01 (Reliability): The bot's core services shall maintain an uptime of 99.5%. The system must include error handling for API failures from Discord or Groq.

SEC-01 (Security): All data for a specific Discord server (configurations, messages, tips) must be logically isolated from all other servers.

SEC-02 (Security): All API keys and secrets must be stored securely using Azure Key Vault, not in source code.

MAIN-01 (Maintainability): The codebase shall be modular, with clear separation between the Discord interaction layer, the AI service layer, and the data persistence layer.