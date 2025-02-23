import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
from pathlib import Path
from openai import OpenAI
import asyncio
import random
import unicodedata

# Load environment variables
load_dotenv()
TOKEN = os.getenv('DISCORD_TOKEN')
OPENAI_API_KEY = os.getenv('OPENAI_API_KEY')

# OpenAI setup
client = OpenAI(api_key=OPENAI_API_KEY)

# Bot setup
intents = discord.Intents.default()
intents.message_content = True
intents.members = True
bot = commands.Bot(command_prefix='!', intents=intents)

# Data storage
class GameData:
    """Manage persistent game data and storage"""
    def __init__(self):
        self.characters = {}          # Store character data
        self.active_games = {}        # Track active game sessions
        self.game_states = {}         # Store current game states
        self.game_players = {}        # Track players in each game
        self.game_objectives = {}     # Track game objectives
        self.data_file = Path("game_data.json")
        self.story_messages = {}      # Track story message IDs for each channel
        self.story_history = {}       # Track story progression
        self.game_languages = {}      # Store language settings for each game
        self.load_data()

    def load_data(self):
        """Load game data from file"""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.characters = data.get('characters', {})
                self.active_games = data.get('active_games', {})
                self.game_states = data.get('game_states', {})
                self.game_players = data.get('game_players', {})
                self.game_objectives = data.get('game_objectives', {})
                self.story_history = data.get('story_history', {})
                self.game_languages = data.get('game_languages', {})

    def save_data(self):
        """Save game data to file"""
        with open(self.data_file, 'w') as f:
            json.dump({
                'characters': self.characters,
                'active_games': self.active_games,
                'game_states': self.game_states,
                'game_players': self.game_players,
                'game_objectives': self.game_objectives,
                'story_history': self.story_history,
                'game_languages': self.game_languages
            }, f, indent=4)

game_data = GameData()

# Update remaining Chinese comments and section headers to English
# Game type constants
GAME_TYPES = {
    "mystery": {"emoji": "🔮"},
    "murder": {"emoji": "🔪"},
    "horror": {"emoji": "👻"},
    "fantasy": {"emoji": "🐉"},
    "detective": {"emoji": "🔍"},
    "adventure": {"emoji": "⚔️"},
    "heist": {"emoji": "💎"},
    "survival": {"emoji": "🏕️"},
    "conspiracy": {"emoji": "🕵️"},
    "comedy": {"emoji": "😂"},
    "espionage": {"emoji": "🕴️"},
    "supernatural": {"emoji": "👥"},
    "historical": {"emoji": "📜"},
    "sci_fi": {"emoji": "🚀"},
    "psychological": {"emoji": "🧠"},
    "escape": {"emoji": "🚪"}
}

LANGUAGE_OPTIONS = {
    "🇺🇸": {"code": "en", "name": "English"},
    "🇹🇼": {"code": "zh", "name": "Traditional Chinese"},
    "🌐": {"code": "both", "name": "Bilingual"}
}

# Game categories
GAME_CATEGORIES = {
    "Mystery & Detective": ["mystery", "murder", "detective", "psychological", "conspiracy"],
    "Adventure & Action": ["adventure", "heist", "survival", "escape"],
    "Fantasy & Supernatural": ["fantasy", "supernatural", "horror", "sci_fi"],
    "Special Themes": ["historical", "espionage", "comedy"]
}

# Game type descriptions
GAME_TYPE_DESCRIPTIONS = {
    "mystery": "Solve complex mysteries and uncover hidden truths",
    "murder": "Investigate murders and find the killer",
    "detective": "Use deduction and evidence to solve cases",
    "psychological": "Explore psychological tensions and mind games",
    "conspiracy": "Uncover and navigate through intricate conspiracies",
    "adventure": "Embark on exciting journeys and face challenges",
    "heist": "Plan and execute elaborate heists",
    "survival": "Survive against harsh conditions or threats",
    "escape": "Find ways to escape from confined situations",
    "fantasy": "Experience magical and mythical adventures",
    "supernatural": "Deal with supernatural phenomena",
    "horror": "Face terrifying situations and creatures",
    "sci_fi": "Explore futuristic and technological scenarios",
    "historical": "Experience adventures in historical settings",
    "espionage": "Engage in spy missions and covert operations",
    "comedy": "Enjoy humorous situations and interactions"
}

# System message templates
SYSTEM_MESSAGES = {
    "game_in_progress": "A game is already in progress! Use !end_game to end the current game.",
    "not_enough_players": "Not enough players joined. Game initialization cancelled.",
    "player_joined": "{player_name} has joined the game!",
    "no_active_game": "No active game in this channel!",
    "no_story_history": "No story history available.",
    "game_ended": "Game session concluded",
    "language_selection": "Select Game Language",
    "no_language_selected": "No language selected, defaulting to bilingual mode.",
    "language_selected": "Selected language: {language}",
    "new_game_init": "New Game Initialization",
    "join_prompt": "React with 👍 to join the game! (Waiting for 2+ players)",
    "game_type_selection": "Choose Game Type",
    "vote_prompt": "React to vote! (10 seconds)",
    "game_type_descriptions": "Game Type Descriptions",
    "how_to_play": "How to Play",
    "game_complete": "Adventure Successfully Completed!",
    "objectives_met": "All objectives have been met! The game has ended.",
    "dm_error": "Couldn't send DM to {player_name}. Please enable DMs from server members."
}

# Game guide message
GAME_GUIDE = """
Simply type your character's actions and dialogue directly in the channel!
No need to use any commands for roleplay.

Available commands:
!scene - Review the current scene and objectives
!story - View story history
!end_game - End the game session
"""

# Translation helper functions
async def translate_text(text, to_lang='zh'):
    """Translate text between English and Traditional Chinese"""
    if not text or not isinstance(text, str):
        return text
        
    if to_lang not in ['zh', 'en']:
        return text

    try:
        prompt = f"""Translate the following {'English' if to_lang == 'zh' else 'Traditional Chinese'} text to {'Traditional Chinese' if to_lang == 'zh' else 'English'}.
Keep all formatting, emojis, and special characters unchanged.
Only translate the actual text content.

Text to translate:
{text}"""
        
        response = await get_ai_response(prompt)
        return response if isinstance(response, str) else text
    except Exception as e:
        print(f"Translation error: {e}")
        return text

def is_chinese(text):
    """Check if text contains Chinese characters"""
    # Method 1: Simple range check for Chinese unicode blocks
    for char in text:
        if '\u4e00' <= char <= '\u9fff':  # Basic Chinese characters
            return True
    return False

def detect_language(text):
    """
    Detect if text is primarily English or Chinese
    Returns: 'en', 'zh', or 'mixed'
    """
    if not text:
        return 'en'
        
    chinese_count = 0
    english_count = 0
    
    for char in text:
        # Skip spaces and punctuation
        if char.isspace() or unicodedata.category(char).startswith('P'):
            continue
            
        # Check for Chinese characters
        if '\u4e00' <= char <= '\u9fff':
            chinese_count += 1
        # Check for English characters
        elif char.isascii() and char.isalpha():
            english_count += 1
    
    # If no valid characters found
    if chinese_count == 0 and english_count == 0:
        return 'en'
    
    # Calculate ratio
    total = chinese_count + english_count
    chinese_ratio = chinese_count / total
    
    # Determine primary language
    if chinese_ratio > 0.7:  # More than 70% Chinese
        return 'zh'
    elif chinese_ratio < 0.3:  # More than 70% English
        return 'en'
    else:
        return 'mixed'

async def process_user_input(text, selected_lang):
    """Process user input based on selected language"""
    input_lang = detect_language(text)
    
    # If input is Chinese, translate to English
    if input_lang == 'zh' or input_lang == 'mixed':
        return await translate_text(text, to_lang='en')
    return text

async def format_output(text, selected_lang):
    """Format output based on selected language"""
    if not text or not isinstance(text, str):
        return text
        
    if selected_lang not in ['en', 'zh', 'both']:
        return text

    MAX_LENGTH = 2000  # Discord's message length limit

    if not text:
        return text

    def split_text(content):
        """Split text into parts that respect paragraph boundaries"""
        parts = []
        current_part = ""
        paragraphs = content.split('\n\n')
        
        for paragraph in paragraphs:
            if len(current_part) + len(paragraph) + 2 <= MAX_LENGTH:
                current_part += (paragraph + '\n\n')
            else:
                if current_part:
                    parts.append(current_part.strip())
                current_part = paragraph + '\n\n'
        if current_part:
            parts.append(current_part.strip())
        return parts

    if selected_lang == 'zh':
        # Translate to Chinese and split if needed
        translated = await translate_text(text, to_lang='zh')
        if len(translated) > MAX_LENGTH:
            return split_text(translated)
        return translated
        
    elif selected_lang == 'both':
        # Handle both languages
        zh_text = await translate_text(text, to_lang='zh')
        
        # Split both texts if either is too long
        if len(text) > MAX_LENGTH // 2 or len(zh_text) > MAX_LENGTH // 2:
            en_parts = split_text(text)
            zh_parts = split_text(zh_text)
            
            # Combine corresponding parts
            combined_parts = []
            max_parts = max(len(en_parts), len(zh_parts))
            
            for i in range(max_parts):
                en_part = en_parts[i] if i < len(en_parts) else ""
                zh_part = zh_parts[i] if i < len(zh_parts) else ""
                combined = f"{en_part}\n\n{zh_part}".strip()
                combined_parts.append(combined)
            
            return combined_parts
            
        return f"{text}\n\n{zh_text}"
    
    # For English, split if needed
    if len(text) > MAX_LENGTH:
        return split_text(text)
    return text

# Message handling functions
async def send_message(ctx, content, title=None, color=None):
    """Send a message in the appropriate language format"""
    if not ctx:
        print("Error: No context provided")
        return
        
    if not content:
        print("Warning: Empty content")
        content = "No content available"

    try:
        MAX_EMBEDS = 25   # Discord's embed limit per message
        
        # Get channel ID and language setting
        if isinstance(ctx, discord.TextChannel):
            channel_id = str(ctx.id)
        elif isinstance(ctx, discord.User) or isinstance(ctx, discord.Member):
            channel_id = None
        else:
            channel_id = str(ctx.channel.id)
        
        selected_lang = game_data.game_languages.get(channel_id, 'both') if channel_id else 'en'
        
        # Format content and title
        formatted_content = await format_output(content, selected_lang)
        formatted_title = await format_output(title, selected_lang) if title else None
        
        # Handle content as list or single string
        if isinstance(formatted_content, list):
            parts = formatted_content
        else:
            parts = [formatted_content]
        
        # Validate parts before sending
        if not isinstance(parts, list):
            parts = [str(parts)]
            
        for part in parts:
            if not isinstance(part, str):
                part = str(part)
        
        # Send parts in batches
        current_batch = []
        batch_number = 1
        total_batches = (len(parts) + MAX_EMBEDS - 1) // MAX_EMBEDS
        
        for i, part in enumerate(parts):
            if selected_lang == 'zh':
                part_title = f"{formatted_title} (第{i+1}/{len(parts)}部分)" if formatted_title else f"第{i+1}/{len(parts)}部分"
            else:
                part_title = f"{formatted_title} (Part {i+1}/{len(parts)})" if formatted_title else f"Part {i+1}/{len(parts)}"
            
            embed = discord.Embed(
                title=part_title,
                description=part,
                color=color or discord.Color.blue()
            )
            current_batch.append(embed)
            
            if len(current_batch) >= MAX_EMBEDS or i == len(parts) - 1:
                if total_batches > 1:
                    batch_msg = "批次" if selected_lang == 'zh' else "Batch"
                    await ctx.send(f"{batch_msg} {batch_number}/{total_batches}")
                if isinstance(ctx, (discord.TextChannel, discord.User, discord.Member)):
                    await ctx.send(embeds=current_batch)
                else:
                    await ctx.send(embeds=current_batch)
                current_batch = []
                batch_number += 1
    except Exception as e:
        print(f"Error in send_message: {e}")
        try:
            await ctx.send("Error: Could not send message")
        except:
            print("Could not send error message")

@bot.event
async def on_ready():
    """Log when bot successfully connects to Discord"""
    print(f'{bot.user} has connected to Discord!')

# Update class comments and structure
class GameSetupState:
    """Manage game setup state and temporary data"""
    def __init__(self):
        self.waiting_for_players = {}  # Track channels waiting for players
        self.joined_players = {}       # Track joined players for each channel
        self.game_type = {}           # Store selected game type for each channel

setup_state = GameSetupState()

# 修改 start_game 命令
@bot.command(name='start_game')
async def start_game(ctx):
    """Start the game initialization process"""
    channel_id = str(ctx.channel.id)
    
    if channel_id in game_data.active_games:
        msg = SYSTEM_MESSAGES["game_in_progress"]
        await send_message(ctx, msg)
        return

    setup_state.waiting_for_players[channel_id] = True
    setup_state.joined_players[channel_id] = []
    
    # Create join prompt message
    await send_message(
        ctx,
        SYSTEM_MESSAGES["join_prompt"],
        title=SYSTEM_MESSAGES["new_game_init"],
        color=discord.Color.blue()
    )
    
    message = await ctx.send("👍")
    await message.add_reaction('👍')
    
    # Wait for 10 seconds to collect players
    await asyncio.sleep(10)
    
    if channel_id in setup_state.waiting_for_players:
        player_count = len(setup_state.joined_players[channel_id])
        if player_count < 2:
            await send_message(ctx, SYSTEM_MESSAGES["not_enough_players"])
            cleanup_setup_state(channel_id)
            return
        
        # Create game type voting message
        game_types_str = "**🎲 " + SYSTEM_MESSAGES["game_type_selection"] + "**\n\n"
        
        for category, types in GAME_CATEGORIES.items():
            game_types_str += f"**{category}**\n"
            for game_type in types:
                info = GAME_TYPES[game_type]
                game_types_str += f"{info['emoji']} {game_type.capitalize()}\n"
            game_types_str += "\n"

        embed = discord.Embed(
            title=SYSTEM_MESSAGES["game_type_selection"],
            description=f"{SYSTEM_MESSAGES['vote_prompt']}\n\n{game_types_str}",
            color=discord.Color.green()
        )
        
        # Add game type descriptions
        selected_lang = game_data.game_languages.get(str(ctx.channel.id), 'both')
        descriptions = "\n".join(
            f"{GAME_TYPES[t]['emoji']} **{t.capitalize()}**: {GAME_TYPE_DESCRIPTIONS[t]}"
            for t in GAME_TYPES
        )
        embed.add_field(
            name=SYSTEM_MESSAGES["game_type_descriptions"],
            value=descriptions,
            inline=False
        )

        vote_msg = await ctx.send(embed=embed)
        
        # Add reactions for voting
        for game_type in GAME_TYPES.values():
            await vote_msg.add_reaction(game_type['emoji'])
        
        # Wait for 10 seconds
        await asyncio.sleep(10)
        
        # Process voting results
        vote_msg = await ctx.channel.fetch_message(vote_msg.id)
        vote_counts = {}
        for game_type, info in GAME_TYPES.items():
            for reaction in vote_msg.reactions:
                if str(reaction.emoji) == info['emoji']:
                    vote_counts[game_type] = reaction.count - 1

        # Handle voting results
        if not vote_counts:
            winning_type = random.choice(list(GAME_TYPES.keys()))
            await send_message(
                ctx,
                f"No votes received. Randomly selected: {GAME_TYPES[winning_type]['emoji']} {winning_type.capitalize()}"
            )
        else:
            max_votes = max(vote_counts.values())
            winners = [t for t, v in vote_counts.items() if v == max_votes]
            
            if len(winners) > 1:
                winning_type = random.choice(winners)
                await send_message(
                    ctx,
                    f"Tie detected! Randomly selected from highest votes: {GAME_TYPES[winning_type]['emoji']} {winning_type.capitalize()}"
                )
            else:
                winning_type = winners[0]
                await send_message(
                    ctx,
                    f"Selected game type: {GAME_TYPES[winning_type]['emoji']} {winning_type.capitalize()}"
                )
        
        setup_state.game_type[channel_id] = winning_type
        await start_game_session(ctx, channel_id)

# 修改 on_reaction_add 事件
@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
        
    channel_id = str(reaction.message.channel.id)
    if channel_id in setup_state.waiting_for_players and reaction.emoji == '👍':
        if user.id not in setup_state.joined_players[channel_id]:
            setup_state.joined_players[channel_id].append(user.id)
            await send_message(
                reaction.message.channel,  # Use the channel directly
                SYSTEM_MESSAGES["player_joined"].format(player_name=user.name)
            )

# Message splitting helper
async def send_long_message(ctx, content, title=None, color=None):
    """Split and send long messages"""
    MAX_LENGTH = 1000
    selected_lang = game_data.game_languages.get(str(ctx.channel.id), 'both')
    
    # Translate content if needed
    content = await format_output(content, selected_lang)
    if title:
        title = await format_output(title, selected_lang)
    
    if len(content) <= MAX_LENGTH:
        await send_message(ctx, content, title, color)
        return

    # Split content
    parts = []
    while content:
        if len(content) <= MAX_LENGTH:
            parts.append(content)
            break
        
        split_point = content[:MAX_LENGTH].rfind('\n')
        if split_point == -1:
            split_point = MAX_LENGTH
        
        parts.append(content[:split_point])
        content = content[split_point:].lstrip()

    # Send parts
    for i, part in enumerate(parts):
        part_title = f"{title} (Part {i+1}/{len(parts)})" if title else f"Part {i+1}/{len(parts)}"
        await send_message(ctx, part, part_title, color)

async def start_game_session(ctx, channel_id):
    """Initialize and start a new game session"""
    game_type = setup_state.game_type[channel_id]
    
    # Language selection
    language_embed = discord.Embed(
        title=SYSTEM_MESSAGES["language_selection"],
        description="""Choose your preferred language:

🇺🇸 - English only
🇹🇼 - Traditional Chinese only
🌐 - Bilingual (English + Traditional Chinese)

React to select! (10 seconds)""",
        color=discord.Color.blue()
    )
    lang_msg = await ctx.send(embed=language_embed)
    
    # Add language selection reactions
    for emoji in LANGUAGE_OPTIONS.keys():
        await lang_msg.add_reaction(emoji)
    
    # Wait for 10 seconds
    await asyncio.sleep(10)
    
    # Get updated message to count reactions
    lang_msg = await ctx.channel.fetch_message(lang_msg.id)
    
    # Count language votes
    lang_votes = {}
    for emoji, lang_info in LANGUAGE_OPTIONS.items():
        for reaction in lang_msg.reactions:
            if str(reaction.emoji) == emoji:
                lang_votes[lang_info['code']] = reaction.count - 1

    # Select language based on votes
    if not lang_votes:
        selected_lang = 'both'  # Default to bilingual
        await send_message(ctx, SYSTEM_MESSAGES["no_language_selected"])
    else:
        selected_lang = max(lang_votes.items(), key=lambda x: x[1])[0]
        lang_name = next(info['name'] for info in LANGUAGE_OPTIONS.values() if info['code'] == selected_lang)
        await send_message(
            ctx,
            SYSTEM_MESSAGES["language_selected"].format(language=lang_name)
        )
    
    # Store selected language
    game_data.game_languages[channel_id] = selected_lang

    # Generate initial story and objectives
    story_prompt = f"""Create a {game_type} LARP game scenario with the following structure:

[OBJECTIVE]
Create a clear, specific main objective that players need to accomplish.
Include 3-5 specific requirements that must be met to complete the objective.

[BACKGROUND]
Write an engaging background story that sets up the scenario.

[CURRENT_SITUATION]
Describe the immediate situation players find themselves in.

Format the response with clear section headers."""

    initial_story = await get_larp_response(story_prompt)
    
    # Extract objectives and requirements
    objective_prompt = f"""From the following story setup, extract:
1. The main objective
2. The specific requirements to complete it

Story:
{initial_story}

Format as JSON:
{{
    "main_objective": "clear objective statement",
    "key_requirements": [
        "requirement 1",
        "requirement 2",
        "requirement 3"
    ]
}}"""

    objectives_response = await get_larp_response(objective_prompt)
    try:
        objective = {}
        if isinstance(objectives_response, str):
            if objectives_response.startswith("```json") and objectives_response.endswith("```"):
                objectives = json.loads(objectives_response[8:-3].strip())  # Remove the markers and strip whitespace
            else:
                objectives = json.loads(objectives_response)
        else:
            raise ValueError("Invalid response format")

        game_data.game_states[channel_id] = {
            'current_scene': initial_story,
            'progress': 0,
            'completed_objectives': [],
            'main_objective': objectives['main_objective'],
            'key_requirements': objectives['key_requirements']
        }
    except (json.JSONDecodeError, ValueError) as e:
        print(f"Error parsing objectives JSON: {str(e)}")
        game_data.game_states[channel_id] = {
            'current_scene': initial_story,
            'progress': 0,
            'completed_objectives': [],
            'main_objective': "Error extracting objective",
            'key_requirements': []
        }

    # Send initial story
    await send_message(
        ctx,
        initial_story,
        title="New Adventure Begins",
        color=discord.Color.gold()
    )

    # Generate and send character roles
    await generate_character_roles(ctx, channel_id, game_type)

    # Initialize game state
    game_data.story_history[channel_id] = []
    game_data.active_games[channel_id] = True
    game_data.game_players[channel_id] = setup_state.joined_players[channel_id]
    game_data.save_data()

# Character generation helper
async def generate_character_roles(ctx, channel_id, game_type):
    """Generate and send character roles to players"""
    selected_lang = game_data.game_languages.get(channel_id, 'both')
    
    for player_id in setup_state.joined_players[channel_id]:
        user = await bot.fetch_user(player_id)
        role_prompt = f"""Create a character role for a {game_type} story.
Include:
- Character name and description
- 2-3 unique abilities or skills
- Personal motivation
- Suggested roleplay style
Format with clear sections."""

        role_info = await get_larp_response(role_prompt)
        try:
            # Create and send embed directly
            embed = discord.Embed(
                title="Your Character Role",
                description=await format_output(role_info, selected_lang),
                color=discord.Color.blue()
            )
            await user.send(embed=embed)
        except discord.Forbidden:
            await send_message(
                ctx.channel,  # Use the channel from context
                SYSTEM_MESSAGES["dm_error"].format(player_name=user.name)
            )

# AI response handler
async def get_ai_response(prompt):
    """Get response from OpenAI API"""
    try:
        messages = [
            {"role": "user", "content": prompt}
        ]

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
            max_tokens=2000,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        return "Error: Unable to generate response. Please try again."

# LARP AI response handler
async def get_larp_response(prompt, game_state=None):
    """Get larp response from OpenAI API"""
    try:
        system_prompt = """You are an experienced LARP game master. 
Create engaging narratives and respond to player actions.
Keep responses focused and relevant to the current scene and objective.
Use descriptive language and maintain consistent story elements."""

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt}
        ]
        
        if game_state:
            messages.insert(1, {
                "role": "system", 
                "content": f"Current game state: {game_state}"
            })

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
            max_tokens=600,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        return "Error: Unable to generate response. Please try again."

# Game state cleanup
def cleanup_setup_state(channel_id):
    """Clean up setup state for a channel"""
    if channel_id in setup_state.waiting_for_players:
        del setup_state.waiting_for_players[channel_id]
    if channel_id in setup_state.joined_players:
        del setup_state.joined_players[channel_id]
    if channel_id in setup_state.game_type:
        del setup_state.game_type[channel_id]

@bot.command(name='end_game')
async def end_game(ctx):
    """End the current game session"""
    channel_id = str(ctx.channel.id)
    if channel_id not in game_data.active_games:
        await send_message(ctx, SYSTEM_MESSAGES["no_active_game"])
        return

    prompt = "Create a satisfying conclusion for the current scene, wrapping up any immediate plot points."
    conclusion = await get_larp_response(prompt, game_data.game_states[channel_id])

    del game_data.active_games[channel_id]
    del game_data.game_states[channel_id]
    game_data.save_data()

    await send_message(
        ctx,
        conclusion,
        title=SYSTEM_MESSAGES["game_ended"],
        color=discord.Color.red()
    )

@bot.command(name='scene')
async def get_current_scene(ctx):
    """Display the current scene description"""
    channel_id = str(ctx.channel.id)
    if channel_id not in game_data.active_games:
        await send_message(ctx, SYSTEM_MESSAGES["no_active_game"])
        return

    current_state = game_data.game_states[channel_id]
    await send_message(
        ctx,
        current_state['current_scene'],
        title="Current Scene",
        color=discord.Color.blue()
    )

@bot.command(name='story')
async def show_story(ctx):
    """Display the full story history"""
    channel_id = str(ctx.channel.id)
    if channel_id not in game_data.active_games:
        await send_message(ctx, SYSTEM_MESSAGES["no_active_game"])
        return

    if channel_id not in game_data.story_history:
        await send_message(ctx, SYSTEM_MESSAGES["no_story_history"])
        return

    story_text = "**📖 Story History**\n\n"
    for event in game_data.story_history[channel_id]:
        story_text += f"\n👤 **{event['actor']}**: {event['action']}\n"
        story_text += f"➡️ {event['result']}\n"

    await send_long_message(ctx, story_text, color=discord.Color.blue())

async def update_story_message(ctx, channel_id, new_content, action=None, actor=None):
    """Update the story message with new content"""
    if channel_id not in game_data.story_history:
        game_data.story_history[channel_id] = []

    # Add new story event
    if action and actor:
        game_data.story_history[channel_id].append({
            'action': action,
            'actor': actor,
            'result': new_content
        })

    # Create story summary
    story_summary = "**🎭 Story Progress**\n\n"
    story_summary += "**Recent Events:**\n"
    
    # Add last event
    for event in game_data.story_history[channel_id][-1:]:
        story_summary += f"\n👤 **{event['actor']}**: {event['action']}\n"
        story_summary += f"➡️ {event['result']}\n"
    
    story_summary += "\n**Current Scene:**\n"
    # Check if current_scene is a string before concatenation
    if isinstance(game_data.game_states[channel_id]['current_scene'], str):
        story_summary += game_data.game_states[channel_id]['current_scene']
    else:
        story_summary += "Current scene data is not available."

    await send_message(
        ctx,
        story_summary,
        title="Story Progress",
        color=discord.Color.blue()
    )

# 添加新的事件監聽器來處理一般訊息
@bot.event
async def on_message(message):
    # Ensure we don't process bot's own messages
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    user_id = str(message.author.id)

    # Check if there's an active game in the channel
    if channel_id in game_data.active_games:
        # Check if the speaker is a game participant
        if user_id in [str(pid) for pid in game_data.game_players[channel_id]]:
            # Ignore command prefix messages, let them be handled by process_commands
            if not message.content.startswith('!'):
                await process_action(message)
    
    # Ensure commands still work
    await bot.process_commands(message)

async def process_action(message):
    """Process player's roleplay action"""
    if not message or not message.content:
        return
        
    channel_id = str(message.channel.id)
    
    # Validate game state
    if channel_id not in game_data.active_games:
        return
    if channel_id not in game_data.game_states:
        game_data.active_games.pop(channel_id, None)
        return
        
    current_state = game_data.game_states[channel_id]
    if not isinstance(current_state, dict):
        print(f"Invalid game state for channel {channel_id}")
        return
        
    selected_lang = game_data.game_languages.get(channel_id, 'both')
    
    # Translate user input if needed
    action_text = await process_user_input(message.content, selected_lang)
    
    completion_check_prompt = f"""
Player action: {action_text}
Current scene: {current_state['current_scene']}

Main objective: {current_state['main_objective']}
Required conditions: {current_state['key_requirements']}

Strictly evaluate if this action contributes to or completes the objective.
1. Check each requirement carefully
2. Only mark as complete if ALL requirements are fully met
3. If complete, explain how each requirement was met
4. If not complete, explain what's still missing

If ALL requirements are met, start response with [GAME_COMPLETE]
Otherwise, evaluate the action and progress normally.
"""

    response = await get_larp_response(completion_check_prompt, current_state)
    formatted_response = await format_output(response, selected_lang)
    
    if isinstance(formatted_response, str) and formatted_response.startswith("[GAME_COMPLETE]"):
        await handle_game_completion(message.channel, channel_id, formatted_response)
        
        await send_message(
            message.channel,
            SYSTEM_MESSAGES["objectives_met"].format(
                objective=current_state['main_objective']
            ),
            title=SYSTEM_MESSAGES["game_complete"],
            color=discord.Color.gold()
        )
        
        # Clean up game state
        del game_data.active_games[channel_id]
        del game_data.game_states[channel_id]
        del game_data.game_players[channel_id]
        if channel_id in game_data.game_objectives:
            del game_data.game_objectives[channel_id]
        game_data.save_data()
    else:
        current_state['current_scene'] = formatted_response
        await update_story_message(
            message.channel, 
            channel_id, 
            formatted_response, 
            action_text, 
            message.author.name
        )
        await send_message(
            message.channel,
            formatted_response,
            title="Roleplay Response",
            color=discord.Color.green()
        )

async def handle_game_completion(ctx, channel_id, final_scene):
    """Handle game completion and cleanup"""
    if not ctx or not channel_id:
        return
        
    try:
        selected_lang = game_data.game_languages.get(channel_id, 'both')
        
        # Ensure final_scene is a string before using replace
        final_content = final_scene.replace("[GAME_COMPLETE]", "") if isinstance(final_scene, str) else str(final_scene)
        
        await send_message(
            ctx,
            final_content,
            title=SYSTEM_MESSAGES["game_complete"],
            color=discord.Color.gold()
        )
        
        # Clean up game state with checks
        game_data.active_games.pop(channel_id, None)
        game_data.game_states.pop(channel_id, None)
        game_data.game_players.pop(channel_id, None)
        game_data.game_objectives.pop(channel_id, None)
        
        game_data.save_data()
    except Exception as e:
        print(f"Error in handle_game_completion: {e}")
        try:
            await ctx.send("Error: Could not complete game properly")
        except:
            print("Could not send error message")

if __name__ == "__main__":
    bot.run(TOKEN) 