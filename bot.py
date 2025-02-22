import os
import discord
from discord.ext import commands
from dotenv import load_dotenv
import json
from pathlib import Path
from openai import OpenAI
import asyncio
import random

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
    def __init__(self):
        self.characters = {}
        self.active_games = {}
        self.game_states = {}
        self.game_players = {}  # Track players in each game
        self.game_objectives = {}  # Track game objectives
        self.data_file = Path("game_data.json")
        self.story_messages = {}  # Track story message IDs for each channel
        self.story_history = {}   # Track story progression
        self.game_languages = {}  # 儲存每個遊戲的語言設置
        self.load_data()

    def load_data(self):
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

GAME_TYPES = {
    "scary": {"name": "恐怖", "emoji": "👻"},
    "funny": {"name": "搞笑", "emoji": "😂"},
    "puzzle": {"name": "解謎", "emoji": "🔍"},
    "adventure": {"name": "冒險", "emoji": "⚔️"},
    "mystery": {"name": "神秘", "emoji": "🔮"},
    "fantasy": {"name": "奇幻", "emoji": "🐉"}
}

class GameSetupState:
    def __init__(self):
        self.waiting_for_players = {}  # channel_id: expiry_time
        self.collecting_preferences = {}  # channel_id: True/False
        self.player_count = {}  # channel_id: count
        self.joined_players = {}  # channel_id: [user_ids]
        self.game_type = {}  # channel_id: type

setup_state = GameSetupState()

# 添加語言選項常數
LANGUAGE_OPTIONS = {
    "🇺🇸": {"code": "en", "name": "English"},
    "🇹🇼": {"code": "zh", "name": "繁體中文"},
    "🌐": {"code": "both", "name": "English + 繁體中文"}
}

async def get_ai_response(prompt, game_state=None):
    try:
        messages = [
            {"role": "system", "content": """你是一位經驗豐富的LARP遊戲主持人。創造引人入勝的敘事並回應玩家行動。
            請使用繁體中文回應，格式如下：
            
            [EN]
            (English response here)
            
            [繁中]
            (繁體中文回應)
            """},
            {"role": "user", "content": prompt}
        ]
        
        if game_state:
            messages.insert(1, {"role": "system", "content": f"Current game state: {game_state}"})

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
            max_tokens=600,  # Increased for dual-language response
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")  # Debug print
        return """Error: Unable to generate story. Please try again in a moment.
        
        錯誤：無法生成故事。請稍後再試。"""

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='create_character')
async def create_character(ctx, character_name: str):
    user_id = str(ctx.author.id)
    if user_id in game_data.characters:
        await ctx.send("You already have a character! Use !delete_character first to create a new one.\n你已經有一個角色了！請先使用 !delete_character 刪除現有角色。")
        return

    game_data.characters[user_id] = {
        'name': character_name,
        'stats': {
            'strength': 10,
            'dexterity': 10,
            'constitution': 10,
            'intelligence': 10,
            'wisdom': 10,
            'charisma': 10
        },
        'inventory': [],
        'health': 100
    }
    game_data.save_data()
    await ctx.send(f"Character '{character_name}' created successfully!\n角色 '{character_name}' 創建成功！")

@bot.command(name='stats')
async def show_stats(ctx):
    user_id = str(ctx.author.id)
    if user_id not in game_data.characters:
        await ctx.send("You don't have a character yet! Use !create_character to make one.\n你還沒有角色！請使用 !create_character 創建一個。")
        return

    character = game_data.characters[user_id]
    stats_message = f"**{character['name']}'s Stats | {character['name']}的屬性:**\n"
    
    stat_translations = {
        'strength': '力量',
        'dexterity': '敏捷',
        'constitution': '體質',
        'intelligence': '智力',
        'wisdom': '智慧',
        'charisma': '魅力'
    }
    
    for stat, value in character['stats'].items():
        stats_message += f"{stat.capitalize()} | {stat_translations[stat]}: {value}\n"
    stats_message += f"Health | 生命值: {character['health']}"
    
    await ctx.send(stats_message)

@bot.command(name='inventory')
async def show_inventory(ctx):
    user_id = str(ctx.author.id)
    if user_id not in game_data.characters:
        await ctx.send("You don't have a character yet! Use !create_character to make one.")
        return

    character = game_data.characters[user_id]
    if not character['inventory']:
        await ctx.send(f"{character['name']}'s inventory is empty!")
    else:
        inventory_list = "\n".join(character['inventory'])
        await ctx.send(f"**{character['name']}'s Inventory:**\n{inventory_list}")

@bot.command(name='roll')
async def roll_dice(ctx, skill: str):
    import random
    user_id = str(ctx.author.id)
    if user_id not in game_data.characters:
        await ctx.send("You don't have a character yet! Use !create_character to make one.")
        return

    character = game_data.characters[user_id]
    if skill.lower() not in character['stats']:
        await ctx.send(f"Invalid skill! Available skills: {', '.join(character['stats'].keys())}")
        return

    base_stat = character['stats'][skill.lower()]
    roll = random.randint(1, 20)
    total = roll + (base_stat - 10) // 2

    await ctx.send(f"{character['name']} rolled for {skill}: {roll} + {(base_stat - 10) // 2} = {total}")

@bot.command(name='start_game')
async def start_game(ctx):
    """Start the game initialization process"""
    channel_id = str(ctx.channel.id)
    
    if channel_id in game_data.active_games:
        await ctx.send("A game is already in progress! Use !force_restart to start a new game.\n遊戲已經在進行中！使用 !force_restart 來開始新遊戲。")
        return

    setup_state.waiting_for_players[channel_id] = True
    setup_state.joined_players[channel_id] = []
    
    embed = discord.Embed(
        title="New Game Initialization | 新遊戲初始化",
        description="React with 👍 to join the game! (Waiting for 2-6 players)\n按 👍 加入遊戲！（需要2-6名玩家）",
        color=discord.Color.blue()
    )
    
    message = await ctx.send(embed=embed)
    await message.add_reaction('👍')
    
    # Wait for 10 seconds to collect players
    await asyncio.sleep(10)
    
    if channel_id in setup_state.waiting_for_players:
        player_count = len(setup_state.joined_players[channel_id])
        if player_count < 2:
            await ctx.send("Not enough players joined. Game initialization cancelled.\n玩家數量不足。遊戲初始化取消。")
            cleanup_setup_state(channel_id)
            return
        
        # Create game type voting message
        game_types_str = "\n".join([f"{info['emoji']} {k.capitalize()}: {info['name']}" for k, info in GAME_TYPES.items()])
        embed = discord.Embed(
            title="Vote for Game Type | 投票選擇遊戲類型",
            description=f"React to vote! (10 seconds)\n請投票！（10秒）\n\n{game_types_str}",
            color=discord.Color.green()
        )
        vote_msg = await ctx.send(embed=embed)
        
        # Add reactions for voting
        for game_type in GAME_TYPES.values():
            await vote_msg.add_reaction(game_type['emoji'])
        
        # Wait for 10 seconds
        await asyncio.sleep(10)
        
        # Fetch updated message to get reaction counts
        vote_msg = await ctx.channel.fetch_message(vote_msg.id)
        
        # Count votes
        vote_counts = {}
        for game_type, info in GAME_TYPES.items():
            for reaction in vote_msg.reactions:
                if str(reaction.emoji) == info['emoji']:
                    vote_counts[game_type] = reaction.count - 1  # Subtract 1 to exclude bot's reaction
        
        # 處理投票結果
        if not vote_counts:  # 沒有人投票
            winning_type = random.choice(list(GAME_TYPES.keys()))
            await ctx.send(f"No votes received. Randomly selected: {GAME_TYPES[winning_type]['emoji']} {winning_type.capitalize()} | 沒有收到投票。隨機選擇：{GAME_TYPES[winning_type]['name']}")
        else:
            # 找出最高票數
            max_votes = max(vote_counts.values())
            # 找出所有得到最高票的類型
            winners = [t for t, v in vote_counts.items() if v == max_votes]
            
            if len(winners) > 1:  # 平票情況
                winning_type = random.choice(winners)
                await ctx.send(f"Tie detected! Randomly selected from highest votes: {GAME_TYPES[winning_type]['emoji']} {winning_type.capitalize()} | 平票！從最高票數中隨機選擇：{GAME_TYPES[winning_type]['name']}")
            else:
                winning_type = winners[0]
                await ctx.send(f"Selected game type: {GAME_TYPES[winning_type]['emoji']} {winning_type.capitalize()} | 選擇的遊戲類型：{GAME_TYPES[winning_type]['name']}")
        
        setup_state.game_type[channel_id] = winning_type
        await start_game_session(ctx, channel_id)

@bot.event
async def on_reaction_add(reaction, user):
    if user.bot:
        return
        
    channel_id = str(reaction.message.channel.id)
    if channel_id in setup_state.waiting_for_players and reaction.emoji == '👍':
        if user.id not in setup_state.joined_players[channel_id]:
            setup_state.joined_players[channel_id].append(user.id)
            await reaction.message.channel.send(f"{user.name} has joined the game! | {user.name} 已加入遊戲！")

@bot.command(name='set_type')
async def set_game_type(ctx, game_type: str):
    await ctx.send("Game type is now selected through voting! Use !start_game to begin.\n遊戲類型現在通過投票選擇！使用 !start_game 開始。")

# 添加一個分割訊息的輔助函數
async def send_long_message(ctx, content, title=None, color=None, is_embed=True):
    """將長訊息分割成多個部分發送"""
    # Discord 嵌入訊息描述的字符限制是 4096，我們使用 2000 作為安全值
    MAX_LENGTH = 2000
    
    # 如果內容很短，直接發送
    if len(content) <= MAX_LENGTH:
        if is_embed:
            embed = discord.Embed(
                title=title,
                description=content,
                color=color or discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(content)
        return

    # 分割內容
    parts = []
    while content:
        # 尋找適當的分割點
        if len(content) <= MAX_LENGTH:
            parts.append(content)
            break
        
        # 在最大長度位置之前尋找最後的換行符
        split_point = content[:MAX_LENGTH].rfind('\n')
        if split_point == -1:  # 如果找不到換行符，就在最大長度處分割
            split_point = MAX_LENGTH
        
        parts.append(content[:split_point])
        content = content[split_point:].lstrip()

    # 發送每個部分
    for i, part in enumerate(parts):
        if is_embed:
            embed = discord.Embed(
                title=f"{title} (Part {i+1}/{len(parts)})" if title else f"Part {i+1}/{len(parts)}",
                description=part,
                color=color or discord.Color.blue()
            )
            await ctx.send(embed=embed)
        else:
            await ctx.send(f"```Part {i+1}/{len(parts)}:\n{part}```")

async def start_game_session(ctx, channel_id):
    game_type = setup_state.game_type[channel_id]
    players = setup_state.joined_players[channel_id]
    
    # 首先選擇語言
    language_embed = discord.Embed(
        title="Select Game Language | 選擇遊戲語言",
        description="""
🇺🇸 - English only
🇹🇼 - 僅使用繁體中文
🌐 - Both English and Traditional Chinese | 同時使用英文與繁體中文

React to choose | 請點擊表情符號選擇
""",
        color=discord.Color.blue()
    )
    lang_msg = await ctx.send(embed=language_embed)
    
    # 添加語言選項反應
    for emoji in LANGUAGE_OPTIONS.keys():
        await lang_msg.add_reaction(emoji)
    
    # 等待10秒讓玩家選擇語言
    await asyncio.sleep(10)
    
    # 獲取更新後的訊息以計算反應數
    lang_msg = await ctx.channel.fetch_message(lang_msg.id)
    
    # 計算語言投票
    lang_votes = {}
    for emoji, lang_info in LANGUAGE_OPTIONS.items():
        for reaction in lang_msg.reactions:
            if str(reaction.emoji) == emoji:
                lang_votes[lang_info['code']] = reaction.count - 1

    # 選擇語言
    if not lang_votes:  # 沒有投票
        selected_lang = 'both'  # 預設使用雙語
        await ctx.send("No language selected, defaulting to bilingual mode.\n未選擇語言，預設使用雙語模式。")
    else:
        selected_lang = max(lang_votes.items(), key=lambda x: x[1])[0]
        lang_name = next(info['name'] for info in LANGUAGE_OPTIONS.values() if info['code'] == selected_lang)
        await ctx.send(f"Selected language: {lang_name}\n選擇的語言：{lang_name}")
    
    game_data.game_languages[channel_id] = selected_lang

    # 根據選擇的語言修改提示
    if selected_lang == 'en':
        prompt = f"""Create a {game_type} LARP game scenario with the following structure:

[OBJECTIVE]
Create a clear, specific main objective that players need to accomplish

[BACKGROUND]
Write an engaging background story that sets up the scenario

[CURRENT_SITUATION]
Describe the immediate situation players find themselves in
"""
    elif selected_lang == 'zh':
        prompt = f"""請創建一個{GAME_TYPES[game_type]['name']}類型的LARP遊戲場景，包含以下結構：

[任務目標]
創建一個明確的具體目標，讓玩家需要完成

[背景故事]
撰寫一個引人入勝的背景故事

[當前情況]
描述玩家目前所處的情境
"""
    else:  # both
        prompt = f"""Create a {game_type} LARP game scenario with the following structure:

[EN]
OBJECTIVE:
(Clear objective statement)

BACKGROUND:
(Background story)

CURRENT SITUATION:
(Current scene description)

[繁中]
任務目標：
(明確的目標說明)

背景故事：
(背景故事)

當前情況：
(當前場景描述)
"""

    response = await get_ai_response(prompt)
    game_data.game_states[channel_id] = {
        'current_scene': response,
        'progress': 0,
        'completed_objectives': []
    }
    
    # 發送初始故事
    await send_long_message(
        ctx,
        response,
        title="🎮 New Adventure Begins | 新冒險開始",
        color=discord.Color.gold()
    )
    
    # 為每個玩家生成角色
    for player_id in players:
        user = await bot.fetch_user(player_id)
        
        # 根據選擇的語言設定角色生成提示
        if selected_lang == 'en':
            role_prompt = f"""Create a character role for a {game_type} story with the following structure:

[CHARACTER]
- Name and basic description
- Special abilities or skills (2-3 unique abilities)
- Personal motivation related to the main objective
- Suggested play style

Respond in English only."""

        elif selected_lang == 'zh':
            role_prompt = f"""為{GAME_TYPES[game_type]['name']}類型的故事創建一個角色，包含以下結構：

[角色]
- 姓名和基本描述
- 特殊能力或技能（2-3個獨特能力）
- 與主要目標相關的個人動機
- 建議的扮演方式

請只使用繁體中文回應。"""

        else:  # both
            role_prompt = f"""Create a character role for a {game_type} story with the following structure:

[EN]
CHARACTER:
- Name and basic description
- Special abilities or skills (2-3 unique abilities)
- Personal motivation related to the main objective
- Suggested play style

[繁中]
角色：
- 姓名和基本描述
- 特殊能力或技能（2-3個獨特能力）
- 與主要目標相關的個人動機
- 建議的扮演方式

Provide response in both English and Traditional Chinese."""

        role_info = await get_ai_response(role_prompt)
        try:
            await send_long_message(
                user,  # 注意這裡是發送給用戶的私訊
                role_info,
                title="🎭 Your Character | 你的角色",
                color=discord.Color.blue()
            )
        except discord.Forbidden:
            error_msg = {
                'en': f"Couldn't send DM to {user.name}. Please enable DMs from server members.",
                'zh': f"無法向 {user.name} 發送私訊。請啟用伺服器成員的私訊功能。",
                'both': f"Couldn't send DM to {user.name}. Please enable DMs from server members.\n無法向 {user.name} 發送私訊。請啟用伺服器成員的私訊功能。"
            }
            await ctx.send(error_msg[selected_lang])
    
    # 顯示遊戲指南（根據選擇的語言）
    guide_descriptions = {
        'en': """
Simply type your character's actions and dialogue directly in the channel!
No need to use any commands for roleplay.

Available commands:
!scene - Review the current scene and objectives
!story - View story history
!stats - Check your character stats
!end_game - End the game session
""",
        'zh': """
直接在頻道中輸入你的角色行動和對話即可！
角色扮演不需要使用任何命令。

可用指令：
!scene - 查看當前場景和任務目標
!story - 查看故事歷史
!stats - 查看角色屬性
!end_game - 結束遊戲
""",
        'both': """
Simply type your character's actions and dialogue directly in the channel!
No need to use any commands for roleplay.

Available commands:
!scene - Review the current scene and objectives
!story - View story history
!stats - Check your character stats
!end_game - End the game session

直接在頻道中輸入你的角色行動和對話即可！
角色扮演不需要使用任何命令。

可用指令：
!scene - 查看當前場景和任務目標
!story - 查看故事歷史
!stats - 查看角色屬性
!end_game - 結束遊戲
"""
    }

    guide_titles = {
        'en': "📖 How to Play",
        'zh': "📖 如何遊玩",
        'both': "📖 How to Play | 如何遊玩"
    }

    guide_embed = discord.Embed(
        title=guide_titles[selected_lang],
        description=guide_descriptions[selected_lang],
        color=discord.Color.blue()
    )
    await ctx.send(embed=guide_embed)
    
    # 初始化故事追蹤
    game_data.story_history[channel_id] = []
    game_data.active_games[channel_id] = True
    game_data.game_players[channel_id] = players
    game_data.save_data()
    
    await update_story_message(ctx, channel_id, response, "Game Started", "System")
    cleanup_setup_state(channel_id)

def cleanup_setup_state(channel_id):
    """Clean up setup state for a channel"""
    if channel_id in setup_state.waiting_for_players:
        del setup_state.waiting_for_players[channel_id]
    if channel_id in setup_state.collecting_preferences:
        del setup_state.collecting_preferences[channel_id]
    if channel_id in setup_state.joined_players:
        del setup_state.joined_players[channel_id]
    if channel_id in setup_state.game_type:
        del setup_state.game_type[channel_id]

@bot.command(name='force_restart')
async def force_restart(ctx):
    """Force restart the game"""
    channel_id = str(ctx.channel.id)
    
    if channel_id in game_data.active_games:
        del game_data.active_games[channel_id]
    if channel_id in game_data.game_states:
        del game_data.game_states[channel_id]
    if channel_id in game_data.game_players:
        del game_data.game_players[channel_id]
    if channel_id in game_data.game_objectives:
        del game_data.game_objectives[channel_id]
    
    cleanup_setup_state(channel_id)
    game_data.save_data()
    
    await ctx.send("Game has been forcefully reset. Use !start_game to start a new game.\n遊戲已被強制重置。使用 !start_game 開始新遊戲。")

@bot.command(name='end_game')
async def end_game(ctx):
    """End the current game session"""
    channel_id = str(ctx.channel.id)
    if channel_id not in game_data.active_games:
        await ctx.send("No active game to end!\n沒有可以結束的遊戲！")
        return

    prompt = "Create a satisfying conclusion for the current scene, wrapping up any immediate plot points."
    conclusion = await get_ai_response(prompt, game_data.game_states[channel_id])

    del game_data.active_games[channel_id]
    del game_data.game_states[channel_id]
    game_data.save_data()

    embed = discord.Embed(
        title="Game Session Concluded | 遊戲會話結束",
        description=conclusion,
        color=discord.Color.red()
    )
    await ctx.send(embed=embed)

@bot.command(name='scene')
async def get_current_scene(ctx):
    """Display the current scene description"""
    channel_id = str(ctx.channel.id)
    if channel_id not in game_data.active_games:
        await ctx.send("No active game in this channel!\n此頻道沒有進行中的遊戲！")
        return

    current_state = game_data.game_states[channel_id]
    embed = discord.Embed(
        title="Current Scene | 當前場景",
        description=current_state['current_scene'],
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

@bot.command(name='story')
async def show_story(ctx):
    """Display the full story history"""
    channel_id = str(ctx.channel.id)
    if channel_id not in game_data.active_games:
        await ctx.send("No active game in this channel!\n此頻道沒有進行中的遊戲！")
        return

    if channel_id not in game_data.story_history:
        await ctx.send("No story history available.\n沒有可用的故事歷史。")
        return

    story_text = "**📖 Full Story History | 完整故事歷史**\n\n"
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
    story_summary = "**🎭 Current Story | 當前故事**\n\n"
    story_summary += "**Recent Events | 最近事件:**\n"
    
    # Add last 5 events
    for event in game_data.story_history[channel_id][-5:]:
        story_summary += f"\n👤 **{event['actor']}**: {event['action']}\n"
        story_summary += f"➡️ {event['result']}\n"
    
    story_summary += "\n**Current Scene | 當前場景:**\n"
    story_summary += game_data.game_states[channel_id]['current_scene']

    # 發送故事更新
    await send_long_message(
        ctx,
        story_summary,
        title="Story Progress | 故事進展",
        color=discord.Color.blue()
    )

# 添加新的事件監聽器來處理一般訊息
@bot.event
async def on_message(message):
    # 確保不會處理機器人自己的訊息
    if message.author.bot:
        return

    channel_id = str(message.channel.id)
    user_id = str(message.author.id)

    # 檢查是否在進行中的遊戲頻道
    if channel_id in game_data.active_games:
        # 檢查發言者是否為遊戲參與者
        if user_id in [str(pid) for pid in game_data.game_players[channel_id]]:
            # 忽略命令前綴的訊息，讓它們由 process_commands 處理
            if not message.content.startswith('!'):
                await process_action(message)
    
    # 確保命令仍然可以運作
    await bot.process_commands(message)

async def process_action(message):
    """處理玩家的角色扮演行動"""
    channel_id = str(message.channel.id)
    current_state = game_data.game_states[channel_id]
    action_text = message.content
    selected_lang = game_data.game_languages.get(channel_id, 'both')
    
    if selected_lang == 'en':
        prompt = f"""
Player {message.author.name} roleplays: {action_text}
Current scene: {current_state['current_scene']}

Evaluate this roleplay action and respond appropriately. If the main objective is completed, include [GAME_COMPLETE] at the start of your response.
Respond in English only.
"""
    elif selected_lang == 'zh':
        prompt = f"""
玩家 {message.author.name} 的角色扮演: {action_text}
當前場景: {current_state['current_scene']}

評估此角色扮演行動並作出適當回應。如果主要目標已完成，請在回應開頭加上 [GAME_COMPLETE]。
請只使用繁體中文回應。
"""
    else:
        prompt = f"""
Player {message.author.name} roleplays: {action_text}
Current scene: {current_state['current_scene']}

Evaluate this roleplay action and respond appropriately. If the main objective is completed, include [GAME_COMPLETE] at the start of your response.
Respond in both English and Traditional Chinese.
"""

    response = await get_ai_response(prompt, current_state)
    current_state['current_scene'] = response
    
    # 檢查是否完成遊戲
    if response.startswith("[GAME_COMPLETE]"):
        await handle_game_completion(message.channel, channel_id, response)
    else:
        await update_story_message(message.channel, channel_id, response, action_text, message.author.name)
        
        await send_long_message(
            message.channel,
            response,
            title="Roleplay Response | 角色扮演回應",
            color=discord.Color.green()
        )

async def handle_game_completion(ctx, channel_id, final_scene):
    embed = discord.Embed(
        title="🎉 Game Complete! | 遊戲完成！ 🎉",
        description=final_scene.replace("[GAME_COMPLETE]", ""),
        color=discord.Color.gold()
    )
    await ctx.send(embed=embed)
    
    # Clean up game state
    del game_data.active_games[channel_id]
    del game_data.game_states[channel_id]
    del game_data.game_players[channel_id]
    if channel_id in game_data.game_objectives:
        del game_data.game_objectives[channel_id]
    game_data.save_data()

if __name__ == "__main__":
    bot.run(TOKEN) 