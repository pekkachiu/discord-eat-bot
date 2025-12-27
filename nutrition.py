from typing import Optional
import httpx

from config import LLM_API_KEY, USDA_API_KEY
from llm_client import llm_generate


def _convert_unit(qty: float, unit: str, target_unit: str) -> tuple[float, str]:
    if unit == target_unit:
        return qty, unit
    unit_norm = unit.lower()
    target_norm = target_unit.lower()
    if unit_norm == "mg" and target_norm == "g":
        return qty / 1000.0, target_unit
    if unit_norm == "g" and target_norm == "mg":
        return qty * 1000.0, target_unit
    return qty, unit


def _format_usda_nutrient(nutrients: list[dict], names: list[str], target_unit: Optional[str] = None) -> str:
    for n in nutrients or []:
        nutrient_obj = n.get("nutrient") or {}
        name = (
            n.get("nutrientName")
            or n.get("name")
            or nutrient_obj.get("name")
            or ""
        ).strip()
        if name in names:
            qty = n.get("value")
            if qty is None:
                qty = n.get("amount")
            unit = n.get("unitName") or n.get("unit") or nutrient_obj.get("unitName") or ""
            if qty is None:
                break
            if target_unit:
                qty, unit = _convert_unit(float(qty), unit, target_unit)
            return f"{float(qty):.1f}{unit}"
    return "未提供"


async def llm_translate_single(text: str) -> str:
    if not LLM_API_KEY:
        return text
    prompt = (
        "請把以下中文食物或份量轉成 Edamam 可解析的英文食材描述。"
        "只輸出一行英文，不要解釋、不加編號；若已是英文就原樣輸出。\n"
        f"{text}"
    )
    try:
        return (await llm_generate(prompt)).strip() or text
    except Exception:
        return text


async def llm_translate_list(lines: list[str]) -> list[str]:
    if not LLM_API_KEY:
        return lines
    prompt = (
        "請把以下中文食材清單轉成 Edamam 可解析的英文食材描述。"
        "每個食材一行輸出，不要編號、不加解釋；已是英文就原樣輸出。\n"
        + "\n".join(lines)
    )
    try:
        text = (await llm_generate(prompt)).strip()
    except Exception:
        return lines
    if not text:
        return lines
    converted = [s.strip() for s in text.splitlines() if s.strip()]
    return converted or lines


async def usda_food_nutrition(query: str) -> str:
    if not USDA_API_KEY:
        return "（未設定 USDA_API_KEY，無法查詢）"

    params = {
        "api_key": USDA_API_KEY,
        "query": query,
        "pageSize": 1,
    }
    async with httpx.AsyncClient(timeout=20) as http:
        search = await http.get("https://api.nal.usda.gov/fdc/v1/foods/search", params=params)
        search.raise_for_status()
        sdata = search.json()
        foods = sdata.get("foods", []) or []
        if not foods:
            return "（查無結果，請換更明確的食物名稱）"
        fdc_id = foods[0].get("fdcId")
        desc = foods[0].get("description") or query
        detail = await http.get(
            f"https://api.nal.usda.gov/fdc/v1/food/{fdc_id}",
            params={"api_key": USDA_API_KEY},
        )
        detail.raise_for_status()
        ddata = detail.json()

    nutrients = ddata.get("foodNutrients", []) or []
    energy = _format_usda_nutrient(nutrients, ["Energy"], "kcal")
    lines = [
        f"食物：{desc}",
        f"熱量：{energy}",
        f"蛋白質：{_format_usda_nutrient(nutrients, ['Protein'], 'g')}",
        f"碳水：{_format_usda_nutrient(nutrients, ['Carbohydrate, by difference'], 'g')}",
        f"脂肪：{_format_usda_nutrient(nutrients, ['Total lipid (fat)'], 'g')}",
        f"膳食纖維：{_format_usda_nutrient(nutrients, ['Fiber, total dietary'], 'g')}",
        f"鈉：{_format_usda_nutrient(nutrients, ['Sodium, Na'], 'mg')}",
    ]
    return "\n".join(lines)
