# Discord LARP Bot

A Discord bot that facilitates Live Action Role-Playing (LARP) games with AI-powered storytelling and multilingual support.

## Features

- **Multilingual Support**
  - English
  - Traditional Chinese
  - Bilingual mode (both English and Chinese)

- **Dynamic Game Types**
  - Mystery & Detective: mystery, murder, detective, psychological, conspiracy
  - Adventure & Action: adventure, heist, survival, escape
  - Fantasy & Supernatural: fantasy, supernatural, horror, sci-fi
  - Special Themes: historical, espionage, comedy

- **AI-Powered Storytelling**
  - Dynamic story generation
  - Character role creation
  - Adaptive narrative responses
  - Objective tracking and completion

- **Game Management**
  - Multiple concurrent games in different channels
  - Player join/leave handling
  - Game state persistence
  - Story history tracking

## Commands

- `!start_game` - Start a new game session
- `!scene` - Review current scene and objectives
- `!story` - View story history
- `!end_game` - End current game session

## How to Play

1. Use `!start_game` to initiate a new game
2. React with 👍 to join (2-6 players needed)
3. Select preferred language:
   - 🇺🇸 English
   - 🇹🇼 Traditional Chinese
   - 🌐 Bilingual
4. Vote for game type
5. Receive character roles via DM
6. Start roleplaying by typing actions and dialogue in the channel

## Setup

1. Clone the repository
2. Install dependencies:
```bash
pip install discord.py python-dotenv openai
```

3. Create a `.env` file with:
```
DISCORD_TOKEN=your_discord_token
OPENAI_API_KEY=your_openai_api_key
```

4. Run the bot:
```bash
python bot.py
```

## Technical Details

- Uses Discord.py for bot functionality
- OpenAI GPT-3.5 for AI responses
- Supports message splitting for long content
- Handles Discord's embed limits (25 per message)
- Persistent game state storage using JSON

## Requirements

- Python 3.8+
- discord.py
- python-dotenv
- openai

## Notes

- Enable DMs from server members to receive character roles
- Bot requires appropriate Discord permissions
- Messages are automatically split if they exceed Discord's length limits
- Game data is saved between sessions