import asyncio
import random
import discord
from discord import app_commands

from config import DISCORD_TOKEN
from food_agents import run_food_agent, _apply_style
from nutrition import llm_translate_list, llm_translate_single, usda_food_nutrition
from response_utils import send_food_result
from router import run_agent
from spin import pick_spin_candidates
from text_utils import make_urls_clickable
from wishlist import list_wishlist, remove_from_wishlist
from style_store import set_guild_style, get_guild_style

# ====== Discord bot（Slash command + 一般聊天）=====
# 紀錄每個 guild 是否開啟一般訊息回覆（預設 True）；重啟會重置
BOT_ENABLED_BY_GUILD = {}


def bot_enabled(guild_id: int) -> bool:
    return BOT_ENABLED_BY_GUILD.get(guild_id, True)


class MyClient(discord.Client):
    def __init__(self):
        intents = discord.Intents.default()
        intents.message_content = True  # 需要在 Discord Portal 打開 Message Content Intent
        super().__init__(intents=intents)
        self.tree = app_commands.CommandTree(self)

    async def setup_hook(self):
        # 只保留全域指令，避免全域 + guild 重複顯示
        for guild in self.guilds:
            try:
                self.tree.clear_commands(guild=guild)
                await self.tree.sync(guild=guild)
            except Exception as e:
                print(f"guild clear failed for {guild}: {e}")
        await self.tree.sync()

    async def on_message(self, message: discord.Message):
        if message.author.bot:
            return
        if message.content.startswith("/"):
            return
        guild_id = message.guild.id if message.guild else None
        if guild_id is not None and not bot_enabled(guild_id):
            return

        try:
            ans = await run_agent(message)
        except Exception as e:
            ans = f"抱歉，聊天時出錯：{e}"

        if not ans:
            return

        safe_ans = make_urls_clickable(ans)
        for i in range(0, len(safe_ans), 1800):
            await message.channel.send(safe_ans[i:i+1800])


dc = MyClient()


@dc.tree.command(name="eat", description="推薦我在成大/台南附近吃什麼")
@app_commands.describe(需求="例如：拉麵 200內 不要排隊 下雨想吃熱的")
async def eat(interaction: discord.Interaction, 需求: str):
    await interaction.response.defer(thinking=True)
    ans, raw_ans = await run_food_agent(需求, interaction.guild_id)
    await send_food_result(interaction.followup.send, ans, raw_ans)


@dc.tree.command(name="bot_toggle", description="開/關 bot 回覆一般訊息（不影響 /eat），作用於此伺服器")
@app_commands.describe(狀態="on 開啟；off 關閉一般訊息回覆")
async def bot_toggle(interaction: discord.Interaction, 狀態: str):
    guild_id = interaction.guild_id
    if guild_id is None:
        await interaction.response.send_message("請在伺服器頻道使用此指令。", ephemeral=True)
        return
    status_lower = 狀態.lower()
    if status_lower not in ("on", "off"):
        await interaction.response.send_message("請輸入 on 或 off", ephemeral=True)
        return
    BOT_ENABLED_BY_GUILD[guild_id] = status_lower == "on"
    await interaction.response.send_message(
        f"已{'開啟' if BOT_ENABLED_BY_GUILD[guild_id] else '關閉'}此伺服器的一般聊天回覆功能。",
        ephemeral=True,
    )


@dc.tree.command(name="spin", description="美食轉盤：從清單抽一道要吃的")
@app_commands.describe(
    items="用逗號分隔的候選項目，空白則用清單來源",
    source="清單來源：auto / wishlist / default",
    search="是否直接搜尋餐廳",
)
async def spin(
    interaction: discord.Interaction,
    items: str = "",
    source: str = "auto",
    search: bool = True,
):
    guild_id = interaction.guild_id

    item_list = [s.strip() for s in items.split(",") if s.strip()] if items.strip() else []
    source = source.lower().strip()
    if source not in ("auto", "wishlist", "default"):
        await interaction.response.send_message("source 只接受 auto / wishlist / default", ephemeral=True)
        return

    candidates = pick_spin_candidates(
        guild_id,
        item_list,
        None if source == "auto" else source,
    )

    if not candidates:
        await interaction.response.send_message(
            "沒有可抽的項目，請提供清單，例如：/spin 水餃,牛肉湯,拉麵",
            ephemeral=True,
        )
        return

    await interaction.response.send_message("🎡 轉盤啟動中…", ephemeral=False)
    msg = await interaction.original_response()

    steps = random.randint(8, 12)
    delay = 0.18
    last_choice = ""
    for _ in range(steps):
        last_choice = random.choice(candidates)
        await msg.edit(content=f"🎡 轉盤滾動中… **{last_choice}**")
        await asyncio.sleep(delay)
        delay = min(delay + 0.05, 0.6)

    await msg.edit(content=f"🎯 美食轉盤結果：**{last_choice}**")

    if not search:
        return

    await interaction.followup.send(f"🔎 正在搜尋「{last_choice}」附近餐廳…")
    ans, raw_ans = await run_food_agent(last_choice, interaction.guild_id)
    await send_food_result(interaction.followup.send, ans, raw_ans)


@dc.tree.command(name="nutrition", description="查詢食物的營養分析（Edamam）")
@app_commands.describe(食物="例如：1 bowl beef noodles / 1 apple / 2 slices pizza")
async def nutrition(interaction: discord.Interaction, 食物: str):
    await interaction.response.defer(thinking=True)
    ingr = await llm_translate_single(食物)
    result = await usda_food_nutrition(ingr)
    result = await _apply_style(result, interaction.guild_id)
    await interaction.followup.send(result)


@dc.tree.command(name="recipe_nutrition", description="查詢食譜營養（Edamam）")
@app_commands.describe(食材列表="用逗號分隔食材，例如：1 cup rice, 200g chicken, 1 tbsp oil")
async def recipe_nutrition(interaction: discord.Interaction, 食材列表: str):
    await interaction.response.defer(thinking=True)
    lines = [s.strip() for s in 食材列表.split(",") if s.strip()]
    if not lines:
        await interaction.followup.send("請輸入食材列表，例如：1 cup rice, 200g chicken, 1 tbsp oil")
        return
    converted = await llm_translate_list(lines)
    if len(converted) > 1:
        note = "（提示：目前以第一個食材做查詢）\n"
    else:
        note = ""
    result = await usda_food_nutrition(converted[0])
    result = await _apply_style(result, interaction.guild_id)
    await interaction.followup.send(note + result)


@dc.tree.command(name="wishlist_show", description="查看待吃清單")
async def wishlist_show(interaction: discord.Interaction):
    if interaction.guild_id is None:
        await interaction.response.send_message("請在伺服器頻道使用此指令。", ephemeral=True)
        return
    items = list_wishlist(interaction.guild_id)
    if not items:
        await interaction.response.send_message("待吃清單是空的。", ephemeral=False)
        return
    text = "\n".join([f"{i+1}. {name}" for i, name in enumerate(items)])
    await interaction.response.send_message(f"本伺服器待吃清單：\n{text}", ephemeral=False)


@dc.tree.command(name="wishlist_remove", description="從待吃清單刪除項目")
@app_commands.describe(index="要刪除的項目編號（從 1 開始）")
async def wishlist_remove(interaction: discord.Interaction, index: int):
    if interaction.guild_id is None:
        await interaction.response.send_message("請在伺服器頻道使用此指令。", ephemeral=True)
        return
    ok, removed = remove_from_wishlist(interaction.guild_id, index)
    if not ok:
        await interaction.response.send_message("刪除失敗：請確認編號是否正確。", ephemeral=False)
        return
    await interaction.response.send_message(f"已刪除：{removed}", ephemeral=False)


@dc.tree.command(name="sync_commands", description="重新同步斜線指令（需管理伺服器權限）")
async def sync_commands(interaction: discord.Interaction):
    if not interaction.user.guild_permissions.manage_guild:
        await interaction.response.send_message("需要「管理伺服器」權限才能執行同步。", ephemeral=True)
        return

    await interaction.response.defer(ephemeral=True, thinking=True)
    try:
        guild = interaction.guild
        if guild:
            dc.tree.clear_commands(guild=guild)
            await dc.tree.sync(guild=guild)
        synced = await dc.tree.sync()
        await interaction.followup.send(f"已同步全域指令共 {len(synced)} 個。")
    except Exception as e:
        await interaction.followup.send(f"同步失敗：{e}")


@dc.tree.command(name="style", description="設定伺服器共用的回覆風格")
@app_commands.describe(風格="例如：簡短、幽默、正式、條列、可愛")
async def style(interaction: discord.Interaction, 風格: str):
    if interaction.guild_id is None:
        await interaction.response.send_message("請在伺服器頻道使用此指令。", ephemeral=True)
        return
    style_text = 風格.strip()
    if not style_text:
        current = get_guild_style(interaction.guild_id)
        msg = f"目前風格：{current}" if current else "目前沒有設定風格。"
        await interaction.response.send_message(msg, ephemeral=True)
        return
    set_guild_style(interaction.guild_id, style_text)
    await interaction.response.send_message(f"已設定此伺服器風格：{style_text}", ephemeral=False)


dc.run(DISCORD_TOKEN)
