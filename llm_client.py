import httpx

from config import LLM_BASE_URL, LLM_API_KEY


async def llm_generate(prompt: str) -> str:
    if not LLM_API_KEY:
        raise RuntimeError("LLM_API_KEY 未設定")

    url = LLM_BASE_URL.rstrip("/") + "/api/generate"
    payload = {
        "model": "gemma3:4b",
        "prompt": prompt,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {LLM_API_KEY}",
        "Content-Type": "application/json",
    }
    async with httpx.AsyncClient(timeout=300) as http:
        resp = await http.post(url, json=payload, headers=headers)
        resp.raise_for_status()
        data = resp.json()
        return data.get("response", "") or data.get("text", "")


async def llm_route_intent(user_text: str) -> str:
    prompt = (
        "你是一個路由器，只回覆以下其中一個標籤：\n"
        "food / weather / nutrition / spin / chat\n"
        "判斷使用者是否要找餐廳推薦、查天氣、查營養、轉盤隨機選餐，否則為 chat。\n"
        "只輸出標籤，不要其他文字。\n"
        f"使用者：{user_text}"
    )
    try:
        label = (await llm_generate(prompt)).strip().lower()
    except Exception:
        return ""

    if label in ("food", "weather", "nutrition", "spin", "chat"):
        return label
    if "food" in label:
        return "food"
    if "weather" in label:
        return "weather"
    if "nutrition" in label:
        return "nutrition"
    if "spin" in label or "wheel" in label or "random" in label:
        return "spin"
    if "chat" in label:
        return "chat"
    return ""
