# Discord Hood Hunter Bot

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
