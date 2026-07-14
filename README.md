# automation

個人常態排程任務集合，跑在 **GitHub Actions** 上（每小時），不需要自己的電腦或伺服器。

## 結構

```
automation/
├─ lib/                  # 共用工具
│   ├─ notify.py         #   Telegram 發訊（token 從環境變數/Secrets 讀）
│   ├─ fetch.py          #   抓網頁
│   └─ catalog.py        #   將任務 state 正規化成網站共用資料
├─ tasks/                # 一支檔案 = 一個任務，需提供 main()
│   ├─ bushiroad_668.py  #   square-bushiroad 668（每天：新增商品）
│   ├─ shop_watch.py     #   多站新品追蹤（每天：bushiroad 284 / torecolo / manasource / cardmax / gurapan / c-labo）
│   └─ firebase_sync.py  #   同步商品、來源與異動歷史到 Firestore
├─ state/                # 各任務狀態（Actions 跑完自動 commit 回來）
├─ tests/                # 各站精簡 HTML fixtures 與離線 parser 測試
├─ web/                  # React + Firebase 商品監控儀表板
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

## Firebase 儀表板

網站預設可在未設定 Firebase 時，以 `state/*.json` 的真實資料進入預覽模式：

```bash
cd web
npm install
npm run dev
```

正式啟用時，在 Firebase 建立 Web App、Cloud Firestore、Google 登入及 Hosting，並設定：

| GitHub 設定 | 類型 | 內容 |
| --- | --- | --- |
| `FIREBASE_SERVICE_ACCOUNT` | Secret | Firebase service account JSON 完整內容 |
| `FIREBASE_PROJECT_ID` | Variable | Firebase project id |
| `FIREBASE_API_KEY` | Variable | Web App API key |
| `FIREBASE_AUTH_DOMAIN` | Variable | Web App auth domain |
| `FIREBASE_APP_ID` | Variable | Web App app id |
| `FIREBASE_ALLOWED_EMAIL` | Variable | 允許登入的 Google 帳號 |

第一次 Google 登入後，在 Firebase Authentication 找到該使用者的 UID，於 Firestore 建立
`admins/{UID}` 文件（內容可為 `{ enabled: true }`）。安全規則只允許這些 UID 讀取資料，
瀏覽器端一律不能寫入；排程透過 Admin SDK 寫入。

完成設定後，手動執行 `scheduled-tasks` 建立 Firestore 基準，再執行
`firebase-dashboard` 發布網站。後續 `main` 更新會自動部署。

## 新增一個任務

1. 在 `tasks/` 建一支 `your_task.py`，提供 `def main(): ...`。
2. 需要發通知就 `from lib.notify import send_telegram`；抓網頁用 `from lib.fetch import fetch_html`。
3. 狀態存到 `state/your_task.json`（會自動被 commit 保存）。
4. 成功或安全略過時回傳 `True`，抓取／解析／通知失敗時回傳 `False`。
5. push 上去即可，`run_all.py` 會自動探索執行，無需改 workflow。

任一任務失敗時，其他任務仍會繼續執行，成功更新的 state 也會先 commit；最後
GitHub Actions 會標示失敗，避免抓取異常被誤認為正常。

## 本機測試

```bash
TG_BOT_TOKEN=xxx TG_CHAT_ID=yyy python run_all.py
python -m unittest discover -s tests -v
```
