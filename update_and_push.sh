#!/bin/bash
set -x  # デバッグ用ログ出力ON

echo "🔄 $(date '+%Y-%m-%d %H:%M:%S') 実行中..."

# Pythonでスケジュール取得とICS生成＋Googleカレンダー登録
/opt/anaconda3/bin/python3 "/Users/tetsuei/Desktop/jupyter lab/ボイスケ更新/update_schedule.py"

# GitHubにICSファイルをpush（icsをWeb共有）
cd "/Users/tetsuei/Desktop/jupyter lab/ボイスケ更新"

git add existing_schedule.ics
git commit -m "Auto update at $(date '+%Y-%m-%d %H:%M')"
git push

# 成否ログ
if [ $? -eq 0 ]; then
    echo "✅ 更新とプッシュが成功しました。"
else
    echo "❌ 更新またはプッシュに失敗しました。"
fi
