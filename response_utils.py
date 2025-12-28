from wishlist import WishlistView, extract_restaurant_names
from text_utils import make_urls_clickable


async def send_food_result(send_func, ans: str, raw_ans: str) -> None:
    safe_ans = make_urls_clickable(ans)
    for i in range(0, len(safe_ans), 1800):
        await send_func(safe_ans[i:i+1800])

    names = extract_restaurant_names(raw_ans)
    if names:
        await send_func("想加入待吃清單？點下面按鈕：", view=WishlistView(names))
