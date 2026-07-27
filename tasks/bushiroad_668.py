# -*- coding: utf-8 -*-
"""任務：square-bushiroad 商品列表 668 監控（每天一次）。

抓取 product-list/668 -> 解析商品(id/名稱/在庫) -> 與上次比較
-> 有「異動」（新增／下架）就登記到 lib/digest.py，與其他來源併成一則通知；
下架只給文案，新增附上商品連結。
狀態存於 state/bushiroad_668.json。

節流：本任務每天只實際執行一次。run_all 每小時呼叫時，
若今天(UTC)已跑過就直接跳過、不抓網頁。
"""

import html as html_lib
import json
import os
import re
import sys
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib import digest  # noqa: E402
from lib.changes import diff_products, has_changes  # noqa: E402
from lib.fetch import fetch_html  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "state", "bushiroad_668.json")

LIST_URL = os.environ.get(
    "BUSHIROAD_668_URL", "https://www.square-bushiroad.com/product-list/668"
)


def parse_total(html):
    m = re.search(r'class="count_number">\s*<span class="number">([\d,]+)</span>', html, re.S)
    return int(m.group(1).replace(",", "")) if m else None


def parse_stock_quantity(text):
    """從商品區塊擷取「在庫数 N」庫存數量；沒有數字（售完或未顯示）回傳 None。"""
    m = re.search(r"在庫数[\s:：]*([\d,]+)", text)
    return int(m.group(1).replace(",", "")) if m else None


def parse_products(html):
    """解析 -> {id(str): {"name": str, "in_stock": bool, "qty": int|None}}（原始清單，含售完）。

    以 data-product-id 為分界切塊；在庫なし / stock soldout 視為售完。
    每個 id 以第一次出現為準。售完過濾在 main 處理。
    """
    products = {}
    matches = list(re.finditer(r'data-product-id="(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        if pid in products:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        block = html[m.end():end]
        in_stock = "在庫なし" not in block and "stock soldout" not in block
        nm = re.search(r'<span class="goods_name">(.*?)</span>', block, re.S)
        name = html_lib.unescape(re.sub(r"<[^>]+>", "", nm.group(1)).strip()) if nm else ""
        products[pid] = {"name": name, "in_stock": in_stock, "qty": parse_stock_quantity(block)}
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


LABEL = "bushiroad 668"


def _item_url(pid):
    return f"https://www.square-bushiroad.com/product/{pid}"


def _state_product(product):
    """依是否有庫存數量決定存成字串或含 qty 的 dict，未知數量沿用舊字串格式。"""
    name = product.get("name", "")
    qty = product.get("qty")
    return {"name": name, "qty": qty} if qty is not None else name


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = load_state()

    # 每天只跑一次：今天已執行就跳過。
    if state.get("last_run_date") == today:
        print(f"今天({today})已執行過，跳過")
        return True

    try:
        page = fetch_html(
            LIST_URL,
            required_markers=("data-product-id=", "goods_name"),
            expected_path_prefix="/product-list/668",
        )
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: 抓取失敗，跳過本次（不更新狀態）：{e}")
        return False

    raw = parse_products(page)
    if not raw:
        print("WARN: 解析到 0 個商品（原始），跳過本次（不更新狀態、不誤報）")
        return False

    total = parse_total(page)
    if total is not None and len(raw) < total:
        print(f"ERROR: 只解析到 {len(raw)}/{total} 件，不更新基準")
        return False
    if any(not product.get("name") for product in raw.values()):
        print("ERROR: 有商品缺少名稱，不更新基準")
        return False

    # 只保留有貨商品（售完不追蹤、不入報告）
    current = {pid: _state_product(v) for pid, v in raw.items() if v.get("in_stock")}
    print(f"原始 {len(raw)} 件，有貨 {len(current)}，售完 {len(raw) - len(current)}")

    prev = state.get("products")

    if not isinstance(prev, dict):
        # 建立基準本身不是異動，只記 log 不發通知。
        print(f"首次執行，建立基準：{len(current)} 件商品")
        save_state({"products": current, "last_run_date": today})
        return True

    changes = diff_products(prev, current)

    if not has_changes(changes):
        print(f"無異動：{len(current)} 件商品")
        save_state({"products": current, "last_run_date": today})
        return True

    # 有異動：登記到本輪彙總通知。送出成功才更新狀態（含 last_run_date），
    # 失敗就保留舊基準，下個整點重新比對並重試。
    print("有異動，加入本輪彙總通知")
    digest.add(
        LABEL,
        changes,
        _item_url,
        lambda: save_state({"products": current, "last_run_date": today}),
    )
    return True


if __name__ == "__main__":
    ok = main()
    # 單獨執行時沒有 notify_digest 任務，自己把彙總通知送出。
    ok = digest.flush() and ok
    sys.exit(0 if ok else 1)
