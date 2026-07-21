# -*- coding: utf-8 -*-
"""將各監控任務的 state 轉成網站與 Firestore 共用格式。"""

import json
import os


RETIRED_SOURCE_IDS = {"cardshop_serra"}


SOURCE_DEFINITIONS = [
    {
        "id": "bushiroad_668",
        "label": "square-bushiroad 668",
        "schedule": "每天",
        "state_file": "bushiroad_668.json",
        "state_key": None,
        "url": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
    },
    {
        "id": "torecolo",
        "label": "torecolo ヴァイス新品",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "torecolo",
        "url": lambda pid: f"https://www.torecolo.jp/shop/g/g{pid}/",
    },
    {
        "id": "clabo",
        "label": "c-labo 2421",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "clabo",
        "url": lambda pid: f"https://www.c-labo-online.jp/product/{pid}",
    },
    {
        "id": "gurapan",
        "label": "gurapan 1081",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "gurapan",
        "url": lambda pid: f"https://gurapan.jp/products/detail/{pid}",
    },
    {
        "id": "manasource",
        "label": "manasource 2268",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "manasource",
        "url": lambda pid: f"https://www.manasource.net/product/{pid}",
    },
    {
        "id": "cardmax",
        "label": "cardmax ct1849",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "cardmax",
        "url": lambda pid: f"https://www.cardmax.jp/shopdetail/{pid}/",
    },
    {
        "id": "bushiroad_284",
        "label": "square-bushiroad 284",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "bushiroad_284",
        "url": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
    },
    {
        "id": "fukufuku_deck",
        "category": "deck",
        "label": "福福トレカ WSデッキ販売",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "fukufuku_deck",
        "url": lambda pid: f"https://weis.fukufukutoreka.com/products/detail/{pid}",
    },
    {
        "id": "torecolo_deck",
        "category": "deck",
        "label": "torecolo WSデッキ販売",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "torecolo_deck",
        "url": lambda pid: f"https://www.torecolo.jp/shop/g/g{pid}/",
    },
    {
        "id": "clabo_deck",
        "category": "deck",
        "label": "c-labo WSデッキ販売",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "clabo_deck",
        "url": lambda pid: f"https://www.c-labo-online.jp/product/{pid}",
    },
    {
        "id": "hobbystation_deck",
        "category": "deck",
        "label": "Hobby Station WSデッキ販売",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "hobbystation_deck",
        "url": lambda pid: f"https://www.hobbystation-single.jp/ws/product/detail/{pid}",
    },
    {
        "id": "gurapan_deck",
        "category": "deck",
        "label": "gurapan WSデッキ販売",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "gurapan_deck",
        "url": lambda pid: f"https://gurapan.jp/products/detail/{pid}",
    },
    {
        "id": "bushiroad_deck",
        "category": "deck",
        "label": "square-bushiroad WSデッキ販売",
        "schedule": "每天",
        "state_file": "shop_watch.json",
        "state_key": "bushiroad_deck",
        "url": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
    },
]


def _load_json(path):
    try:
        with open(path, encoding="utf-8") as file:
            data = json.load(file)
            return data if isinstance(data, dict) else None
    except (OSError, json.JSONDecodeError):
        return None


def collect_catalog(repo_root):
    """回傳 products、sources；只包含已有有效 state 的來源。"""
    state_dir = os.path.join(repo_root, "state")
    state_cache = {}
    products = []
    sources = []

    for definition in SOURCE_DEFINITIONS:
        category = definition.get("category", "product")
        state_file = definition["state_file"]
        if state_file not in state_cache:
            state_cache[state_file] = _load_json(os.path.join(state_dir, state_file))
        state = state_cache[state_file]
        if state is None:
            continue

        if definition["state_key"] is None:
            source_state = state
        else:
            source_state = state.get("sites", {}).get(definition["state_key"])
        if not isinstance(source_state, dict):
            continue

        raw_products = source_state.get("products")
        if not isinstance(raw_products, dict):
            continue

        source_products = []
        for product_id, value in raw_products.items():
            if isinstance(value, dict):
                name = value.get("name", "")
                prices = value.get("prices", [])
                qty = value.get("qty")
            else:
                name = value if isinstance(value, str) else ""
                prices = []
                qty = None

            product = {
                "id": f"{definition['id']}__{product_id}",
                "sourceId": definition["id"],
                "sourceLabel": definition["label"],
                "productId": str(product_id),
                "name": name,
                "url": definition["url"](product_id),
                "prices": prices,
                "qty": qty,
                "currency": "JPY",
                "category": category,
                "active": True,
            }
            products.append(product)
            source_products.append(product)

        stock_quantity = sum(
            product["qty"] for product in source_products if product["qty"] is not None
        )
        sources.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "schedule": definition["schedule"],
                "category": category,
                "activeCount": len(source_products),
                "stockQuantity": stock_quantity,
                "status": "ok",
                "lastRunDate": state.get("last_run_date"),
            }
        )

    return products, sources
