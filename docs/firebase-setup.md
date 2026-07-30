# Firebase 設定與部署

本專案使用 Firebase Authentication、Cloud Firestore 與 Firebase Hosting。正式環境資料預設不公開，只有完成 Google 登入且 UID 已加入 Firestore 觀看者清單的使用者可以讀取。

## 1. 啟用 Firebase 服務

在 Firebase Console 的目標專案完成以下設定：

1. 建立 Web App，記下 `apiKey`、`projectId`、`appId`；`authDomain` 建議使用 Hosting 網域（例如 `your-project.web.app`）。
2. 建立 Cloud Firestore database。
3. 在 **Authentication → Sign-in method** 啟用 Google provider。
4. 確認 Hosting 已啟用，且實際網域已加入 Authentication 的 authorized domains。
5. 在 Google Cloud Console 的 OAuth 網頁用戶端加入 `https://your-project.web.app/__/auth/handler` 作為已授權的重新導向 URI。這可讓行動版 redirect 登入維持在同一個網域，避免 Safari 的跨站儲存限制。

本 repository 的 `.firebaserc` 預設指向 `card-shop-tracker`。若使用其他專案，請同步更新該檔案或部署時明確傳入 `--project`。

## 1-1. Hosting 網域

主要網址是 **https://cardradar.web.app**（Hosting site `cardradar`）。

Firebase 的專案 ID 建立後無法改名，所以專案 ID 仍是 `card-shop-tracker`；為了讓網址與專案名稱
Card Radar 一致，改在同一個專案內新增 Hosting site：

| Site | 網址 | 角色 |
| --- | --- | --- |
| `cardradar` | https://cardradar.web.app | 主要網址 |
| `card-shop-tracker` | https://card-shop-tracker.web.app | 舊網址；同時是 `FIREBASE_AUTH_DOMAIN` |

`.firebaserc` 的 hosting target `app` 同時指向兩個 site，`firebase.json` 以 `"target": "app"` 部署，
因此一次部署會把相同內容送到兩個網址。舊網址刻意保留而**不做轉址**：Google 登入（尤其行動版
redirect）會使用 `authDomain` 的 `card-shop-tracker.web.app/__/auth/handler`，轉址會讓登入失效。

新增網址時記得在 **Authentication → Settings → Authorized domains** 加入該網域，否則從新網址登入
會得到 `auth/unauthorized-domain`。若日後要把 `authDomain` 也換成新網域，需同時在 Google Cloud
Console 的 OAuth 網頁用戶端加入 `https://cardradar.web.app/__/auth/handler`，並更新
`FIREBASE_AUTH_DOMAIN` variable。

新增站台的指令：

```bash
npx --yes firebase-tools@15.23.0 hosting:sites:create <site-id> --project card-shop-tracker
```

site ID 是全域唯一的，`card-radar` 已被其他專案占用，因此改用 `cardradar`。

## 2. 新增或移除觀看者

1. 請觀看者先使用預定的 Google 帳號登入一次網站；畫面會顯示尚未授權，同時 Firebase Authentication 會建立使用者。
2. 在 **Authentication → Users** 複製該使用者的 UID。
3. 在 Firestore 建立 `admins/{UID}` 文件，內容為：

```json
{
  "enabled": true
}
```

4. 請觀看者重新整理網站，即可讀取儀表板，不需要重新建置或部署。

每位觀看者各自建立一份 `admins/{UID}` 文件。要移除權限時，將 `enabled` 改為 `false` 或刪除該文件；若也不希望對方再次登入，可同時在 Authentication 停用或刪除該使用者。

`firestore.rules` 以 UID 文件作為唯一的資料授權依據。沒有啟用的 `admins/{UID}`，即使已完成 Google 登入也無法讀取監控資料。

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
| `FIREBASE_AUTH_DOMAIN` | Hosting 網域，例如 `your-project.web.app` |
| `FIREBASE_APP_ID` | `appId` |

請使用專用、最小權限的 service account，不要使用個人憑證。下載後不要把 JSON 放進 repository；`.gitignore` 會排除常見 service-account 檔名，但不能取代正確的秘密管理與金鑰輪替。

## 4. 第一次同步與部署

1. 在 GitHub Actions 手動執行 `scheduled-tasks`。
2. 確認 `sync-firestore` job 成功，並在 Firestore 看到 `products`、`sources`、`runs`、`meta` 集合。
3. 手動執行 `firebase-dashboard`。
4. 開啟主要網址 https://cardradar.web.app，以允許的 Google 帳號登入。

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
| `sources/{source}` | 來源狀態、商品數、追蹤網頁原始連結（`pageUrl`）與同步時間 | 管理員唯讀；只有 `displayName` 一個欄位可由管理員改寫 |
| `events/{autoId}` | 新品、價格、下架、重新上架事件 | 管理員唯讀 |
| `runs/{autoId}` | 每次同步摘要 | 管理員唯讀 |
| `meta/sync` | 最近一次同步摘要 | 管理員唯讀 |

未列出的路徑以及其餘瀏覽器寫入預設拒絕。`sources/{source}.displayName` 是唯一例外：
儀表板的「追蹤網頁」清單可讓管理員自訂展示名稱，Rules 只允許這個欄位、限制為 1–60 字元，
刪除欄位即還原監控任務產生的 `label`。

## 安全檢查

- 定期輪替 `FIREBASE_SERVICE_ACCOUNT`，刪除不再使用的金鑰。
- 移除使用者時，同時停用 Authentication 使用者並刪除或停用 `admins/{UID}`。
- 不要把 service account JSON 貼到 issue、PR、Actions log 或前端環境變數。
- Firebase API key 可出現在前端，但應在 Google Cloud Console 對 key 設定適用的 API 與網站限制。
- Hosting 的 `Referrer-Policy` 必須允許跨網域請求傳送來源網域（目前使用 `strict-origin-when-cross-origin`），否則 HTTP referrer 限制會拒絕 Firebase Authentication 請求。
- Hosting 的 CSP 必須允許 `https://apis.google.com` 腳本及同網域 iframe；Firebase Authentication 會使用這兩者完成 popup 與 redirect 登入初始化。
- SPA 頁面不得快取，避免 Firebase Auth 或安全標頭更新後，瀏覽器仍沿用舊版登入設定；帶雜湊的 JS/CSS 檔案仍可長期快取。
- 部署後檢查 Hosting response headers，確認 CSP、frame protection 與 MIME sniffing protection 仍存在。
