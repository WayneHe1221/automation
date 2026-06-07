# -*- coding: utf-8 -*-
"""任務：cardshop-serra 商品列表監控。

抓取列表頁（含分頁）-> 解析每個商品(id/名稱/價格) -> 與上次比較
-> 偵測「新增商品 / 價格異動 / 下架」-> 有變化就用 Telegram 通知。
狀態存於 repo 的 state/cardshop_list.json，由 GitHub Actions 跑完 commit 回來。
"""

import json
import math
import os
import re
import sys
import urllib.parse

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.fetch import fetch_html  # noqa: E402
from lib.notify import send_telegram  # noqa: E402

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_PATH = os.path.join(REPO_ROOT, "state", "cardshop_list.json")

DEFAULT_LIST_URL = (
    "https://cardshop-serra.com/ws/products/list"
    "?name=&attr_17=&stock_status=1&disp_number=0&orderby=4&pageno=1"
)
LIST_URL = os.environ.get("CARDSHOP_LIST_URL", DEFAULT_LIST_URL)

MAX_PAGES = 20  # 分頁安全上限


def set_pageno(url, pageno):
    parts = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    q["pageno"] = str(pageno)
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))


def parse_total(html):
    m = re.search(r"([\d,]+)\s*件中", html)
    return int(m.group(1).replace(",", "")) if m else None


def _unescape(s):
    for a, b in (("&amp;", "&"), ("&lt;", "<"), ("&gt;", ">"), ("&quot;", '"'), ("&#39;", "'")):
        s = s.replace(a, b)
    return s


def _prices_in_block(block):
    """取出商品區塊內所有現價(去掉劃線原價)，回傳排序 distinct list。"""
    prices = set()
    for td in re.findall(
        r'<td class="product-list__item__table--price">(.*?)</td>', block, re.S
    ):
        td = re.sub(
            r'<span class="product-list__item__table--price-original">.*?</span>',
            " ",
            td,
            flags=re.S,
        )
        m = re.search(r"([\d,]+)\s*円", td)
        if m:
            digits = m.group(1).replace(",", "")
            if digits:
                prices.add(int(digits))
    return sorted(prices)


def parse_products(html):
    """解析列表頁 -> {id(str): {"name": str, "prices": [int,...]}}。"""
    products = {}
    marker = r'<a href="https?://[^"]*?/products/detail/(\d+)"\s+class="product-list__item__img">'
    matches = list(re.finditer(marker, html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        start = m.start()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        block = html[start:end]

        name = ""
        nm = re.search(
            r'class="product-list__item__title--name[^"]*"[^>]*>(.*?)</a>', block, re.S
        )
        if nm:
            name = _unescape(re.sub(r"<[^>]+>", "", nm.group(1)).strip())

        prices = _prices_in_block(block)
        if pid in products:
            products[pid]["prices"] = sorted(set(products[pid]["prices"]) | set(prices))
            if not products[pid]["name"] and name:
                products[pid]["name"] = name
        else:
            products[pid] = {"name": name, "prices": prices}
    return products


def fetch_all_products(list_url):
    html1 = fetch_html(set_pageno(list_url, 1))
    total = parse_total(html1)
    products = parse_products(html1)
    if total is not None:
        per_page = max(len(products), 1)
        pages = min(math.ceil(total / per_page), MAX_PAGES)
        for p in range(2, pages + 1):
            try:
                page_products = parse_products(fetch_html(set_pageno(list_url, p)))
            except Exception as e:  # noqa: BLE001
                print(f"WARN: 第 {p} 頁抓取失敗：{e}")
                break
            if not page_products:
                break
            products.update(page_products)
            if len(products) >= total:
                break
    return products, total


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


def yen_list(prices):
    return " / ".join(f"{p:,}円" for p in prices) if prices else "—"


def link(pid, name):
    label = name if name else f"商品 {pid}"
    return f'<a href="https://cardshop-serra.com/ws/products/detail/{pid}">{label}</a>'


def main():
    try:
        current, total = fetch_all_products(LIST_URL)
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: 抓取列表失敗，跳過本次（不更新狀態）：{e}")
        return

    if not current:
        print("WARN: 列表解析到 0 個商品，跳過本次（不更新狀態、不誤報）")
        return
    if total is not None and len(current) < total:
        print(f"WARN: 只解析到 {len(current)}/{total} 件（可能分頁未抓全）")

    state = load_state()
    prev = state.get("products")

    if not isinstance(prev, dict):
        print(f"首次執行，建立基準：{len(current)} 件商品")
        send_telegram(
            f"✅ <b>列表監控已啟動</b>\n\n"
            f"目前共 <b>{len(current)}</b> 件商品。\n"
            f"之後每小時檢查一次，有<b>新增商品</b>或<b>價格異動</b>會立刻通知你。"
        )
        save_state({"products": current})
        return

    cur_ids, prev_ids = set(current), set(prev)
    new_ids = [i for i in current if i not in prev_ids]
    removed_ids = [i for i in prev if i not in cur_ids]
    changed = [
        (pid, prev[pid].get("prices", []), current[pid].get("prices", []))
        for pid in current
        if pid in prev and prev[pid].get("prices", []) != current[pid].get("prices", [])
    ]

    if not new_ids and not removed_ids and not changed:
        print(f"無變化：{len(current)} 件商品")
        save_state({"products": current})
        return

    sections = []
    if new_ids:
        lines = [f"🆕 <b>新增商品 ({len(new_ids)})</b>"]
        lines += [f"• {link(pid, current[pid]['name'])} — {yen_list(current[pid]['prices'])}" for pid in new_ids]
        sections.append("\n".join(lines))
    if changed:
        lines = [f"💱 <b>價格異動 ({len(changed)})</b>"]
        for pid, old_p, new_p in changed:
            lines.append(f"• {link(pid, current[pid]['name'])}\n   {yen_list(old_p)} → <b>{yen_list(new_p)}</b>")
        sections.append("\n".join(lines))
    if removed_ids:
        lines = [f"❌ <b>下架/售完 ({len(removed_ids)})</b>"]
        lines += [f"• {link(pid, prev[pid].get('name', ''))}" for pid in removed_ids]
        sections.append("\n".join(lines))

    message = "🔔 <b>商品列表有變化</b>\n\n" + "\n\n".join(sections)
    print(f"變化：新增 {len(new_ids)}、異動 {len(changed)}、下架 {len(removed_ids)}，發送通知")
    if send_telegram(message):
        save_state({"products": current})
    else:
        print("通知失敗，保留舊基準，下次重試")


if __name__ == "__main__":
    main()
