import asyncio
import json
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx

import config  # Load .env before food_tool import.
from food_tool import Tools as FoodTools
from llm_client import llm_generate
from nutrition import llm_translate_list, usda_food_nutrition
from text_utils import (
    detect_food_location,
    detect_meal_from_text,
    extract_city,
    extract_nutrition_target,
    infer_meal_by_time,
)

food = FoodTools()


async def get_current_weather(city: str) -> dict:
    async with httpx.AsyncClient(timeout=15) as http:
        geo = await http.get(
            "https://geocoding-api.open-meteo.com/v1/search",
            params={"name": city, "count": 1, "language": "zh", "format": "json"},
        )
        geo.raise_for_status()
        g = geo.json()
        if "results" not in g or not g["results"]:
            return {"city": city, "error": "找不到城市"}

        lat = g["results"][0]["latitude"]
        lon = g["results"][0]["longitude"]

        w = await http.get(
            "https://api.open-meteo.com/v1/forecast",
            params={"latitude": lat, "longitude": lon, "current_weather": True},
        )
        w.raise_for_status()
        cw = w.json().get("current_weather", {})
        return {
            "city": city,
            "temperature_c": cw.get("temperature"),
            "windspeed": cw.get("windspeed"),
            "weathercode": cw.get("weathercode"),
        }


async def find_food(
    keyword: str,
    location: str = "國立成功大學",
    max_travel_time: int = 20,
    min_rating: float = 3.5,
    min_reviews: int = 0,
) -> str:
    return await asyncio.to_thread(
        food.find_food,
        keyword,
        location,
        max_travel_time,
        min_rating,
        min_reviews,
    )


async def run_food_agent(user_text: str) -> str:
    city_en, location_label = detect_food_location(user_text)
    meal_by_text = detect_meal_from_text(user_text)
    now = datetime.now(ZoneInfo("Asia/Taipei"))
    meal_guess = meal_by_text or infer_meal_by_time(now)
    meal_src = "使用者描述" if meal_by_text else "當前時間推測"
    local_time = now.strftime("%H:%M")

    weather = await get_current_weather(city_en)
    search_kw = user_text if meal_by_text else f"{meal_guess} {user_text}"
    food_text = await find_food(keyword=search_kw, location=location_label)

    prompt = (
        "你是成大附近的美食推薦助理。\n"
        f"使用者需求：{user_text}\n"
        f"搜尋地點：{location_label}\n"
        f"餐別：{meal_guess}（來源：{meal_src}）\n"
        f"現在時間（台灣）：{local_time}\n"
        f"天氣資料：{json.dumps(weather, ensure_ascii=False)}\n"
        "搜尋結果（包含距離/評分/評論數/價位/必點/評論摘要）：\n"
        f"{food_text}\n\n"
        "請用繁中給 3~5 家推薦，格式示例：\n"
        "1. 店名\n"
        "   距離/時間：xx\n"
        "   價位：xx\n"
        "   評分：xx\n"
        "   必點：菜名1；菜名2；菜名3（若沒有必點請寫：暫無明確推薦）\n"
        "   地圖：直接貼上 Google Maps 連結（必填，不可省略）\n"
        "   推薦理由：一句話\n"
        "   營業：營業時間或未提供\n"
        "必須把「必點」欄位列出具體菜名，避免只寫“推薦招牌”；每家都要附 Google Maps 連結。"
    )

    try:
        return await llm_generate(prompt)
    except Exception as e:
        return f"抱歉，呼叫 LLM 失敗：{e}"


async def run_weather_agent(user_text: str) -> str:
    city = extract_city(user_text)
    try:
        weather = await get_current_weather(city)
    except Exception as e:
        return f"抱歉，查天氣失敗：{e}"

    prompt = (
        "你是一個簡潔的天氣小幫手，使用繁體中文回答。"
        f"\n城市：{city}"
        f"\n天氣資料：{json.dumps(weather, ensure_ascii=False)}"
        "\n請告訴使用者目前溫度、風速，並給穿著或出門建議。"
    )
    try:
        return await llm_generate(prompt)
    except Exception as e:
        return f"抱歉，呼叫 LLM 失敗：{e}"


async def run_chat_agent(user_text: str) -> str:
    prompt = (
        "你是一個友善的聊天夥伴，使用繁體中文，簡潔自然地回覆。"
        "如果使用者主動問吃什麼，才進入美食推薦；否則就是閒聊。"
        f"\n使用者：{user_text}\n"
        "請直接回覆，不要多餘的系統訊息。"
    )
    try:
        return await llm_generate(prompt)
    except Exception as e:
        return f"抱歉，呼叫 LLM 失敗：{e}"


async def run_nutrition_agent(user_text: str) -> str:
    target = extract_nutrition_target(user_text)
    converted = await llm_translate_list([target])
    target = converted[0] if converted else target
    return await usda_food_nutrition(target)
