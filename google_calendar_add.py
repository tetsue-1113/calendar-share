from __future__ import print_function
import datetime
import os.path
import pytz

from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build

# 📌 GoogleカレンダーID（マイカレンダーなら "primary"）
CALENDAR_ID = 'primary'

# 🔐 認証スコープ（カレンダー編集権限）
SCOPES = ['https://www.googleapis.com/auth/calendar']

# 📅 追加したいイベント（ここは例。今後はschedulesから生成）
TEST_EVENTS = [
    {
        'summary': 'NG',
        'start': datetime.datetime(2025, 6, 1, 13, 0),
        'end': datetime.datetime(2025, 6, 1, 14, 0),
    },
    {
        'summary': 'NG',
        'start': datetime.datetime(2025, 6, 2, 10, 30),
        'end': datetime.datetime(2025, 6, 2, 12, 0),
    }
]

def authorize_calendar():
    """認証してGoogle Calendar APIのサービスを返す"""
    creds = None
    if os.path.exists('token.json'):
        creds = Credentials.from_authorized_user_file('token.json', SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file('credentials.json', SCOPES)
            creds = flow.run_local_server(port=0)
        with open('token.json', 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def insert_event(service, event):
    """前後90分を加味してイベントをGoogleカレンダーに追加"""
    timezone = pytz.timezone("Asia/Tokyo")

    adjusted_start = event['start'] - datetime.timedelta(minutes=90)
    adjusted_end = event['end'] + datetime.timedelta(minutes=90)

    event_body = {
        'summary': 'NG',
        'start': {
            'dateTime': adjusted_start.isoformat(),
            'timeZone': 'Asia/Tokyo',
        },
        'end': {
            'dateTime': adjusted_end.isoformat(),
            'timeZone': 'Asia/Tokyo',
        }
    }
    created = service.events().insert(calendarId=CALENDAR_ID, body=event_body).execute()
    print(f"✅ 登録完了: {created.get('start').get('dateTime')} - NG")

if __name__ == '__main__':
    service = authorize_calendar()
    for e in TEST_EVENTS:
        insert_event(service, e)
