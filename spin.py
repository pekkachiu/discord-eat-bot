import asyncio 
import random
from typing import Optional

import discord

from config import DEFAULT_SPIN_CANDIDATES
from food_agents import run_food_agent
from response_utils import send_food_result
from wishlist import list_wishlist


def detect_spin_source(text: str) -> Optional[str]:
    if any(k in text for k in ["清單", "待吃", "wishlist"]):
        return "wishlist"
    if any(k in text for k in ["預設", "內建", "default"]):
        return "default"
    return None


def pick_spin_candidates(
    guild_id: Optional[int],
    items: list[str],
    source: Optional[str],
) -> list[str]:
    if items:
        return items
    if source is None:
        return DEFAULT_SPIN_CANDIDATES
    if source == "default":
        return DEFAULT_SPIN_CANDIDATES
    if source == "wishlist" and guild_id is not None:
        return list_wishlist(guild_id)
    if guild_id is not None:
        wishlist_items = list_wishlist(guild_id)
        if wishlist_items:
            return wishlist_items
    return DEFAULT_SPIN_CANDIDATES


async def run_spin_agent(
    channel: discord.abc.Messageable,
    guild_id: Optional[int],
    source: Optional[str] = None,
) -> None:
    candidates = pick_spin_candidates(guild_id, [], source)
    if not candidates:
        await channel.send("清單是空的，請先用 /wishlist_show 檢查或用 /spin items 自訂清單。")
        return

    msg = await channel.send("🎡 轉盤啟動中…")
    steps = random.randint(8, 12)
    delay = 0.18
    last_choice = ""
    for _ in range(steps):
        last_choice = random.choice(candidates)
        await msg.edit(content=f"🎡 轉盤滾動中… **{last_choice}**")
        await asyncio.sleep(delay)
        delay = min(delay + 0.05, 0.6)

    await msg.edit(content=f"🎯 轉盤結果：**{last_choice}**\n🔎 正在搜尋餐廳…")
    food_ans = await run_food_agent(last_choice, guild_id)
    await send_food_result(channel.send, food_ans)
