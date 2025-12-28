import json
import os 
import re
import discord

from config import WISHLIST_PATH


def _load_wishlist() -> dict:
    if not os.path.exists(WISHLIST_PATH):
        return {}
    try:
        with open(WISHLIST_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_wishlist(data: dict) -> None:
    with open(WISHLIST_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def add_to_wishlist(guild_id: int, name: str) -> bool:
    data = _load_wishlist()
    key = str(guild_id)
    items = data.get(key, [])
    if name in items:
        return False
    items.append(name)
    data[key] = items
    _save_wishlist(data)
    return True


def remove_from_wishlist(guild_id: int, index: int) -> tuple[bool, str]:
    data = _load_wishlist()
    key = str(guild_id)
    items = data.get(key, [])
    if index < 1 or index > len(items):
        return False, ""
    removed = items.pop(index - 1)
    data[key] = items
    _save_wishlist(data)
    return True, removed


def list_wishlist(guild_id: int) -> list[str]:
    data = _load_wishlist()
    return data.get(str(guild_id), [])


def extract_restaurant_names(text: str) -> list[str]:
    names: list[str] = []
    keycap_digits = {
        "0️⃣": "0",
        "1️⃣": "1",
        "2️⃣": "2",
        "3️⃣": "3",
        "4️⃣": "4",
        "5️⃣": "5",
        "6️⃣": "6",
        "7️⃣": "7",
        "8️⃣": "8",
        "9️⃣": "9",
    }
    for line in text.splitlines():
        normalized = line
        for k, v in keycap_digits.items():
            if k in normalized:
                normalized = normalized.replace(k, v)
        m = re.match(r"^\s*\[?\s*\d+\s*[\]\).、．-]?\s*(.+)$", normalized)
        if not m:
            continue
        name = m.group(1).strip()
        name = re.split(r"[（(].*$", name)[0].strip()
        if name and name not in names:
            names.append(name)
    return names[:5]


class WishlistView(discord.ui.View):
    def __init__(self, names: list[str]):
        super().__init__(timeout=300)
        for idx, name in enumerate(names[:5]):
            label = f"加入 {idx + 1}"
            button = discord.ui.Button(label=label, style=discord.ButtonStyle.primary)

            async def on_click(interaction: discord.Interaction, item=name):
                if interaction.guild_id is None:
                    await interaction.response.send_message("請在伺服器頻道使用此功能。", ephemeral=True)
                    return
                added = add_to_wishlist(interaction.guild_id, item)
                msg = f"已加入待吃清單：{item}" if added else f"已在待吃清單：{item}"
                await interaction.response.send_message(msg, ephemeral=False)

            button.callback = on_click
            self.add_item(button)
