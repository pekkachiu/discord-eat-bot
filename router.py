from food_agents import run_chat_agent, run_food_agent, run_nutrition_agent, run_weather_agent
from llm_client import llm_route_intent
from response_utils import send_food_result
from spin import detect_spin_source, run_spin_agent


def is_food_query(text: str) -> bool:
    kw = ["吃", "餐廳", "午餐", "晚餐", "宵夜", "早餐", "便當", "拉麵", "美食", "吃什麼", "吃啥"]
    return any(k in text for k in kw)


def is_weather_query(text: str) -> bool:
    kw = ["天氣", "氣溫", "溫度", "下雨", "冷不冷", "熱不熱"]
    return any(k in text for k in kw)


def is_nutrition_query(text: str) -> bool:
    kw = ["營養", "熱量", "卡路里", "蛋白質", "碳水", "脂肪", "營養成分"]
    return any(k in text for k in kw)


async def run_agent(message) -> str:
    user_text = message.content
    label = await llm_route_intent(user_text)
    guild_id = message.guild.id if message.guild else None
    if label == "nutrition":
        return await run_nutrition_agent(user_text, guild_id)
    if label == "weather":
        return await run_weather_agent(user_text, guild_id)
    if label == "food":
        ans, raw_ans = await run_food_agent(user_text, guild_id)
        await send_food_result(message.channel.send, ans, raw_ans)
        return ""
    if label == "spin":
        source = detect_spin_source(user_text)
        await run_spin_agent(message.channel, guild_id, source=source)
        return ""
    if label == "chat":
        return await run_chat_agent(user_text, guild_id)

    if is_nutrition_query(user_text):
        return await run_nutrition_agent(user_text, guild_id)
    if is_weather_query(user_text):
        return await run_weather_agent(user_text, guild_id)
    if is_food_query(user_text):
        ans, raw_ans = await run_food_agent(user_text, guild_id)
        await send_food_result(message.channel.send, ans, raw_ans)
        return ""
    return await run_chat_agent(user_text, guild_id)
