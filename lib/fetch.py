# -*- coding: utf-8 -*-
"""共用：可靠地抓取並驗證網頁 HTML。"""

import random
import time
import urllib.error
import urllib.parse
import urllib.request

USER_AGENT = (
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)
TRANSIENT_HTTP_CODES = {408, 425, 429, 500, 502, 503, 504}


class FetchError(RuntimeError):
    """網頁抓取或內容驗證失敗。"""


def _normalized_host(url):
    host = (urllib.parse.urlparse(url).hostname or "").lower()
    return host[4:] if host.startswith("www.") else host


def _retry_delay(error, attempt, backoff):
    if isinstance(error, urllib.error.HTTPError):
        retry_after = error.headers.get("Retry-After")
        if retry_after and retry_after.isdigit():
            return min(float(retry_after), 10.0)
    return backoff * (2 ** (attempt - 1)) + random.uniform(0, 0.25)


def fetch_html(
    url,
    timeout=30,
    encoding=None,
    attempts=3,
    backoff=1.0,
    required_markers=(),
    expected_path_prefix=None,
    user_agent=None,
):
    """抓取 HTML，並驗證最終網址與頁面關鍵標記。"""
    request = urllib.request.Request(
        url,
        headers={
            "User-Agent": user_agent or USER_AGENT,
            "Accept": "text/html,application/xhtml+xml",
            "Accept-Language": "ja,en;q=0.8,zh-TW;q=0.6",
        },
    )
    expected_host = _normalized_host(url)
    markers = (
        (required_markers,)
        if isinstance(required_markers, str)
        else tuple(required_markers)
    )

    for attempt in range(1, attempts + 1):
        try:
            with urllib.request.urlopen(request, timeout=timeout) as response:
                final_url = response.geturl()
                final_parts = urllib.parse.urlparse(final_url)
                if _normalized_host(final_url) != expected_host:
                    raise FetchError(f"網址被導向非預期網域：{final_url}")
                if expected_path_prefix and not final_parts.path.startswith(
                    expected_path_prefix
                ):
                    raise FetchError(f"網址被導向非預期頁面：{final_url}")

                charset = encoding or response.headers.get_content_charset() or "utf-8"
                html = response.read().decode(charset, errors="replace")
                missing = [marker for marker in markers if marker not in html]
                if missing:
                    raise FetchError(f"頁面缺少必要標記：{', '.join(missing)}")
                return html
        except urllib.error.HTTPError as error:
            if error.code not in TRANSIENT_HTTP_CODES or attempt == attempts:
                raise FetchError(f"HTTP {error.code}：{url}") from error
            last_error = error
        except (urllib.error.URLError, OSError) as error:
            if attempt == attempts:
                raise FetchError(f"連線失敗：{url}（{error}）") from error
            last_error = error
        except FetchError:
            raise

        delay = _retry_delay(last_error, attempt, backoff)
        print(f"WARN: 抓取失敗，第 {attempt}/{attempts} 次，{delay:.1f} 秒後重試")
        time.sleep(delay)

    raise FetchError(f"抓取失敗：{url}")
