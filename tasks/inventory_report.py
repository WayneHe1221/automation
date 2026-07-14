# -*- coding: utf-8 -*-
"""任務：產生追蹤商品清單報告 inventory_report.md。

讀取各任務的 state/*.json，輸出含連結的 Markdown 清單到 repo 根目錄。
內容只取決於商品資料（不含會每次變動的時間戳），因此只有在追蹤商品
實際變動時檔案才會變、才會被 commit，不會洗版。

ORDER 設為 900：在所有抓取任務之後才執行，確保報告反映本次最新狀態。
"""

import json
import os

ORDER = 900

REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
STATE_DIR = os.path.join(REPO_ROOT, "state")
REPORT_PATH = os.path.join(REPO_ROOT, "inventory_report.md")


def _load(name):
    path = os.path.join(STATE_DIR, name)
    if os.path.exists(path):
        try:
            with open(path, encoding="utf-8") as f:
                return json.load(f)
        except (OSError, json.JSONDecodeError):
            pass
    return {}


# 各來源的商品頁連結組法
URL = {
    "bushiroad": lambda pid: f"https://www.square-bushiroad.com/product/{pid}",
    "torecolo": lambda pid: f"https://www.torecolo.jp/shop/g/g{pid}/",
    "manasource": lambda pid: f"https://www.manasource.net/product/{pid}",
    "cardmax": lambda pid: f"https://www.cardmax.jp/shopdetail/{pid}/",
    "gurapan": lambda pid: f"https://gurapan.jp/products/detail/{pid}",
    "clabo": lambda pid: f"https://www.c-labo-online.jp/product/{pid}",
    "fukufuku": lambda pid: f"https://weis.fukufukutoreka.com/products/detail/{pid}",
    "hobbystation": lambda pid: f"https://www.hobbystation-single.jp/ws/product/detail/{pid}",
}


def _md_escape(s):
    """避免商品名中的 ] 破壞 Markdown 連結語法。"""
    return s.replace("[", "(").replace("]", ")")


def _item_line(name, url, suffix=""):
    label = _md_escape(name) if name else url
    return f"- [{label}]({url}){suffix}"


def build_report():
    lines = ["# 追蹤商品清單", ""]
    lines.append("> 由 GitHub Actions 自動更新；內容隨追蹤商品變動而變。")
    lines.append("")
    total = 0

    # square-bushiroad 668
    b6 = _load("bushiroad_668.json").get("products", {})
    lines.append(f"## square-bushiroad 668（每天）— {len(b6)} 件")
    lines.append("")
    for pid, name in b6.items():
        lines.append(_item_line(name, URL["bushiroad"](pid)))
    if b6:
        lines.append("")
    total += len(b6)

    # shop_watch 多站
    sw = _load("shop_watch.json").get("sites", {})
    sw_sites = [
        ("torecolo", "torecolo ヴァイス新品", "torecolo"),
        ("clabo", "c-labo 2421（有庫存）", "clabo"),
        ("gurapan", "gurapan 1081", "gurapan"),
        ("manasource", "manasource 2268", "manasource"),
        ("cardmax", "cardmax ct1849", "cardmax"),
        ("bushiroad_284", "square-bushiroad 284", "bushiroad"),
    ]
    for key, label, urlkey in sw_sites:
        prods = sw.get(key, {}).get("products", {})
        lines.append(f"## {label}（每天）— {len(prods)} 件")
        lines.append("")
        for pid, name in prods.items():
            lines.append(_item_line(name, URL[urlkey](pid)))
        if prods:
            lines.append("")
        total += len(prods)

    lines.append("## 販售牌組")
    lines.append("")
    deck_sites = [
        ("fukufuku_deck", "福福トレカ WSデッキ販売", "fukufuku"),
        ("torecolo_deck", "torecolo WSデッキ販売", "torecolo"),
        ("clabo_deck", "c-labo WSデッキ販売", "clabo"),
        ("hobbystation_deck", "Hobby Station WSデッキ販売", "hobbystation"),
        ("gurapan_deck", "gurapan WSデッキ販売", "gurapan"),
        ("bushiroad_deck", "square-bushiroad WSデッキ販売", "bushiroad"),
    ]
    for key, label, urlkey in deck_sites:
        prods = sw.get(key, {}).get("products", {})
        lines.append(f"### {label}（每天）— {len(prods)} 件")
        lines.append("")
        for pid, name in prods.items():
            lines.append(_item_line(name, URL[urlkey](pid)))
        if prods:
            lines.append("")
        total += len(prods)

    lines.insert(2, f"**合計 {total} 件**")
    lines.insert(3, "")
    return "\n".join(lines).rstrip() + "\n"


def main():
    report = build_report()
    old = ""
    if os.path.exists(REPORT_PATH):
        with open(REPORT_PATH, encoding="utf-8") as f:
            old = f.read()
    if report == old:
        print("報告無變化，不需更新")
        return True
    with open(REPORT_PATH, "w", encoding="utf-8") as f:
        f.write(report)
    print(f"已更新 {os.path.basename(REPORT_PATH)}")
    return True


if __name__ == "__main__":
    main()
