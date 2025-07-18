Functional Specification: The Snitch
This document details the operational logic for each feature of "The Snitch" bot, bridging the user experience with the underlying RAG, CoT, and Azure architecture.

1. Core Functionality: The Newsletter
This is the bot's flagship feature, running automatically in the background.

User Experience: Once a day, at a time configured by the server admin, the bot will post a "Daily Dispatch" or "Newsletter" into a designated channel. This post will be written in the server's chosen persona and highlight the most interesting event of the last 24 hours.

Technical Logic (The Full RAG/CoT Pipeline):

Trigger: A time-triggered Azure Function runs every 5-10 minutes. It queries the servers collection in Cosmos DB to find any servers whose news_time has passed since the last run.

Step 1: Retrieval: For each due server, the function:

Fetches the last 24 hours of messages from the server.

Chunks, embeds, and stores these messages in the server's dedicated ChromaDB collection (identified by server_id).

Step 2: LangChain Pipeline (The Newsroom):

Chain A (News Desk): The system performs a similarity search on the ChromaDB collection to retrieve the most active conversation clusters. These are fed into the "News Desk" prompt to identify potential stories.

Chain B (Editor-in-Chief): The potential stories are passed to the "Editor-in-Chief" prompt, along with the server's persona (retrieved from Cosmos DB), to select the main headline.

Chain C (Star Reporter): The chosen story, persona, and the original source messages (retrieved again for quoting) are fed into the "Star Reporter" prompt to write the final article.

Dispatch: The formatted text from Chain C is posted to the news_channel_id (from Cosmos DB).

Update: A timestamp for the last newsletter sent is updated in the servers collection to prevent duplicate posts.

2. AI Commands & Reactions
These are user-invoked commands that provide instant, AI-powered responses.

/breaking-news
User Experience: A user types /breaking-news. The bot immediately analyzes the last ~50-100 messages in the channel and posts a dramatic, "Breaking News" bulletin about the most recent topic.

Technical Logic: This is a compressed version of the newsletter pipeline.

Trigger: An HTTP-triggered Azure Function receives the command from Discord.

Retrieval: The bot fetches the last X messages from the channel.

Generation: It uses a simplified, single-shot CoT prompt that combines the "News Desk" and "Star Reporter" logic:

"You are a [persona] reporter. Analyze the last 50 messages. Identify the single most important event, then write a short, one-paragraph 'BREAKING NEWS' bulletin about it. Quote at least one user."

Response: The generated text is sent back as an immediate reply.

/fact-check [message_id]
User Experience: A user replies to a message and uses the /fact-check command. The bot replies with a humorous verdict like "🟢 True," "🔴 Cap," or "🟡 Needs Investigation."

Technical Logic:

The bot retrieves the content of the specified message.

It uses a simple prompt:

"You are a skeptical fact-checker. Read this statement: '[message content]'. Is this statement likely true, false, or impossible to verify from the context of a Discord chat? Respond with only 'True', 'False', or 'Needs Investigation'."

The bot maps the single-word response to the corresponding emoji and text.

/leak
User Experience: A user types /leak. The bot posts a funny, completely fabricated "leak" about a random, recently active user.

Technical Logic:

The bot fetches a list of users who have been active in the last hour.

It picks a random user.

It uses a creative prompt:

"You are a shady informant. Write a funny, harmless, and obviously fake 'leaked' secret about @[username]. The leak should be about a silly topic like video games, food, or hobbies."

3. Engagement & Chaos Mechanics
These systems run in the background to quantify and gamify server activity.

"Controversy Score" Tracker
User Experience: This is mostly invisible to users but directly feeds the newsletter. The most controversial messages are more likely to be featured.

Technical Logic:

As messages are indexed into ChromaDB (Step 1a of the newsletter flow), a "Controversy Score" is calculated and stored as metadata.

Metrics for Score:

reply_velocity: How many replies a message gets in a short time.

reaction_count: Total number of reactions.

negative_reactions: Count of reactions like 😠, 👎, etc.

keyword_analysis: A small score boost for words associated with debate or drama (e.g., "actually," "wrong," "prove it").

The "News Desk" prompt (Chain A) will be instructed to use this score to help identify top events.

Mini-Games (e.g., Guess the Quote)
User Experience: The bot posts a message like: "Guess Who Said It: 'I can't believe you've done this.' You have 60 seconds to guess!" Users reply with their guesses.

Technical Logic:

A time-triggered command or manual admin command initiates the game.

The bot queries its ChromaDB collection for a random but memorable message from the past week.

It posts the quote and starts a 60-second timer.

It listens for replies and checks if the message author matches the guess. The first correct guess wins.

4. Configuration & Utility
/set-persona [persona_name]
User Experience: An admin uses this command to change the bot's personality.

Technical Logic: The command updates the persona field for the server_id in the Cosmos DB servers collection. This value is then directly injected into the prompts for all generation tasks.

/submit-tip [message]
User Experience: A user can send a DM to the bot or use this command to anonymously submit a "tip."

Technical Logic:

The command saves the tip message, server_id, and a timestamp into the tips collection in Cosmos DB.

Future enhancement: The "News Desk" chain could be programmed to review these tips and use them as starting points for its similarity search in ChromaDB to see if a tipped event has public chatter associated with it.