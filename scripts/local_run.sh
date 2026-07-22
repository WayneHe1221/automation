#!/usr/bin/env bash
# 本機排程執行器：補足 GitHub Actions best-effort 排程可能延遲／跳過的整點。
#
# 每次執行：拉取最新 main → 跑 run_all.py（抓取＋通知＋報告＋Firestore 同步）
# → 把有變動的 state／報告 commit 回 main。任務本身每天（UTC）只實際抓取一次，
# 因此若當天 GitHub Actions 已跑過，本機這一輪會安全略過，不會重複通知或洗版。
#
# 到期自動退場：超過 END_DATE 後，會自我移除 crontab 內的排程並停止。
set -uo pipefail

# 只維持到今年 9/1（含當天）；之後自動卸載。
END_DATE="2026-09-01"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SOURCE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
RUNTIME_ROOT="${CARD_RADAR_CRON_HOME:-$SOURCE_ROOT/.local_cron}"
REPO_ROOT="$RUNTIME_ROOT/repo"

# cron 的 PATH 很精簡，補上常見的 git／python／node 位置。
export PATH="/opt/homebrew/bin:/usr/local/bin:/usr/bin:/bin:/usr/sbin:/sbin:$PATH"

log() { printf '%s %s\n' "$(date '+%Y-%m-%d %H:%M:%S')" "$*"; }

# ---- 到期自我卸載 -------------------------------------------------------
TODAY="$(date '+%Y-%m-%d')"
if [[ "$TODAY" > "$END_DATE" ]]; then
  log "已超過維護期限 ${END_DATE}，移除本機 crontab 排程並結束。"
  ( crontab -l 2>/dev/null | grep -Fv "$SCRIPT_DIR/local_run.sh" ) | crontab - 2>/dev/null || true
  exit 0
fi

# ---- 防重疊：同一時間只允許一個執行個體 ---------------------------------
mkdir -p "$RUNTIME_ROOT"
LOCK_DIR="$RUNTIME_ROOT/lock"
if ! mkdir "$LOCK_DIR" 2>/dev/null; then
  log "偵測到前一輪仍在執行（$LOCK_DIR 已存在），本輪跳過。"
  exit 0
fi
trap 'rmdir "$LOCK_DIR" 2>/dev/null || true' EXIT

# ---- 載入本機機密（TG_*, FIREBASE_PROJECT_ID, GOOGLE_APPLICATION_CREDENTIALS）
ENV_FILE="$SCRIPT_DIR/local_cron.env"
if [[ -f "$ENV_FILE" ]]; then
  set -a
  # shellcheck disable=SC1090
  source "$ENV_FILE"
  set +a
else
  log "警告：找不到 ${ENV_FILE}，Telegram／Firestore 相關步驟可能會略過。"
fi

# ---- 選用 Python 直譯器 -------------------------------------------------
if [[ -x "$SOURCE_ROOT/.venv/bin/python" ]]; then
  PYTHON="$SOURCE_ROOT/.venv/bin/python"
else
  PYTHON="$(command -v python3 || true)"
fi
if [[ -z "${PYTHON:-}" ]]; then
  log "找不到 python，結束。"
  exit 1
fi

# python.org 的 macOS Python 預設找不到根憑證，會讓 urllib 抓取全數失敗。
# 若尚未指定 SSL_CERT_FILE，就指向 certifi 的憑證庫（由 requirements 帶入）。
if [[ -z "${SSL_CERT_FILE:-}" ]]; then
  certifi_path="$("$PYTHON" -c 'import certifi; print(certifi.where())' 2>/dev/null || true)"
  [[ -n "$certifi_path" ]] && export SSL_CERT_FILE="$certifi_path"
fi

# ---- 以獨立 clone 取得最新 main，不碰使用者目前工作的 branch -----------
log "=== 本機排程開始（${PYTHON}）==="
if [[ ! -d "$REPO_ROOT/.git" ]]; then
  origin_url="$(git -C "$SOURCE_ROOT" remote get-url origin 2>/dev/null || true)"
  if [[ -z "$origin_url" ]]; then
    log "找不到 origin URL，無法建立獨立 clone。"
    exit 1
  fi
  log "建立獨立排程 clone：$REPO_ROOT"
  if ! git clone --branch main --single-branch "$origin_url" "$REPO_ROOT"; then
    log "git clone 失敗，本輪跳過。"
    exit 1
  fi
fi

cd "$REPO_ROOT" || { log "無法進入 $REPO_ROOT"; exit 1; }
git reset --hard HEAD >/dev/null
if ! git pull --rebase origin main; then
  log "git pull 失敗，本輪跳過（不動 state）。"
  exit 1
fi

# 上一輪若 commit 成功但 push 暫時失敗，先補推再執行本輪。
if [[ "$(git rev-list --count origin/main..HEAD)" -gt 0 ]]; then
  log "偵測到上一輪尚未推送的 commit，先補推。"
  if ! git push origin main; then
    log "補推失敗，本輪跳過以避免累積分歧。"
    exit 1
  fi
fi

# ---- 執行所有任務 -------------------------------------------------------
"$PYTHON" run_all.py
run_status=$?
log "run_all.py 結束碼：$run_status"

# ---- commit／push 有變動的 state 與報告（與 GitHub Actions 一致） -------
git add state/ inventory_report.md
if git diff --staged --quiet; then
  log "state／報告無變化，不需 commit。"
else
  git -c user.name="local-cron" -c user.email="local-cron@localhost" \
    commit -m "chore: update task state & inventory report (local cron) [skip ci]"
  # main 可能已被 GitHub Actions 推進，push 失敗就 rebase 後再試一次。
  if ! git push origin main; then
    log "push 被拒，先 rebase 再重試。"
    git pull --rebase --autostash origin main && git push origin main \
      || log "push 仍失敗，保留本機 commit，等下一輪再推。"
  fi
  log "已提交 state／報告更新。"
fi

log "=== 本機排程結束 ==="
exit "$run_status"
