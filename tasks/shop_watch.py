# -*- coding: utf-8 -*-
"""任務：多站商品列表追蹤（每天一次）。

監看多個卡牌商店的列表頁，偵測「新增商品」並用 Telegram 通知（名稱 + 連結）。
各站結構不同，以 SITES 設定表 + 對應解析器處理。
狀態存於 state/shop_watch.json。

節流：每天只實際執行一次（UTC 日期）。任一站失敗則當天稍後重試，
已成功的站因基準已更新不會重複通知。
"""

import html
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
RAW_DROP_GUARD_MINIMUM = 10
RAW_DROP_GUARD_RATIO = 0.5
MOBILE_USER_AGENT = (
    "Mozilla/5.0 (iPhone; CPU iPhone OS 18_0 like Mac OS X) "
    "AppleWebKit/605.1.15 Version/18.0 Mobile/15E148 Safari/604.1"
)


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def _clean(s):
    return html.unescape(re.sub(r"\s+", " ", re.sub(r"<[^>]+>", " ", s)).strip())


def is_suspicious_raw_drop(previous_count, current_count):
    return (
        isinstance(previous_count, int)
        and previous_count >= RAW_DROP_GUARD_MINIMUM
        and current_count < previous_count * RAW_DROP_GUARD_RATIO
    )


def parse_count_number(html):
    """square-bushiroad / manasource / c-labo 共通的「N件」總數。"""
    m = re.search(r'count_number"?>\s*<span class="number">([\d,]+)</span>', html, re.S)
    return int(m.group(1).replace(",", "")) if m else None


def parse_fukufuku_count(html):
    m = re.search(r'product-list__result[^>]*>.*?<span>([\d,]+)</span>件', html, re.S)
    return int(m.group(1).replace(",", "")) if m else None


def parse_hobbystation_count(html):
    m = re.search(r'ec-searchnavRole__counter.*?ec-font-bold[^>]*>([\d,]+)件', html, re.S)
    return int(m.group(1).replace(",", "")) if m else None


# ---------------------------------------------------------------- 各站解析器
# 解析器一律回傳「原始」清單 {id(str): {"name": str, "in_stock": bool}}
# （含售完品；售完過濾在 main 統一處理，以免影響分頁件數估算）
# 每個 id 以「第一次出現」決定名稱與庫存（已驗證可靠）。


def parse_squarebushi(html):
    """square-bushiroad：data-product-id 切塊 + goods_name；在庫なし/soldout 為售完。"""
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
        products[pid] = {"name": _clean(nm.group(1)) if nm else "", "in_stock": in_stock}
    return products


def parse_product_links(html):
    """manasource / c-labo：/product/<id> 連結 + goods_name；在庫なし/soldout 為售完。"""
    products = {}
    matches = list(re.finditer(r'href="https?://[^"]*/product/(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        if pid in products:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        window = html[m.end():min(m.end() + 3000, end if end > m.end() else len(html))]
        in_stock = "在庫なし" not in window and "stock soldout" not in window
        nm = re.search(r'<span class="goods_name">(.*?)</span>', window, re.S)
        products[pid] = {"name": _clean(nm.group(1)) if nm else "", "in_stock": in_stock}
    return products


def parse_torecolo(html):
    """torecolo：/shop/g/g<編號> 區塊 + goods-name；「売切れ」為售完。"""
    products = {}
    for block in re.split(r'js-enhanced-ecommerce-item', html)[1:]:
        idm = re.search(r'/shop/g/g([^/?"#]+)/', block)
        if not idm:
            continue
        pid = idm.group(1)
        if pid in products:
            continue
        in_stock = "売切れ" not in block
        nm = re.search(r'class="[^"]*goods-name[^"]*"[^>]*>(.*?)</a>', block, re.S)
        products[pid] = {"name": _clean(nm.group(1)) if nm else "", "in_stock": in_stock}
    return products


def parse_fukufuku(html):
    """福福トレカ：商品標題連結 + 商品區塊內的品切れ訊息。"""
    products = {}
    for block in re.split(r'<li class="product-list__item">', html)[1:]:
        match = re.search(
            r'class="[^"]*product-list__item__title--name[^"]*"'
            r'[^>]+href="[^"]*/products/detail/(\d+)"[^>]*>(.*?)</a>',
            block,
            re.S,
        )
        if not match:
            continue
        product_id = match.group(1)
        if product_id in products:
            continue
        sold_out = any(marker in block for marker in ("品切れ", "売り切れ", "SOLD OUT"))
        products[product_id] = {
            "name": _clean(match.group(2)),
            "in_stock": not sold_out,
        }
    return products


def parse_hobbystation(html):
    """Hobby Station：商品詳細連結 + PC 商品名；SOLD OUT/disabled 為售完。"""
    products = {}
    for block in re.findall(r'<li(?:\s[^>]*)?>(.*?)</li>', html, re.S):
        id_match = re.search(r'href="[^"]*/ws/product/detail/(\d+)"', block)
        name_match = re.search(
            r'class="list_product_Name_pc".*?<a[^>]*>(.*?)</a>', block, re.S
        )
        if not id_match or not name_match:
            continue
        product_id = id_match.group(1)
        if product_id in products:
            continue
        sold_out = 'alt="SOLD OUT"' in block or re.search(
            r'class="shopCart"[^>]*\bdisabled\b', block
        )
        products[product_id] = {
            "name": _clean(name_match.group(1)),
            "in_stock": not sold_out,
        }
    return products


def parse_cardmax(html):
    """cardmax (MakeShop, EUC-JP)：支援手機版價格與舊桌面版清單。"""
    html = re.sub(r"<!--.*?-->", " ", html, flags=re.S)
    products = {}

    for block in re.findall(r'<li(?:\s[^>]*)?>(.*?)</li>', html, re.S):
        id_match = re.search(r'detail\.html\?id=(\d+)', block)
        name_match = re.search(r'<img[^>]+alt="([^"]+)"', block, re.S)
        if not id_match or not name_match:
            continue
        product_id = id_match.group(1)
        if product_id in products:
            continue
        sold_out = 'class="soldout"' in block or "売り切れ" in block
        price_match = re.search(
            r'<p[^>]+class="price"[^>]*>.*?<em>([\d,]+)</em>', block, re.S
        )
        prices = [int(price_match.group(1).replace(",", ""))] if price_match else []
        products[product_id] = {
            "name": _clean(name_match.group(1)),
            "in_stock": not sold_out,
            "prices": prices,
        }

    if products:
        return products

    matches = list(re.finditer(r'<a href="/shopdetail/(\d+)/[^"]*"[^>]*>(.*?)</a>', html, re.S))
    for i, m in enumerate(matches):
        pid = m.group(1)
        name = _clean(m.group(2))
        if not name or pid in products:  # 略過純圖片連結與重複
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        after = html[m.end():min(m.end() + 400, end if end > m.end() else len(html))]
        price_match = re.search(r'([\d,]+)円', after)
        prices = [int(price_match.group(1).replace(",", ""))] if price_match else []
        products[pid] = {
            "name": name,
            "in_stock": "売り切れ" not in after,
            "prices": prices,
        }
    return products


def parse_gurapan(html):
    """gurapan (EC-CUBE)：/products/detail/<id> + item-name；SOLD OUT/品切/売り切れ 為售完。"""
    products = {}
    matches = list(re.finditer(r'href="[^"]*/products/detail/(\d+)"', html))
    for i, m in enumerate(matches):
        pid = m.group(1)
        if pid in products:
            continue
        end = matches[i + 1].start() if i + 1 < len(matches) else len(html)
        window = html[m.end():min(m.end() + 3000, end if end > m.end() else len(html))]
        in_stock = not (
            "SOLD OUT" in window.upper() or "品切" in window or "売り切れ" in window
        )
        nm = re.search(r'class="ec-shelfGrid__item-name">(.*?)</p>', window, re.S)
        products[pid] = {"name": _clean(nm.group(1)) if nm else "", "in_stock": in_stock}
    return products


# ---------------------------------------------------------------- 抓取（含分頁）


def _set_query(url, key, value):
    parts = urllib.parse.urlparse(url)
    q = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    q[key] = str(value)
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))


def fetch_paged(
    url,
    parser,
    page_param="page",
    encoding=None,
    required_markers=(),
    count_parser=None,
):
    """抓第 1 頁；若 count_number 顯示還有更多則翻頁補齊。"""
    expected_path = urllib.parse.urlparse(url).path
    page_html = fetch_html(
        url,
        encoding=encoding,
        required_markers=required_markers,
        expected_path_prefix=expected_path,
    )
    products = parser(page_html)
    total = (count_parser or parse_count_number)(page_html)
    if total is not None and products:
        per_page = len(products)
        pages = min(math.ceil(total / per_page), MAX_PAGES)
        for p in range(2, pages + 1):
            try:
                page_url = _set_query(url, page_param, p)
                next_html = fetch_html(
                    page_url,
                    encoding=encoding,
                    required_markers=required_markers,
                    expected_path_prefix=expected_path,
                )
                page_products = parser(next_html)
            except Exception as e:  # noqa: BLE001
                raise RuntimeError(f"第 {p} 頁抓取失敗：{e}") from e
            if not page_products:
                raise RuntimeError(f"第 {p} 頁解析到 0 件")
            before = len(products)
            products.update(page_products)
            if len(products) >= total or len(products) == before:
                break
    if total is not None and len(products) < total:
        raise RuntimeError(f"只解析到 {len(products)}/{total} 件")
    return products


# ---------------------------------------------------------------- 站台設定

SITES = [
    {
        "key": "bushiroad_284",
        "label": "square-bushiroad 284",
        "fetch": lambda: fetch_paged(
            "https://www.square-bushiroad.com/product-list/284",
            parse_squarebushi,
            required_markers=("data-product-id=", "goods_name"),
        ),
        "item_url": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
    },
    {
        "key": "torecolo",
        "label": "torecolo ヴァイス新品",
        "fetch": lambda: parse_torecolo(
            fetch_html(
                "https://www.torecolo.jp/shop/c/c10309996/",
                required_markers="js-enhanced-ecommerce-item",
                expected_path_prefix="/shop/c/c10309996/",
            )
        ),
        "item_url": lambda pid: f"https://www.torecolo.jp/shop/g/g{pid}/",
    },
    {
        "key": "manasource",
        "label": "manasource 2268",
        "fetch": lambda: fetch_paged(
            "https://www.manasource.net/product-list/2268/0/photo",
            parse_product_links,
            required_markers=("/product/", "goods_name"),
        ),
        "item_url": lambda pid: f"https://www.manasource.net/product/{pid}",
    },
    {
        "key": "cardmax",
        "label": "cardmax ct1849",
        "revision": 2,
        "require_prices": True,
        "fetch": lambda: parse_cardmax(
            fetch_html(
                "https://www.cardmax.jp/smartphone/list.html?category_code=ct1849",
                encoding="euc_jp",
                required_markers=('id="list_item"', 'class="price"'),
                expected_path_prefix="/smartphone/list.html",
                user_agent=MOBILE_USER_AGENT,
            )
        ),
        "item_url": lambda pid: f"https://www.cardmax.jp/shopdetail/{pid}/",
    },
    {
        "key": "gurapan",
        "label": "gurapan 1081",
        "fetch": lambda: parse_gurapan(
            fetch_html(
                "https://gurapan.jp/products/list?category_id=1081",
                required_markers="/products/detail/",
                expected_path_prefix="/products/list",
            )
        ),
        "item_url": lambda pid: f"https://gurapan.jp/products/detail/{pid}",
    },
    {
        "key": "clabo",
        "label": "c-labo 2421(有庫存)",
        "fetch": lambda: fetch_paged(
            "https://www.c-labo-online.jp/product-list/2421/0/photo?num=60&available=1",
            parse_product_links,
            required_markers=("/product/", "goods_name"),
        ),
        "item_url": lambda pid: f"https://www.c-labo-online.jp/product/{pid}",
    },
    {
        "key": "fukufuku_deck",
        "label": "福福トレカ WSデッキ販売",
        "fetch": lambda: fetch_paged(
            "https://weis.fukufukutoreka.com/products/list?category_id=2",
            parse_fukufuku,
            page_param="pageno",
            required_markers=("product-list__result", "/products/detail/"),
            count_parser=parse_fukufuku_count,
        ),
        "item_url": lambda pid: f"https://weis.fukufukutoreka.com/products/detail/{pid}",
    },
    {
        "key": "torecolo_deck",
        "label": "torecolo WSデッキ販売",
        "fetch": lambda: parse_torecolo(
            fetch_html(
                "https://www.torecolo.jp/shop/c/c10309010/",
                required_markers="js-enhanced-ecommerce-item",
                expected_path_prefix="/shop/c/c10309010/",
            )
        ),
        "item_url": lambda pid: f"https://www.torecolo.jp/shop/g/g{pid}/",
    },
    {
        "key": "clabo_deck",
        "label": "c-labo WSデッキ販売",
        "fetch": lambda: fetch_paged(
            "https://www.c-labo-online.jp/product-list/1070/0/photo?num=120&available=1&sort=&Submit=",
            parse_product_links,
            required_markers=("/product/", "goods_name"),
        ),
        "item_url": lambda pid: f"https://www.c-labo-online.jp/product/{pid}",
    },
    {
        "key": "hobbystation_deck",
        "label": "Hobby Station WSデッキ販売",
        "fetch": lambda: fetch_paged(
            "https://www.hobbystation-single.jp/ws/product/list?HbstSearchOptions%5B0%5D%5Bid%5D=16&HbstSearchOptions%5B0%5D%5Bsearch_keyword%5D=%28BANNER%29%E3%82%AA%E3%83%AA%E3%82%B8%E3%83%8A%E3%83%AB%E3%83%87%E3%83%83%E3%82%AD%28BANNER%29&HbstSearchOptions%5B0%5D%5BType%5D=2",
            parse_hobbystation,
            page_param="pageno",
            required_markers=("searchRsultList", "ec-searchnavRole__counter"),
            count_parser=parse_hobbystation_count,
        ),
        "item_url": lambda pid: f"https://www.hobbystation-single.jp/ws/product/detail/{pid}",
    },
    {
        "key": "gurapan_deck",
        "label": "gurapan WSデッキ販売",
        "fetch": lambda: parse_gurapan(
            fetch_html(
                "https://gurapan.jp/products/list?category_id=1253",
                required_markers="/products/detail/",
                expected_path_prefix="/products/list",
            )
        ),
        "item_url": lambda pid: f"https://gurapan.jp/products/detail/{pid}",
    },
    {
        "key": "bushiroad_deck",
        "label": "square-bushiroad WSデッキ販売",
        "fetch": lambda: fetch_paged(
            "https://www.square-bushiroad.com/product-group/78",
            parse_squarebushi,
            required_markers=("WSデッキ販売", "count_number"),
        ),
        "item_url": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
        "allow_empty": True,
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


def _product_name(value):
    if isinstance(value, dict):
        return value.get("name", "")
    return value if isinstance(value, str) else ""


def _state_product(product):
    name = product.get("name", "")
    prices = product.get("prices", [])
    return {"name": name, "prices": prices} if prices else name


def notify_new_items(site, new_ids, current):
    lines = [f"🆕 <b>{esc(site['label'])} 新增商品 ({len(new_ids)})</b>", ""]
    for pid in new_ids[:NOTIFY_MAX_ITEMS]:
        product_name = _product_name(current[pid])
        name = esc(product_name) if product_name else f"商品 {pid}"
        lines.append(f"• <b>{name}</b>\n  {site['item_url'](pid)}")
    if len(new_ids) > NOTIFY_MAX_ITEMS:
        lines.append(f"…等共 {len(new_ids)} 件")
    return send_telegram("\n".join(lines))


def main():
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    state = load_state()
    sites_state = state.setdefault("sites", {})
    missing_site_keys = {site["key"] for site in SITES} - set(sites_state)
    stale_site_keys = {
        site["key"]
        for site in SITES
        if site.get("revision") is not None
        and sites_state.get(site["key"], {}).get("revision") != site["revision"]
    }
    pending_site_keys = missing_site_keys | stale_site_keys

    if state.get("last_run_date") == today and not pending_site_keys:
        print(f"今天({today})已執行過，跳過")
        return True

    sites_to_run = (
        [site for site in SITES if site["key"] in pending_site_keys]
        if state.get("last_run_date") == today
        else SITES
    )

    first_run = not sites_state
    startup_summary = []
    all_ok = True

    for site in sites_to_run:
        key = site["key"]
        try:
            raw = site["fetch"]()
        except Exception as e:  # noqa: BLE001
            print(f"ERROR: [{key}] 抓取失敗：{e}")
            all_ok = False
            continue

        if not raw and not site.get("allow_empty"):
            # 原始清單為空 = 疑似抓取/解析問題（非「全部售完」），保守跳過。
            print(f"WARN: [{key}] 解析到 0 件（原始），跳過（不更新基準、不誤報）")
            all_ok = False
            continue

        missing_names = sum(not product.get("name") for product in raw.values())
        if missing_names:
            print(f"ERROR: [{key}] {missing_names} 件商品缺少名稱，跳過（不更新基準）")
            all_ok = False
            continue

        missing_prices = sum(
            product.get("in_stock") and not product.get("prices")
            for product in raw.values()
        )
        if site.get("require_prices") and missing_prices:
            print(f"ERROR: [{key}] {missing_prices} 件有貨商品缺少價格，跳過（不更新基準）")
            all_ok = False
            continue

        previous_site_state = sites_state.get(key, {})
        previous_raw_count = previous_site_state.get("raw_count")
        if raw and is_suspicious_raw_drop(previous_raw_count, len(raw)):
            print(
                f"ERROR: [{key}] 原始商品數由 {previous_raw_count} 驟降為 {len(raw)}，"
                "跳過（不更新基準）"
            )
            all_ok = False
            continue

        # 只保留有貨商品（售完不追蹤、不入報告）
        current = {pid: _state_product(v) for pid, v in raw.items() if v.get("in_stock")}
        sold = len(raw) - len(current)
        print(f"[{key}] 原始 {len(raw)} 件，有貨 {len(current)}，售完 {sold}")

        prev = sites_state.get(key, {}).get("products")

        if not isinstance(prev, dict):
            print(f"[{key}] 首次執行，建立基準：{len(current)} 件（有貨）")
            sites_state[key] = {"products": current, "raw_count": len(raw)}
            if site.get("revision") is not None:
                sites_state[key]["revision"] = site["revision"]
            startup_summary.append(f"• {esc(site['label'])}：{len(current)} 件（有貨）")
            continue

        new_ids = [pid for pid in current if pid not in prev]
        if not new_ids:
            print(f"[{key}] 無新增：{len(current)} 件")
            sites_state[key] = {"products": current, "raw_count": len(raw)}
            if site.get("revision") is not None:
                sites_state[key]["revision"] = site["revision"]
            continue

        print(f"[{key}] 新增 {len(new_ids)} 件，發送通知")
        if notify_new_items(site, new_ids, current):
            sites_state[key] = {"products": current, "raw_count": len(raw)}
            if site.get("revision") is not None:
                sites_state[key]["revision"] = site["revision"]
        else:
            print(f"[{key}] 通知失敗，保留舊基準，稍後重試")
            all_ok = False

    if startup_summary:
        if not send_telegram(
            "✅ <b>多站商品追蹤已啟動</b>\n\n"
            + "\n".join(startup_summary)
            + "\n\n之後每天檢查一次，有新增商品會逐站通知。"
        ):
            all_ok = False

    if all_ok:
        state["last_run_date"] = today
    else:
        print("部分站台失敗，今天稍後將重試（已成功站台不會重複通知）")
    save_state(state)
    if first_run:
        print(f"首次執行完成：{len(startup_summary)}/{len(SITES)} 站建立基準")
    return all_ok


if __name__ == "__main__":
    main()
