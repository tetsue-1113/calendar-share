#!/bin/bash
set -euo pipefail

# -----------------------
#  設定（ユーザーに依存しない）
# -----------------------
PROJECT_DIR="$HOME/Desktop/Python/ボイスケ更新"
VENV_DIR="$PROJECT_DIR/.venv"
PYTHON_PATH="$VENV_DIR/bin/python"
PIP_PATH="$VENV_DIR/bin/pip"
BOOTSTRAP_MARKER="$VENV_DIR/.local_build_complete"
SCRIPT_NAME="update_schedule.py"
ICS_FILE="existing_schedule.ics"

cd "$PROJECT_DIR" || {
    echo "❌ プロジェクトディレクトリが存在しません: $PROJECT_DIR"
    exit 1
}

rebuild_venv() {
    echo "⚠️ 仮想環境をこのMac上で再構築しています..."
    rm -rf "$VENV_DIR"
    python3 -m venv "$VENV_DIR"
    "$PIP_PATH" install --upgrade pip
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        "$PIP_PATH" install -r "$PROJECT_DIR/requirements.txt"
    fi
    touch "$BOOTSTRAP_MARKER"
}

# -----------------------
#  仮想環境を確認・作成
# -----------------------
if [ ! -x "$PYTHON_PATH" ] || [ ! -f "$BOOTSTRAP_MARKER" ]; then
    rebuild_venv
fi

# 仮想環境の主要ライブラリを軽く検証
if ! "$PYTHON_PATH" -c "import requests, charset_normalizer, selenium, googleapiclient" >/dev/null 2>&1; then
    echo "⚠️ 依存関係の読み込みに失敗したため、仮想環境を再作成します..."
    rebuild_venv
fi

# 仮想環境の Python バージョンを表示
echo "▶️ 使用Python: $("$PYTHON_PATH" --version)"

# -----------------------
#  実行ログ記録
# -----------------------
echo "$(date '+%Y-%m-%d %H:%M:%S') 実行中..."

# -----------------------
# ▶️ スクリプト実行
# -----------------------
if ! "$PYTHON_PATH" "$PROJECT_DIR/$SCRIPT_NAME"; then
    echo "❌ Python処理でエラーが発生したため、Git更新を中止します。"
    exit 1
fi

# -----------------------
#  Git管理（.icsのみコミット）
# -----------------------
if [ -f "$ICS_FILE" ]; then
    git add "$ICS_FILE"
    COMMIT_MSG="Auto update at $(date '+%Y-%m-%d %H:%M')"
    git commit -m "$COMMIT_MSG" || echo "ℹ️ コミット対象の変更がありません。"

    # プッシュ前にリモートの最新状態を取り込む
    git pull --rebase --autostash origin main || { echo "❌ リモートとの差分取得に失敗しました。手動で解決してください。"; exit 1; }

    git push origin HEAD && \
      echo "✅ 更新とプッシュが成功しました。" || \
      echo "❌ Git プッシュに失敗しました。"
else
    echo "⚠️ $ICS_FILE が存在しません。"
fi
