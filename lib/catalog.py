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
            name = value if isinstance(value, str) else ""
            prices = []

            product = {
                "id": f"{definition['id']}__{product_id}",
                "sourceId": definition["id"],
                "sourceLabel": definition["label"],
                "productId": str(product_id),
                "name": name,
                "url": definition["url"](product_id),
                "prices": prices,
                "currency": "JPY",
                "active": True,
            }
            products.append(product)
            source_products.append(product)

        sources.append(
            {
                "id": definition["id"],
                "label": definition["label"],
                "schedule": definition["schedule"],
                "activeCount": len(source_products),
                "status": "ok",
                "lastRunDate": state.get("last_run_date"),
            }
        )

    return products, sources
