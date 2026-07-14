# Firebase 設定與部署

本專案使用 Firebase Authentication、Cloud Firestore 與 Firebase Hosting。正式環境資料預設不公開，只有同時通過前端帳號檢查及 Firestore 管理員規則的使用者可以讀取。

## 1. 啟用 Firebase 服務

在 Firebase Console 的目標專案完成以下設定：

1. 建立 Web App，記下 `apiKey`、`authDomain`、`projectId`、`appId`。
2. 建立 Cloud Firestore database。
3. 在 **Authentication → Sign-in method** 啟用 Google provider。
4. 確認 Hosting 已啟用，且實際網域已加入 Authentication 的 authorized domains。

本 repository 的 `.firebaserc` 預設指向 `card-shop-tracker`。若使用其他專案，請同步更新該檔案或部署時明確傳入 `--project`。

## 2. 建立管理員

1. 先使用預定帳號登入一次網站，讓 Firebase Authentication 建立使用者。
2. 在 **Authentication → Users** 複製該使用者的 UID。
3. 在 Firestore 建立 `admins/{UID}` 文件，內容為：

```json
{
  "enabled": true
}
```

`firestore.rules` 會檢查這個文件。前端的 email allowlist 只是提早阻擋錯誤帳號；即使繞過前端，沒有啟用的 `admins/{UID}` 仍無法讀取資料。

## 3. 設定 GitHub Actions

在 repository 的 **Settings → Secrets and variables → Actions** 新增：

### Secrets

| 名稱 | 內容 |
| --- | --- |
| `FIREBASE_SERVICE_ACCOUNT` | 專用 service account JSON 的完整內容 |

### Variables

| 名稱 | 對應 Web App 設定 |
| --- | --- |
| `FIREBASE_PROJECT_ID` | `projectId` |
| `FIREBASE_API_KEY` | `apiKey` |
| `FIREBASE_AUTH_DOMAIN` | `authDomain` |
| `FIREBASE_APP_ID` | `appId` |
| `FIREBASE_ALLOWED_EMAIL` | 允許使用儀表板的 Google email |

請使用專用、最小權限的 service account，不要使用個人憑證。下載後不要把 JSON 放進 repository；`.gitignore` 會排除常見 service-account 檔名，但不能取代正確的秘密管理與金鑰輪替。

## 4. 第一次同步與部署

1. 在 GitHub Actions 手動執行 `scheduled-tasks`。
2. 確認 `sync-firestore` job 成功，並在 Firestore 看到 `products`、`sources`、`runs`、`meta` 集合。
3. 手動執行 `firebase-dashboard`。
4. 開啟 Hosting URL，以允許的 Google 帳號登入。

之後：

- `scheduled-tasks` 每小時喚醒，成功抓取後更新 state，再由 `sync-firestore` 寫入 Firestore。
- `main` 的前端、Firebase 設定或相關資料程式有變更時，`firebase-dashboard` 會重新建置並部署。

## 本機連接 Firebase

複製範本並填入 Firebase Web App 的公開設定：

```bash
cp web/.env.example web/.env.local
cd web
npm ci
npm run dev
```

Vite 會將 `VITE_*` 變數編入瀏覽器 bundle，請勿在其中放入 service account、Telegram token 或其他伺服器秘密。

若要從本機同步 Firestore，使用 Application Default Credentials：

```bash
export FIREBASE_PROJECT_ID=card-shop-tracker
export GOOGLE_APPLICATION_CREDENTIALS=/absolute/path/to/firebase-service-account.json
python tasks/firebase_sync.py
```

## 本機部署

需要 Firebase CLI 登入或具備適當權限的 Application Default Credentials：

```bash
cd web
npm ci
npm run build
cd ..
npx --yes firebase-tools@15.23.0 deploy \
  --only hosting,firestore:rules \
  --project card-shop-tracker
```

部署前請確認 `web/dist/demo-data.json` 不存在。

## Firestore 資料模型

| 集合／文件 | 用途 | 瀏覽器權限 |
| --- | --- | --- |
| `admins/{uid}` | 可讀取儀表板的 UID allowlist | 使用者只能讀自己的文件 |
| `products/{source__product}` | 正規化商品與目前啟用狀態 | 管理員唯讀 |
| `sources/{source}` | 來源狀態、商品數與同步時間 | 管理員唯讀 |
| `events/{autoId}` | 新品、價格、下架、重新上架事件 | 管理員唯讀 |
| `runs/{autoId}` | 每次同步摘要 | 管理員唯讀 |
| `meta/sync` | 最近一次同步摘要 | 管理員唯讀 |

未列出的路徑以及所有瀏覽器寫入預設拒絕。

## 安全檢查

- 定期輪替 `FIREBASE_SERVICE_ACCOUNT`，刪除不再使用的金鑰。
- 移除使用者時，同時停用 Authentication 使用者並刪除或停用 `admins/{UID}`。
- 不要把 service account JSON 貼到 issue、PR、Actions log 或前端環境變數。
- Firebase API key 可出現在前端，但應在 Google Cloud Console 對 key 設定適用的 API 與網站限制。
- 部署後檢查 Hosting response headers，確認 CSP、frame protection 與 MIME sniffing protection 仍存在。
