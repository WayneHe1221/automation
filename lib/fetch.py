# -*- coding: utf-8 -*-
"""共用：抓取網頁 HTML。"""

import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)


def fetch_html(url, timeout=30, encoding=None):
    """抓取 HTML。encoding 可強制指定（如舊式日文站的 euc_jp）。"""
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        charset = encoding or resp.headers.get_content_charset() or "utf-8"
        return resp.read().decode(charset, errors="replace")
