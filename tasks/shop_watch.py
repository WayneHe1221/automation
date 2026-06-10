# -*- coding: utf-8 -*-
"""任務：多站商品列表追蹤（每天一次）。

監看多個卡牌商店的列表頁，偵測「新增商品」並用 Telegram 通知（名稱 + 連結）。
各站結構不同，以 SITES 設定表 + 對應解析器處理。
狀態存於 state/shop_watch.json。

節流：每天只實際執行一次（UTC 日期）。任一站失敗則當天稍後重試，
已成功的站因基準已更新不會重複通知。
"""

import json
import math
import os
import re
import sys
import urllib.parse
from datetime import datetime, timezone

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.fetch import fetch_html  # noqa: E402
from lib.notify import send_telegram  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "state", "shop_watch.json")

MAX_PAGES = 10  # 分頁安全上限
NOTIFY_MAX_ITEMS = 25  # 單站單則訊息最多列出幾件，其餘以「…等 N 件」收尾


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _unescape(s):
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return s


def _clean(s):
    return _unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip())


def parse_count_number(html):
    """square-bushiroad / manasource / c-labo 共通的「N件」總數。"""
    m = re.search(r'count_number"?>\s*<span class="number">([\d,]+)</span>', html, re.S)
    return int(m.group(1).replace(",", "")) if m else None


# ---------------------------------------------------------------- 各站解析器
# 解析器一律回傳 {id(str): name(str)}


def parse_squarebushi(html):
    """square-bushiroad：data-product-id 切塊 + goods_name。"""
    products = {}
    matches = list(re.finditer(r'data-product-id="(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        block = html[m.end():end]
        nm = re.search(r'<span class="goods_name">(.*?)</span>', block, re.S)
        name = _clean(nm.group(1)) if nm else ""
        if pid not in products or (name and not products[pid]):
            products[pid] = name
    return products


def parse_product_links(html):
    """manasource / c-labo：/product/<id> 連結 + 後續 goods_name。"""
    products = {}
    matches = list(re.finditer(r'href="https?://[^"]*/product/(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        window = html[m.end():min(m.end() + 3000, end if end > m.end() else len(html))]
        nm = re.search(r'<span class="goods_name">(.*?)</span>', window, re.S)
        name = _clean(nm.group(1)) if nm else ""
        if pid not in products or (name and not products[pid]):
            products[pid] = name
    return products


def parse_torecolo(html):
    """torecolo：/shop/g/g<編號> 連結 + goods-name 錨點文字。"""
    products = {}
    blocks = re.split(r'js-enhanced-ecommerce-item', html)[1:]
    for block in blocks:
        idm = re.search(r'/shop/g/g(\w+)', block)
        if not idm:
            continue
        pid = idm.group(1)
        nm = re.search(r'class="[^"]*goods-name[^"]*"[^>]*>(.*?)</a>', block, re.S)
        name = _clean(nm.group(1)) if nm else ""
        if pid not in products or (name and not products[pid]):
            products[pid] = name
    return products


def parse_cardmax(html):
    """cardmax (MakeShop, EUC-JP)：/shopdetail/<id>/ 連結文字即名稱。
    需先移除 HTML 註解（內含舊廣告的 shopdetail 連結）。"""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    products = {}
    for m in re.finditer(r'<a href="/shopdetail/(\d+)/[^"]*"[^>]*>(.*?)</a>', html, re.S):
        pid, inner = m.group(1), m.group(2)
        name = _clean(inner)
        if pid not in products or (name and not products[pid]):
            products[pid] = name
    # 過濾沒名稱的（純圖片/按鈕連結若同 id 已有名稱則保留名稱版）
    return {pid: nm for pid, nm in products.items() if nm}


def parse_gurapan(html):
    """gurapan (EC-CUBE)：/products/detail/<id> + ec-shelfGrid__item-name。"""
    products = {}
    matches = list(re.finditer(r'href="[^"]*/products/detail/(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        window = html[m.end():min(m.end() + 3000, end if end > m.end() else len(html))]
        nm = re.search(r'class="ec-shelfGrid__item-name">(.*?)</p>', window, re.S)
        name = _clean(nm.group(1)) if nm else ""
        if pid not in products or (name and not products[pid]):
            products[pid] = name
    return products


# ---------------------------------------------------------------- 抓取（含分頁）


def _set_query(url, key, value):
    parts = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    q[key] = str(value)
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))


def fetch_paged(url, parser, page_param="page", encoding=None):
    """抓第 1 頁；若 count_number 顯示還有更多則翻頁補齊。"""
    html = fetch_html(url, encoding=encoding)
    products = parser(html)
    total = parse_count_number(html)
    if total is not None and products:
        per_page = len(products)
        pages = min(math.ceil(total / per_page), MAX_PAGES)
        for p in range(2, pages + 1):
            try:
                page_products = parser(fetch_html(_set_query(url, page_param, p), encoding=encoding))
            except Exception as e:  # noqa: BLE001
                print(f"WARN: 第 {p} 頁抓取失敗：{e}")
                break
            if not page_products:
                break
            before = len(products)
            products.update(page_products)
            if len(products) >= total or len(products) == before:
                break
    if total is not None and len(products) < total:
        print(f"WARN: 只解析到 {len(products)}/{total} 件")
    return products


# ---------------------------------------------------------------- 站台設定

SITES = [
    {
        "key": "bushiroad_284",
        "label": "square-bushiroad 284",
        "fetch": lambda: fetch_paged(
            "https://www.square-bushiroad.com/product-list/284", parse_squarebushi
        ),
        "item_url": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
    },
    {
        "key": "torecolo",
        "label": "torecolo ヴァイス新品",
        "fetch": lambda: parse_torecolo(fetch_html("https://www.torecolo.jp/shop/c/c10309996/")),
        "item_url": lambda pid: f"https://www.torecolo.jp/shop/g/g{pid}/",
    },
    {
        "key": "manasource",
        "label": "manasource 2268",
        "fetch": lambda: fetch_paged(
            "https://www.manasource.net/product-list/2268/0/photo", parse_product_links
        ),
        "item_url": lambda pid: f"https://www.manasource.net/product/{pid}",
    },
    {
        "key": "cardmax",
        "label": "cardmax ct1849",
        "fetch": lambda: parse_cardmax(
            fetch_html("https://www.cardmax.jp/shopbrand/ct1849/", encoding="euc_jp")
        ),
        "item_url": lambda pid: f"https://www.cardmax.jp/shopdetail/{pid}/",
    },
    {
        "key": "gurapan",
        "label": "gurapan 1081",
        "fetch": lambda: parse_gurapan(
            fetch_html("https://gurapan.jp/products/list?category_id=1081")
        ),
        "item_url": lambda pid: f"https://gurapan.jp/products/detail/{pid}",
    },
    {
        "key": "clabo",
        "label": "c-labo 2421(有庫存)",
        "fetch": lambda: fetch_paged(
            "https://www.c-labo-online.jp/product-list/2421/0/photo?num=60&available=1",
            parse_product_links,
        ),
        "item_url": lambda pid: f"https://www.c-labo-online.jp/product/{pid}",
    },
]


# ---------------------------------------------------------------- 狀態與主流程


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


def notify_new_items(site, new_ids, current):
    lines = [f"🆕 <b>{esc(site['label'])} 新增商品 ({len(new_ids)})</b>", ""]
    for pid in new_ids[:NOTIFY_MAX_ITEMS]:
        name = esc(current[pid]) if current[pid] else f"商品 {pid}"
        lines.append(f"• <b>{name}</b>\n  {site['item_url'](pid)}")
    if len(new_ids) > NOTIFY_MAX_ITEMS:
        lines.append(f"…等共 {len(new_ids)} 件")
    return send_telegram("\n".join(lines))


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = load_state()

    if state.get("last_run_date") == today:
        print(f"今天({today})已執行過，跳過")
        return

    sites_state = state.setdefault("sites", {})
    first_run = not sites_state
    startup_summary = []
    all_ok = True

    for site in SITES:
        key = site["key"]
        try:
            current = site["fetch"]()
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: [{key}] 抓取失敗：{e}")
            all_ok = False
            continue

        if not current:
            print(f"WARN: [{key}] 解析到 0 件，跳過（不更新基準、不誤報）")
            all_ok = False
            continue

        prev = sites_state.get(key, {}).get("products")

        if not isinstance(prev, dict):
            print(f"[{key}] 首次執行，建立基準：{len(current)} 件")
            sites_state[key] = {"products": current}
            startup_summary.append(f"• {esc(site['label'])}：{len(current)} 件")
            continue

        new_ids = [pid for pid in current if pid not in prev]
        if not new_ids:
            print(f"[{key}] 無新增：{len(current)} 件")
            sites_state[key] = {"products": current}
            continue

        print(f"[{key}] 新增 {len(new_ids)} 件，發送通知")
        if notify_new_items(site, new_ids, current):
            sites_state[key] = {"products": current}
        else:
            print(f"[{key}] 通知失敗，保留舊基準，稍後重試")
            all_ok = False

    if startup_summary:
        send_telegram(
            "✅ <b>多站商品追蹤已啟動</b>\n\n"
            + "\n".join(startup_summary)
            + "\n\n之後每天檢查一次，有新增商品會逐站通知。"
        )

    if all_ok:
        state["last_run_date"] = today
    else:
        print("部分站台失敗，今天稍後將重試（已成功站台不會重複通知）")
    save_state(state)
    if first_run:
        print(f"首次執行完成：{len(startup_summary)}/{len(SITES)} 站建立基準")


if __name__ == "__main__":
    main()
