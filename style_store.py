import json
import os

STYLE_PATH = "style.json"


def _load() -> dict:
    if not os.path.exists(STYLE_PATH):
        return {}
    try:
        with open(STYLE_PATH, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def _save(data: dict) -> None:
    with open(STYLE_PATH, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=2)


def set_guild_style(guild_id: int, style: str) -> None:
    data = _load()
    data[str(guild_id)] = style
    _save(data)


def get_guild_style(guild_id: int) -> str:
    data = _load()
    return str(data.get(str(guild_id), "")).strip()
