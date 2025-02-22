# Discord LARP Bot

A Discord bot for hosting and managing Live Action Role-Playing (LARP) games in Discord servers, featuring AI-powered storytelling.

## Features
- Character creation and management
- Game session management
- Dice rolling for skill checks
- Private messaging for secret actions
- Basic inventory system
- Character stats tracking
- AI-powered storytelling and game mastering
- Dynamic story progression based on player actions

## Requirements
- Python 3.8+
- discord.py
- python-dotenv
- openai

## Setup
1. Clone this repository
2. Create a `.env` file in the root directory and add your tokens:
   ```
   DISCORD_TOKEN=your_bot_token_here
   OPENAI_API_KEY=your_openai_api_key_here
   ```
3. Install requirements:
   ```
   pip install -r requirements.txt
   ```
4. Run the bot:
   ```
   python bot.py
   ```

## Commands
### Character Management
- `!create_character <name>` - Create a new character
- `!stats` - View your character's stats
- `!roll <skill>` - Roll for a skill check
- `!inventory` - View your inventory

### Game Management
- `!start_game` - Start a new game session
- `!action <description>` - Perform an action in the game
- `!scene` - View the current scene description
- `!end_game` - End the current game session

### General
- `!help` - Show all available commands