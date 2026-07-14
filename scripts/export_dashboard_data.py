#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""產生前端在未連接 Firebase 時使用的本機預覽資料。"""

import json
import os
import sys
from datetime import datetime, timezone

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, REPO_ROOT)

from lib.catalog import collect_catalog  # noqa: E402


def main():
    products, sources = collect_catalog(REPO_ROOT)
    output_path = os.path.join(REPO_ROOT, "web", "public", "demo-data.json")
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    payload = {
        "generatedAt": datetime.now(timezone.utc).isoformat(),
        "products": products,
        "sources": sources,
        "events": [],
    }
    with open(output_path, "w", encoding="utf-8") as file:
        json.dump(payload, file, ensure_ascii=False, separators=(",", ":"))
    print(f"已產生網站預覽資料：{len(products)} 件商品")


if __name__ == "__main__":
    main()
