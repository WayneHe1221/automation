# -*- coding: utf-8 -*-
"""共用：Telegram 通知。

token / chat id 一律從環境變數讀取（GitHub Actions 由 Secrets 注入），
絕不寫進程式或 commit 進 repo。
"""

import json
import os
import urllib.error
import urllib.parse
import urllib.request

TG_LIMIT = 3800  # Telegram 單則訊息保守字數上限


def send_telegram(text, token=None, chat_id=None):
    """送一則 HTML 格式訊息；成功回 True。"""
    token = token or os.environ.get("TG_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: 缺少 TG_BOT_TOKEN 或 TG_CHAT_ID，無法送出 Telegram 訊息")
        return False

    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text[:TG_LIMIT],
            "parse_mode": "HTML",
            "disable_web_page_preview": "true",
        }
    ).encode("utf-8")
    req = urllib.request.Request(url, data=payload)
    try:
        with urllib.request.urlopen(req, timeout=30) as resp:
            body = json.loads(resp.read().decode("utf-8", errors="replace"))
            if body.get("ok"):
                return True
            print(f"ERROR: Telegram API 回傳失敗：{body}")
            return False
    except urllib.error.HTTPError as e:
        detail = e.read().decode("utf-8", errors="replace")
        print(f"ERROR: Telegram HTTPError {e.code}：{detail}")
        return False
    except Exception as e:  # noqa: BLE001
        print(f"ERROR: 送 Telegram 例外：{e}")
        return False
