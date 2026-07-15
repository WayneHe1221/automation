# 排程與維運手冊

## GitHub Actions

| Workflow | 觸發條件 | 工作內容 |
| --- | --- | --- |
| `parser-tests` | PR、推送至 `main`、手動 | 安裝 Python 依賴並執行離線 parser 測試 |
| `scheduled-tasks` | 每小時第 25 分、手動 | 測試、抓取、通知、更新 state／報告、同步 Firestore |
| `firebase-dashboard` | `main` 的網站／Firebase 相關檔案變更、手動 | 建置 React、部署 Hosting 與 Firestore Rules |

GitHub cron 使用 UTC。爬取任務以 UTC 日期判斷「今天是否成功執行過」，因此台北時間每天 08:00 之後進入新的執行日。排程是 best-effort，可能延遲或偶爾跳過；下一個整點仍會再次喚醒。

`scheduled-tasks` 使用 concurrency group，前一輪尚未結束時不會被新一輪取消。

## 執行順序與失敗行為

`run_all.py` 自動載入 `tasks/` 內的模組，依 `ORDER`（預設 100）及檔名排序：

1. 商店抓取任務更新 `state/*.json`。
2. `firebase_sync`（`ORDER = 800`）在有設定 `FIREBASE_PROJECT_ID` 時同步 Firestore。
3. `inventory_report`（`ORDER = 900`）以最新 state 重建報告。

CardMax `ct1849` 使用手機版頁面取得商品名稱、庫存與含稅價格；價格會保存在 state，並由 `firebase_sync` 寫入 Firestore 供儀表板顯示及追蹤後續變化。

在 GitHub Actions 中，抓取 job 本身不提供 Firebase 憑證，所以其中的 `firebase_sync` 會安全略過；state commit 完成後，獨立的 `sync-firestore` job 才以限制範圍的憑證同步 `main` 最新資料。

安全策略：

- 抓取失敗、頁面被導向非預期網域、缺少關鍵 HTML 標記或解析為空時，不更新該來源基準。
- 原始商品數異常驟降時，不接受新結果，避免網站改版被誤判成大量下架。
- Telegram 通知失敗時保留舊基準，讓下一輪可以重試。
- 單一任務失敗時繼續執行其他任務，最後讓 workflow 失敗以保留可見性。
- 無論抓取是否完全成功，已成功更新的 state 與報告都會先 commit。

## 手動操作

### 重跑完整排程

GitHub → **Actions → scheduled-tasks → Run workflow**。

適用情況：第一次建立基準、來源暫時故障後重試、Firebase 同步需要補跑。

### 只重新部署網站

GitHub → **Actions → firebase-dashboard → Run workflow**。

適用情況：Firebase 設定補齊、Hosting 部署失敗後重試、只更新 Rules 或安全標頭。

### 本機驗證

```bash
source .venv/bin/activate
python -m unittest discover -s tests -v
python tasks/inventory_report.py

cd web
npm ci
npm run build
npm audit --omit=dev --audit-level=high
test ! -e dist/demo-data.json
```

`inventory_report.md` 是產生檔；只有在 state 改變或確認產生邏輯更新時才應提交其差異。

## 新增或修改監控來源

1. 在 `tasks/` 新增具有 `main()` 的模組，或在 `tasks/shop_watch.py` 的 `SITES` 加入來源。
2. 使用 `lib.fetch.fetch_html`，設定預期 path 與頁面關鍵標記，避免登入頁或阻擋頁被當成商品頁。
3. 將狀態寫入 `state/`；成功或安全略過回傳 `True`，抓取、解析或通知失敗回傳 `False`。
4. 在 `tests/fixtures/` 保存最小化 HTML fixture，於 `tests/` 新增離線 parser 測試。
5. 若來源需要出現在網站，更新 `lib/catalog.py` 的 `SOURCE_DEFINITIONS`。
6. 若來源需要出現在靜態報告，更新 `tasks/inventory_report.py`。
7. 執行 Python 測試、重建報告及前端 build，再送出 PR。

不要讓測試依賴即時商店網站；即時連線不穩定，也可能對商店造成不必要負載。

## 常見問題

### Workflow 顯示任務失敗，但 state 仍有 commit

這是預期行為。成功來源先保存，失敗來源保留舊基準；查看 `Run all tasks` log 找出失敗站台。

### 每個整點都顯示「今天已執行過」

這是每日限流機制。Workflow 每小時喚醒是為了在 GitHub 排程延遲、商店暫時失敗或通知失敗時自動重試。

### 儀表板顯示沒有權限

依序確認：Authentication UID 是否存在 `admins/{UID}`、文件的 `enabled` 是否為 `true`、Rules 是否已部署。新增觀看者不需要重新部署網站。

### Firestore 沒有最新資料

查看 `scheduled-tasks` 的 `sync-firestore` job，確認 `FIREBASE_PROJECT_ID` variable 與 `FIREBASE_SERVICE_ACCOUNT` secret 已設定，且 service account 金鑰未失效。

### 本機網站進入預覽模式

未提供完整 `VITE_FIREBASE_*` 設定時會使用 `state/*.json` 產生的本機資料。需要連接 Firebase 時，建立 `web/.env.local` 並重新啟動 Vite。
