# Discord Hood Hunter Bot

## Overview
A Discord bot for food discovery that integrates Google Places search, optional LLM-driven suggestions, and USDA nutrition lookups. It helps users find nearby spots, get quick recommendations, and enrich results with nutrition info when available.

## Features
- Food recommendations: search nearby restaurants based on preferences (Google Places).
- Spin wheel: pick a dish from custom/wishlist/default candidates and optionally search it.
- Nutrition lookup: USDA Nutrition data; if LLM is configured, Chinese inputs are auto-translated to English ingredients.
- General chat: intent routing for food/nutrition/weather/spin and casual chat replies.
- Wishlist: add items from search results with buttons; server-specific list.
- Reply style: set a shared reply style per server.

## Commands
- `/eat 需求`: recommend what to eat near NCKU/Tainan.
- `/bot_toggle 狀態`: on to enable; off to disable general message replies (does not affect `/eat`).
- `/spin items? source? search?`: spin wheel; items is comma-separated; source=auto/wishlist/default; search toggles restaurant lookup.
- `/nutrition 食物`: nutrition for a single food (e.g., `1 bowl beef noodles`).
- `/recipe_nutrition 食材列表`: recipe nutrition; comma-separated ingredients.
- `/wishlist_show`: show wishlist.
- `/wishlist_remove index`: remove an item by number (starting from 1).
- `/style 風格`: set server reply style (e.g., short/funny/formal).
- `/sync_commands`: resync slash commands (requires Manage Server permission).

## Setup
1) Create a virtualenv and install deps:

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

2) Create `.env` from `env.example` and fill in keys:

```bash
cp env.example .env
```

Required:
- `DISCORD_BOT_TOKEN`
- `GOOGLE_API_KEY`

Optional (features depend on them):
- `LLM_API_KEY` or `OPENAI_API_KEY`
- `LLM_BASE_URL`
- `USDA_API_KEY`

3) Run the bot:

```bash
python bot.py
```

## Notes
- Enable Message Content Intent in the Discord Developer Portal for your bot.
