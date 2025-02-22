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
    "mystery": {"name": "神秘", "emoji": "🔮"},
    "murder": {"name": "謀殺懸疑", "emoji": "🔪"},
    "horror": {"name": "恐怖", "emoji": "👻"},
    "fantasy": {"name": "奇幻", "emoji": "🐉"},
    "detective": {"name": "偵探推理", "emoji": "🔍"},
    "adventure": {"name": "冒險", "emoji": "⚔️"},
    "heist": {"name": "盜寶行動", "emoji": "💎"},
    "survival": {"name": "生存", "emoji": "🏕️"},
    "conspiracy": {"name": "陰謀", "emoji": "🕵️"},
    "comedy": {"name": "搞笑", "emoji": "😂"},
    "espionage": {"name": "諜報", "emoji": "🕴️"},
    "supernatural": {"name": "超自然", "emoji": "👥"},
    "historical": {"name": "歷史", "emoji": "📜"},
    "sci_fi": {"name": "科幻", "emoji": "🚀"},
    "psychological": {"name": "心理驚悚", "emoji": "🧠"},
    "escape": {"name": "密室逃脫", "emoji": "🚪"}
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

async def get_ai_response(prompt, game_state=None, language='both'):
    try:
        # 根據語言設置不同的系統提示
        system_prompts = {
            'en': """You are an experienced LARP game master. Create engaging narratives and respond to player actions.
            Respond in English only.""",
            
            'zh': """你是一位經驗豐富的LARP遊戲主持人。創造引人入勝的敘事並回應玩家行動。
            請只使用繁體中文回應。""",
            
            'both': """You are an experienced LARP game master. Create engaging narratives and respond to player actions.
            Provide responses in both English and Traditional Chinese using this format:
            
            [EN]
            (English response)
            
            [繁中]
            (繁體中文回應)
            """
        }

        messages = [
            {"role": "system", "content": system_prompts[language]},
            {"role": "user", "content": prompt}
        ]
        
        if game_state:
            messages.insert(1, {"role": "system", "content": f"Current game state: {game_state}"})

        response = client.chat.completions.create(
            model="gpt-3.5-turbo-1106",
            messages=messages,
            max_tokens=600,
            temperature=0.7
        )
        return response.choices[0].message.content
    except Exception as e:
        print(f"OpenAI API Error: {str(e)}")
        error_messages = {
            'en': "Error: Unable to generate story. Please try again in a moment.",
            'zh': "錯誤：無法生成故事。請稍後再試。",
            'both': "Error: Unable to generate story. Please try again in a moment.\n\n錯誤：無法生成故事。請稍後再試。"
        }
        return error_messages[language]

@bot.event
async def on_ready():
    print(f'{bot.user} has connected to Discord!')

@bot.command(name='start_game')
async def start_game(ctx):
    """Start the game initialization process"""
    channel_id = str(ctx.channel.id)
    
    if channel_id in game_data.active_games:
        await ctx.send("A game is already in progress! Must end it before start a new game.\n遊戲已經在進行中！使用 !end_game 來結束目前遊戲。")
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
        
        # 將遊戲類型分類顯示
        game_types_str = "**🎲 Choose Game Type | 選擇遊戲類型**\n\n"
        
        categories = {
            "Mystery & Detective": ["mystery", "murder", "detective", "psychological", "conspiracy"],
            "Adventure & Action": ["adventure", "heist", "survival", "escape"],
            "Fantasy & Supernatural": ["fantasy", "supernatural", "horror", "sci_fi"],
            "Special Themes": ["historical", "espionage", "comedy"],
        }
        
        for category, types in categories.items():
            game_types_str += f"**{category}**\n"
            for game_type in types:
                info = GAME_TYPES[game_type]
                game_types_str += f"{info['emoji']} {game_type.capitalize()}: {info['name']}\n"
            game_types_str += "\n"

        embed = discord.Embed(
            title="Vote for Game Type | 投票選擇遊戲類型",
            description=f"React to vote! (10 seconds)\n請投票！（10秒）\n\n{game_types_str}",
            color=discord.Color.green()
        )
        
        # 添加遊戲類型說明
        type_descriptions = {
            'en': {
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
            },
            'zh': {
                "mystery": "解開複雜謎團，揭露隱藏真相",
                "murder": "調查謀殺案件，找出兇手",
                "detective": "運用推理和證據解決案件",
                "psychological": "探索心理張力和心智博弈",
                "conspiracy": "揭露並應對錯綜複雜的陰謀",
                "adventure": "展開刺激的冒險旅程",
                "heist": "策劃並執行精密的盜寶行動",
                "survival": "在惡劣環境或威脅中求生",
                "escape": "想辦法逃離受限的處境",
                "fantasy": "體驗魔法和神話冒險",
                "supernatural": "應對超自然現象",
                "horror": "面對恐怖的處境和生物",
                "sci_fi": "探索未來科技場景",
                "historical": "體驗歷史背景中的冒險",
                "espionage": "執行間諜任務和秘密行動",
                "comedy": "享受幽默有趣的情境互動"
            }
        }

        # 根據選擇的語言添加說明
        selected_lang = game_data.game_languages.get(str(ctx.channel.id), 'both')
        if selected_lang in ['en', 'both']:
            embed.add_field(name="Game Type Descriptions", value="\n".join(f"{GAME_TYPES[t]['emoji']} **{t.capitalize()}**: {type_descriptions['en'][t]}" for t in GAME_TYPES), inline=False)
        if selected_lang in ['zh', 'both']:
            embed.add_field(name="遊戲類型說明", value="\n".join(f"{GAME_TYPES[t]['emoji']} **{GAME_TYPES[t]['name']}**: {type_descriptions['zh'][t]}" for t in GAME_TYPES), inline=False)

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

    response = await get_ai_response(prompt, language=selected_lang)
    game_data.game_states[channel_id] = {
        'current_scene': response,
        'progress': 0,
        'completed_objectives': [],
        'main_objective': '',  # 儲存主要目標
        'key_requirements': []  # 儲存完成目標需要的關鍵條件
    }
    
    # 解析並儲存主要目標和關鍵要求
    if selected_lang == 'en':
        objective_prompt = f"""Based on the story setup:
1. Extract the main objective in a clear, measurable statement
2. List 3-5 specific key requirements that must ALL be met to complete the objective
3. Format as JSON:
{{
    "main_objective": "objective statement",
    "key_requirements": ["req1", "req2", "req3"]
}}"""
    elif selected_lang == 'zh':
        objective_prompt = f"""根據故事設定：
1. 提取明確、可衡量的主要目標
2. 列出3-5個必須全部達成才能完成目標的具體關鍵要求
3. 以JSON格式輸出：
{{
    "main_objective": "目標陳述",
    "key_requirements": ["要求1", "要求2", "要求3"]
}}"""
    else:
        objective_prompt = f"""Based on the story setup, provide in both languages:
1. Extract the main objective in a clear, measurable statement
2. List 3-5 specific key requirements that must ALL be met to complete the objective
3. Format as JSON:
{{
    "main_objective": {{
        "en": "objective statement",
        "zh": "目標陳述"
    }},
    "key_requirements": {{
        "en": ["req1", "req2", "req3"],
        "zh": ["要求1", "要求2", "要求3"]
    }}
}}"""

    objective_response = await get_ai_response(objective_prompt, language=selected_lang)
    try:
        objectives = json.loads(objective_response)
        game_data.game_states[channel_id].update(objectives)
    except:
        print("Error parsing objectives JSON")

    # 發送初始故事
    await send_long_message(
        ctx,
        response,
        title=get_title("🎮 New Adventure Begins", "新冒險開始", selected_lang),
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

        role_info = await get_ai_response(role_prompt, language=selected_lang)
        try:
            await send_long_message(
                user,
                role_info,
                title=get_title("Your Character", "你的角色", selected_lang),
                color=discord.Color.blue()
            )
        except discord.Forbidden:
            error_msg = get_error_message("Couldn't send DM to", "無法向", user.name, selected_lang)
            await ctx.send(error_msg)
    
    # 顯示遊戲指南（根據選擇的語言）
    guide_descriptions = {
        'en': """
Simply type your character's actions and dialogue directly in the channel!
No need to use any commands for roleplay.

Available commands:
!scene - Review the current scene and objectives
!story - View story history
!end_game - End the game session
""",
        'zh': """
直接在頻道中輸入你的角色行動和對話即可！
角色扮演不需要使用任何命令。

可用指令：
!scene - 查看當前場景和任務目標
!story - 查看故事歷史
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
    
    # 構建更嚴格的完成檢查提示
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

    response = await get_ai_response(completion_check_prompt, current_state, language=selected_lang)
    
    if response.startswith("[GAME_COMPLETE]"):
        # 確認完成後自動結束遊戲
        await handle_game_completion(message.channel, channel_id, response)
        
        # 發送遊戲結束通知
        end_titles = {
            'en': "🎊 Adventure Successfully Completed!",
            'zh': "🎊 冒險成功完成！",
            'both': "🎊 Adventure Successfully Completed! | 冒險成功完成！"
        }
        
        end_messages = {
            'en': f"All objectives have been met! The game has ended.\nMain Objective: {current_state['main_objective']}",
            'zh': f"所有目標都已達成！遊戲已結束。\n主要目標：{current_state['main_objective']}",
            'both': f"""All objectives have been met! The game has ended.
Main Objective: {current_state['main_objective']}

所有目標都已達成！遊戲已結束。
主要目標：{current_state['main_objective']}"""
        }
        
        end_embed = discord.Embed(
            title=end_titles[selected_lang],
            description=end_messages[selected_lang],
            color=discord.Color.gold()
        )
        await message.channel.send(embed=end_embed)
        
        # 清理遊戲狀態
        del game_data.active_games[channel_id]
        del game_data.game_states[channel_id]
        del game_data.game_players[channel_id]
        if channel_id in game_data.game_objectives:
            del game_data.game_objectives[channel_id]
        game_data.save_data()
    else:
        current_state['current_scene'] = response
        await update_story_message(message.channel, channel_id, response, action_text, message.author.name)
        await send_long_message(
            message.channel,
            response,
            title=get_title("Roleplay Response", "角色扮演回應", selected_lang),
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

# 添加一個輔助函數來生成標題
def get_title(en_text, zh_text, language):
    if language == 'en':
        return f"🎭 {en_text}"
    elif language == 'zh':
        return f"🎭 {zh_text}"
    else:
        return f"🎭 {en_text} | {zh_text}"

# 添加一個輔助函數來生成錯誤訊息
def get_error_message(en_prefix, zh_prefix, name, language):
    if language == 'en':
        return f"{en_prefix} {name}. Please enable DMs from server members."
    elif language == 'zh':
        return f"{zh_prefix} {name} 發送私訊。請啟用伺服器成員的私訊功能。"
    else:
        return f"{en_prefix} {name}. Please enable DMs from server members.\n{zh_prefix} {name} 發送私訊。請啟用伺服器成員的私訊功能。"

if __name__ == "__main__":
    bot.run(TOKEN) 