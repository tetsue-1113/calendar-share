#!/bin/bash

# -----------------------
# 🔧 設定（ユーザーに依存しない）
# -----------------------
PROJECT_DIR="$HOME/Desktop/jupyter lab/ボイスケ更新"
PYTHON_PATH="/opt/anaconda3/bin/python3"  # ← 環境によって違う可能性があるため注意
SCRIPT_NAME="update_schedule.py"
ICS_FILE="existing_schedule.ics"

cd "$PROJECT_DIR" || {
    echo "❌ プロジェクトディレクトリが存在しません: $PROJECT_DIR"
    exit 1
}

# -----------------------
# 🕒 実行ログ記録
# -----------------------
echo "🔄 $(date '+%Y-%m-%d %H:%M:%S') 実行中..."

# -----------------------
# ▶️ スクリプト実行
# -----------------------
"$PYTHON_PATH" "$PROJECT_DIR/$SCRIPT_NAME"

# -----------------------
# 📦 Git管理（.icsのみコミット）
# -----------------------
if [ -f "$ICS_FILE" ]; then
    git add "$ICS_FILE"
    COMMIT_MSG="Auto update at $(date '+%Y-%m-%d %H:%M')"
    git commit -m "$COMMIT_MSG"
    git push

    if [ $? -eq 0 ]; then
        echo "✅ 更新とプッシュが成功しました。"
    else
        echo "❌ Git プッシュに失敗しました。"
    fi
else
    echo "⚠️ $ICS_FILE が存在しません。"
fi