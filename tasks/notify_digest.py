# -*- coding: utf-8 -*-
"""任務：把本輪各來源的異動併成一則 Telegram 通知送出。

抓取任務（ORDER 預設 100）只把異動登記到 lib/digest.py，由本任務一次送出，
避免每個來源各發一則重複洗版。送出成功後才會執行各來源的 commit
（更新 state 基準與當日執行紀錄）。

ORDER 設為 500：在所有抓取任務之後，但在 firebase_sync（800）與
inventory_report（900）之前，確保同步與報告看到的是已 commit 的最新基準。
"""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from lib.digest import flush  # noqa: E402

ORDER = 500


def main():
    return flush()


if __name__ == "__main__":
    main()
