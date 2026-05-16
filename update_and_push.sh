#!/bin/bash

# -----------------------
#  設定（ユーザーに依存しない）
# -----------------------
PROJECT_DIR="$HOME/Desktop/Python/ボイスケ更新"
PYTHON_PATH="$PROJECT_DIR/.venv/bin/python"
SCRIPT_NAME="update_schedule.py"
ICS_FILE="existing_schedule.ics"

cd "$PROJECT_DIR" || {
    echo "❌ プロジェクトディレクトリが存在しません: $PROJECT_DIR"
    exit 1
}

# -----------------------
#  仮想環境を確認・作成
# -----------------------
if [ ! -x "$PYTHON_PATH" ]; then
    echo "⚠️ 仮想環境が見つかりません。新規作成しています..."
    python3 -m venv "$PROJECT_DIR/.venv" || { echo "❌ 仮想環境の作成に失敗しました。"; exit 1; }
    # 必要なパッケージをインストール（requirements.txt がある場合）
    if [ -f "$PROJECT_DIR/requirements.txt" ]; then
        "$PROJECT_DIR/.venv/bin/pip" install -r "$PROJECT_DIR/requirements.txt" || echo "⚠️ 依存関係のインストールに失敗しました。"
    fi
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
"$PYTHON_PATH" "$PROJECT_DIR/$SCRIPT_NAME"

if [ $? -ne 0 ]; then
    echo "❌ Python処理でエラーが発生したため、Git更新を中止します。"
    exit 1
fi

# -----------------------
#  Git管理（.icsのみコミット）
# -----------------------
if [ -f "$ICS_FILE" ]; then
    git add "$ICS_FILE"
    COMMIT_MSG="Auto update at $(date '+%Y-%m-%d %H:%M')"
    git commit -m "$COMMIT_MSG"

    # プッシュ前にリモートの最新状態を取り込む
    git pull --rebase --autostash origin main || { echo "❌ リモートとの差分取得に失敗しました。手動で解決してください。"; exit 1; }

    git push origin HEAD && \
      echo "✅ 更新とプッシュが成功しました。" || \
      echo "❌ Git プッシュに失敗しました。"
else
    echo "⚠️ $ICS_FILE が存在しません。"
fi