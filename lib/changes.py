# -*- coding: utf-8 -*-
"""共用：追蹤清單的異動比對與 Telegram 文案片段。

異動 = 新增 / 價格變化 / 下架（含售完）。
在庫數只在「新增」時附註，本身的增減不算異動——同一件商品的在庫數幾乎每天都在
變，列入通知會天天重複洗版。

文案規則：
- 下架只給文案（商品頁通常已失效或售完），不附連結。
- 其餘異動（新增、價格）都附上商品連結。

實際送出由 lib/digest.py 把所有來源併成一則訊息處理。
"""

MAX_ITEMS_PER_SECTION = 25  # 單一區塊最多列出幾件，其餘以「…等共 N 件」收尾


def esc(s):
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def product_name(value):
    if isinstance(value, dict):
        return value.get("name", "")
    return value if isinstance(value, str) else ""


def product_qty(value):
    return value.get("qty") if isinstance(value, dict) else None


def product_prices(value):
    return value.get("prices", []) if isinstance(value, dict) else []


def new_changes():
    return {"added": [], "price": [], "removed": []}


def diff_products(previous, current):
    """比較新舊基準，回傳 {"added": [...], "price": [...], "removed": [...]}。

    每筆為 {"id", "name"}；新增另含 "qty"（未知為 None），價格變化另含 "old"／"new"。
    價格其中一邊未知（空清單）時不算變化，以免列表頁改版或缺標示造成誤報。
    """
    previous = previous if isinstance(previous, dict) else {}
    current = current if isinstance(current, dict) else {}

    changes = new_changes()

    for pid, value in current.items():
        if pid not in previous:
            changes["added"].append(
                {"id": pid, "name": product_name(value), "qty": product_qty(value)}
            )
            continue

        old_value = previous[pid]
        old_prices, new_prices = product_prices(old_value), product_prices(value)
        if old_prices and new_prices and old_prices != new_prices:
            changes["price"].append(
                {
                    "id": pid,
                    "name": product_name(value) or product_name(old_value),
                    "old": old_prices,
                    "new": new_prices,
                }
            )

    for pid, value in previous.items():
        if pid not in current:
            changes["removed"].append({"id": pid, "name": product_name(value)})

    return changes


def has_changes(changes):
    return any(changes.get(key) for key in new_changes())


def merge_changes(all_changes):
    """把多個來源的異動合成一份，供彙總標題統計件數。"""
    merged = new_changes()
    for changes in all_changes:
        for key in merged:
            merged[key].extend(changes.get(key) or [])
    return merged


def _label(entry):
    name = entry.get("name") or ""
    return esc(name) if name else f"商品 {entry['id']}"


def _format_prices(prices):
    return "／".join(f"{price:,}円" for price in prices)


def _added_line(entry):
    qty = entry.get("qty")
    suffix = f"（在庫 {qty}）" if qty is not None else ""
    return f"• <b>{_label(entry)}</b>{suffix}"


def _price_line(entry):
    return (
        f"• <b>{_label(entry)}</b> "
        f"{_format_prices(entry['old'])} → {_format_prices(entry['new'])}"
    )


def _removed_line(entry):
    return f"• {_label(entry)}"


# (key, 標題, 摘要用字, 行文字產生器, 是否附連結)
SECTIONS = (
    ("added", "🆕 新增", "新增", _added_line, True),
    ("price", "💰 價格變化", "價格", _price_line, True),
    ("removed", "🚫 下架", "下架", _removed_line, False),
)


def summary_text(changes):
    """例如「新增 2・下架 1」；沒有異動回傳空字串。"""
    return "・".join(
        f"{word} {len(changes[key])}"
        for key, _title, word, _line, _with_link in SECTIONS
        if changes.get(key)
    )


def render_change_lines(changes, item_url, max_items=MAX_ITEMS_PER_SECTION):
    """回傳單一來源的異動文案行（不含來源標題）；沒有異動回傳空清單。"""
    lines = []
    for key, title, _word, render_line, with_link in SECTIONS:
        entries = changes.get(key) or []
        if not entries:
            continue
        lines.append(f"<b>{title} ({len(entries)})</b>")
        for entry in entries[:max_items]:
            line = render_line(entry)
            if with_link:
                line += f"\n  {item_url(entry['id'])}"
            lines.append(line)
        if len(entries) > max_items:
            lines.append(f"…等共 {len(entries)} 件")
        lines.append("")
    return lines
