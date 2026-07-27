# -*- coding: utf-8 -*-
"""共用：把同一輪所有來源的異動彙整成「一則」Telegram 通知。

各任務只負責 add()：登記自己的異動，以及「通知送出成功後才執行」的 commit
（更新基準／執行日）。tasks/notify_digest.py（ORDER = 500，在抓取之後、
Firestore 同步與報告之前）呼叫 flush() 一次送出。

送出成功才逐一 commit；失敗則所有來源保留舊基準、當天不記為已執行，
下一輪重新比對並重試——與原本逐站送出時的重試語意相同。
"""

from lib.changes import (
    esc,
    has_changes,
    merge_changes,
    render_change_lines,
    summary_text,
)
from lib.notify import send_telegram

_pending = []


def add(label, changes, item_url, commit, max_items=None):
    """登記一個來源的異動；沒有異動就不登記（回傳 False）。"""
    if not has_changes(changes):
        return False
    _pending.append(
        {
            "label": label,
            "changes": changes,
            "item_url": item_url,
            "commit": commit,
            "max_items": max_items,
        }
    )
    return True


def pending_labels():
    return [entry["label"] for entry in _pending]


def reset():
    """清空待送清單（供測試與重跑使用）。"""
    _pending.clear()


def build_message(entries):
    """組出彙總文案：一個標題 + 每個來源一段。"""
    merged = merge_changes(entry["changes"] for entry in entries)
    lines = [
        "🔔 <b>商品異動</b>",
        f"{len(entries)} 個來源・{summary_text(merged)}",
        "",
    ]
    for entry in entries:
        lines.append(f"▍<b>{esc(entry['label'])}</b>")
        render_kwargs = (
            {"max_items": entry["max_items"]} if entry["max_items"] else {}
        )
        lines.extend(
            render_change_lines(entry["changes"], entry["item_url"], **render_kwargs)
        )
    return "\n".join(lines).rstrip()


def flush():
    """送出本輪彙總通知；成功（或本來就沒有異動）回傳 True。"""
    if not _pending:
        print("本輪無異動，不發通知")
        return True

    if not send_telegram(build_message(_pending)):
        print(
            f"ERROR: 彙總通知送出失敗，{len(_pending)} 個來源保留舊基準，稍後重試："
            f"{'、'.join(pending_labels())}"
        )
        return False

    for entry in _pending:
        entry["commit"]()
    print(f"已送出彙總通知（{len(_pending)} 個來源）：{'、'.join(pending_labels())}")
    _pending.clear()
    return True
