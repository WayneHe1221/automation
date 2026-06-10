# automation

個人常態排程任務集合，跑在 **GitHub Actions** 上（每小時），不需要自己的電腦或伺服器。

## 結構

```
automation/
├─ lib/                  # 共用工具
│   ├─ notify.py         #   Telegram 發訊（token 從環境變數/Secrets 讀）
│   └─ fetch.py          #   抓網頁
├─ tasks/                # 一支檔案 = 一個任務，需提供 main()
│   ├─ cardshop_list.py  #   cardshop-serra 列表監控（每小時：新增/價格異動/下架）
│   ├─ bushiroad_668.py  #   square-bushiroad 668（每天：新增商品）
│   └─ shop_watch.py     #   多站新品追蹤（每天：bushiroad 284 / torecolo / manasource / cardmax / gurapan / c-labo）
├─ state/                # 各任務狀態（Actions 跑完自動 commit 回來）
├─ run_all.py            # 入口：自動探索並執行 tasks/ 所有任務
└─ .github/workflows/
    └─ schedule.yml      # cron 每小時觸發
```

## 必要設定（一次）

在 GitHub repo → **Settings → Secrets and variables → Actions → New repository secret** 新增：

| Secret | 內容 |
| ------ | ---- |
| `TG_BOT_TOKEN` | Telegram Bot token（@BotFather 取得） |
| `TG_CHAT_ID`   | 你的 Telegram 數字 chat id（@userinfobot 取得） |

> ⚠️ 本 repo 為公開專案。token **只**放在上述加密的 Secrets，**絕不**寫進程式或 commit。
> `.gitignore` 已排除 `config.env` / `*.env`。

設定後到 **Actions** 分頁手動觸發 `scheduled-tasks` 跑第一次（建立基準），或等下一個整點。

## 新增一個任務

1. 在 `tasks/` 建一支 `your_task.py`，提供 `def main(): ...`。
2. 需要發通知就 `from lib.notify import send_telegram`；抓網頁用 `from lib.fetch import fetch_html`。
3. 狀態存到 `state/your_task.json`（會自動被 commit 保存）。
4. push 上去即可，`run_all.py` 會自動探索執行，無需改 workflow。

## 本機測試

```bash
TG_BOT_TOKEN=xxx TG_CHAT_ID=yyy python run_all.py
```
