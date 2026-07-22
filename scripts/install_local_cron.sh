#!/usr/bin/env bash
# 安裝／移除補足 GitHub Actions 的本機 crontab 排程。
#
#   scripts/install_local_cron.sh            # 安裝（預設每小時第 55 分，與 GitHub 的第 25 分錯開）
#   scripts/install_local_cron.sh --minute 40  # 自訂分鐘
#   scripts/install_local_cron.sh --uninstall  # 移除
#   scripts/install_local_cron.sh --show       # 檢視目前 crontab
#
# 排程本身會在超過 local_run.sh 內的 END_DATE 後自我卸載，這裡不需另設結束日。
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
RUNNER="$SCRIPT_DIR/local_run.sh"
LOG_FILE="$SCRIPT_DIR/local_cron.log"
MINUTE=55
ACTION="install"

while [[ $# -gt 0 ]]; do
  case "$1" in
    --minute) MINUTE="$2"; shift 2 ;;
    --uninstall) ACTION="uninstall"; shift ;;
    --show) ACTION="show"; shift ;;
    *) echo "未知參數：$1"; exit 2 ;;
  esac
done

current_crontab() { crontab -l 2>/dev/null || true; }
without_runner() { current_crontab | grep -Fv "$RUNNER" || true; }

case "$ACTION" in
  show)
    current_crontab
    ;;
  uninstall)
    without_runner | crontab -
    echo "已移除本機排程。"
    ;;
  install)
    chmod +x "$RUNNER"
    REPO_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
    # 優先使用 Homebrew 的新版 Python，避免 macOS 內建 Python 3.9／LibreSSL。
    PYTHON=""
    for candidate in "${CRON_PYTHON:-}" /opt/homebrew/bin/python3.13 /opt/homebrew/bin/python3.12 /usr/local/bin/python3.13 /usr/local/bin/python3.12 "$(command -v python3 || true)"; do
      if [[ -n "$candidate" && -x "$candidate" ]]; then
        PYTHON="$candidate"
        break
      fi
    done
    if [[ -z "$PYTHON" ]]; then
      echo "找不到可用的 Python。"
      exit 1
    fi

    venv_is_current=0
    if [[ -x "$REPO_ROOT/.venv/bin/python" ]]; then
      venv_is_current="$("$REPO_ROOT/.venv/bin/python" -c 'import sys; print(int(sys.version_info >= (3, 12)))')"
    fi
    if [[ "$venv_is_current" != "1" ]]; then
      echo "以 $PYTHON 重建虛擬環境 .venv …"
      "$PYTHON" -m venv --clear "$REPO_ROOT/.venv"
    fi
    echo "安裝／更新 Python 依賴 …"
    "$REPO_ROOT/.venv/bin/pip" install -q -r "$REPO_ROOT/requirements.txt"
    if [[ ! -f "$SCRIPT_DIR/local_cron.env" ]]; then
      echo "提醒：尚未建立 $SCRIPT_DIR/local_cron.env，請先由 local_cron.env.example 複製並填值（含 Firestore 憑證）。"
    fi
    # 每小時第 $MINUTE 分執行一次；stdout/stderr 追加到 log。
    line="$MINUTE * * * * /usr/bin/env bash \"$RUNNER\" >> \"$LOG_FILE\" 2>&1"
    { without_runner; echo "$line"; } | crontab -
    echo "已安裝本機排程：每小時第 $MINUTE 分。"
    echo "  指令：$line"
    echo "  記錄：$LOG_FILE"
    echo "注意（macOS）：cron 需要『完整磁碟取用權限』；請到系統設定 → 隱私權與安全性 → 完整磁碟取用權限，加入 /usr/sbin/cron。"
    ;;
esac
