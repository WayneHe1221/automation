# -*- coding: utf-8 -*-
"""任務：square-bushiroad 商品列表 668 監控（每天一次）。

抓取 product-list/668 -> 解析商品(id/名稱) -> 與上次比較
-> 有「新增商品」就用同一個 Telegram bot 通知。
狀態存於 state/bushiroad_668.json。

節流：本任務每天只實際執行一次。run_all 每小時呼叫時，
若今天(UTC)已跑過就直接跳過、不抓網頁。
"""

import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.fetch import fetch_html  # noqa: E402
from lib.notify import send_telegram  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "state", "bushiroad_668.json")

LIST_URL = os.environ.get(
    "BUSHIROAD_668_URL", "https://www.square-bushiroad.com/product-list/668"
)


def _unescape(s):
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return s


def parse_total(html):
    m = re.search(r'class="count_number">\s*<span class="number">([\d,]+)</span>', html, re.S)
    return int(m.group(1).replace(",", "")) if m else None


def parse_products(html):
    """解析 -> {id(str): name(str)}。以 data-product-id 為分界切塊。"""
    products = {}
    matches = list(re.finditer(r'data-product-id="(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        block = html[start:end]
        nm = re.search(r'<span class="goods_name">(.*?)</span>', block, re.S)
        name = ""
        if nm:
            name = _unescape(re.sub(r"<[^>]+>", "", nm.group(1)).strip())
        if pid not in products:
            products[pid] = name
        elif name and not products[pid]:
            products[pid] = name
    return products


def load_state():
    if os.path.exists(STATE_PATH):
        try:
            with open(STATE_PATH, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


def save_state(state):
    os.makedirs(os.path.dirname(STATE_PATH), exist_ok=True)
    with open(STATE_PATH, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)


def link(pid, name):
    label = name if name else f"商品 {pid}"
    return f'<a href="https://www.square-bushiroad.com/product/{pid}">{label}</a>'


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = load_state()

    # 每天只跑一次：今天已執行就跳過。
    if state.get("last_run_date") == today:
        print(f"今天({today})已執行過，跳過")
        return

    try:
        html = fetch_html(LIST_URL)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: 抓取失敗，跳過本次（不更新狀態）：{e}")
        return

    current = parse_products(html)
    if not current:
        print("WARN: 解析到 0 個商品，跳過本次（不更新狀態、不誤報）")
        return

    total = parse_total(html)
    if total is not None and len(current) < total:
        print(f"WARN: 只解析到 {len(current)}/{total} 件（可能分頁未抓全）")

    prev = state.get("products")

    if not isinstance(prev, dict):
        print(f"首次執行，建立基準：{len(current)} 件商品")
        send_telegram(
            f"✅ <b>bushiroad 668 追蹤已啟動</b>\n\n"
            f"目前共 <b>{len(current)}</b> 件商品。\n"
            f"之後每天檢查一次，有<b>新增商品</b>會通知你。"
        )
        save_state({"products": current, "last_run_date": today})
        return

    new_ids = [pid for pid in current if pid not in prev]

    if not new_ids:
        print(f"無新增：{len(current)} 件商品")
        save_state({"products": current, "last_run_date": today})
        return

    lines = [f"🆕 <b>bushiroad 668 新增商品 ({len(new_ids)})</b>", ""]
    lines += [f"• {link(pid, current[pid])}" for pid in new_ids]
    message = "\n".join(lines)
    print(f"新增 {len(new_ids)} 件，發送通知")
    if send_telegram(message):
        save_state({"products": current, "last_run_date": today})
    else:
        # 通知失敗：不更新狀態（含 last_run_date），下個整點重試。
        print("通知失敗，保留舊基準，稍後重試")


if __name__ == "__main__":
    main()
