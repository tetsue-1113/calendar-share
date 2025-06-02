from __future__ import print_function
import datetime
import pytz
import os.path
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# トークンとクレデンシャルのファイルパス
TOKEN_PATH = 'token.json'
CREDENTIALS_PATH = 'credentials.json'

# Google CalendarのID（"primary"ならマイカレンダー）
CALENDAR_ID = 'primary'

# 東京のタイムゾーン
JST = pytz.timezone('Asia/Tokyo')


def load_credentials():
    """トークンまたは認証情報を読み込む"""
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            raise Exception("有効な認証情報が存在しません。'token.json'を再作成してください。")
    return creds


def create_event(service, start_dt, end_dt, summary):
    """イベントを作成してGoogleカレンダーに登録する"""
    # 前後1時間（60分）を加算
    is_allday = start_dt.hour == 0 and start_dt.minute == 0 and end_dt.hour == 23 and end_dt.minute == 59

    if not is_allday:
        start_dt = start_dt - datetime.timedelta(minutes=60)
        end_dt = end_dt + datetime.timedelta(minutes=60)

    # ISO形式に変換
    start_iso = start_dt.isoformat()
    end_iso = end_dt.isoformat()

    event = {
        'summary': summary,
        'start': {
            'dateTime': start_iso,
            'timeZone': 'Asia/Tokyo',
        },
        'end': {
            'dateTime': end_iso,
            'timeZone': 'Asia/Tokyo',
        },
    }

    service.events().insert(calendarId=CALENDAR_ID, body=event).execute()


def main(events):
    """
    events: List[Dict] 形式で [{'summary': 'NG 山田太郎', 'start': datetime, 'end': datetime}, ...]
    """
    creds = load_credentials()
    service = build('calendar', 'v3', credentials=creds)

    for e in events:
        create_event(service, e['start'], e['end'], e['summary'])
