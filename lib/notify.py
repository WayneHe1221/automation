# -*- coding: utf-8 -*-
"""共用：Telegram 通知。

token / chat id 一律從環境變數讀取（GitHub Actions 由 Secrets 注入），
絕不寫進程式或 commit 進 repo。
"""

import html
import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request

TG_LIMIT = 3800  # Telegram 單則訊息保守字數上限


def split_telegram_html(text, limit=TG_LIMIT):
    """依完整行切分 HTML 訊息，避免截斷標籤。"""
    if len(text) <= limit:
        return [text]

    chunks = []
    current = []
    current_length = 0
    for line in text.splitlines(keepends=True):
        if len(line) > limit:
            if current:
                chunks.append("".join(current).rstrip("\n"))
                current = []
                current_length = 0
            plain = html.escape(
                html.unescape(re.sub(r"<[^>]+>", "", line.rstrip("\n")))
            )
            chunks.extend(
                plain[offset : offset + limit]
                for offset in range(0, len(plain), limit)
            )
            continue

        if current and current_length + len(line) > limit:
            chunks.append("".join(current).rstrip("\n"))
            current = []
            current_length = 0
        current.append(line)
        current_length += len(line)

    if current:
        chunks.append("".join(current).rstrip("\n"))
    return [chunk for chunk in chunks if chunk]


def _send_telegram_chunk(text, token, chat_id):
    url = f"https://api.telegram.org/bot{token}/sendMessage"
    payload = urllib.parse.urlencode(
        {
            "chat_id": chat_id,
            "text": text,
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


def send_telegram(text, token=None, chat_id=None):
    """送出一或多則 HTML 格式訊息；全部成功才回 True。"""
    token = token or os.environ.get("TG_BOT_TOKEN", "")
    chat_id = chat_id or os.environ.get("TG_CHAT_ID", "")
    if not token or not chat_id:
        print("ERROR: 缺少 TG_BOT_TOKEN 或 TG_CHAT_ID，無法送出 Telegram 訊息")
        return False

    chunks = split_telegram_html(text)
    for index, chunk in enumerate(chunks, start=1):
        if not _send_telegram_chunk(chunk, token, chat_id):
            print(f"ERROR: Telegram 訊息第 {index}/{len(chunks)} 段送出失敗")
            return False
    return True
