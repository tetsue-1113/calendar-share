import os
from datetime import timedelta
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request

# ✅ カレンダーAPIのスコープ
SCOPES = ['https://www.googleapis.com/auth/calendar']

# ✅ credentials.json の絶対パス（ここを環境に合わせて変更）
CREDENTIALS_PATH = "/Users/tetsuei/Desktop/jupyter lab/ボイスケ更新/credentials.json"
TOKEN_PATH = "/Users/tetsuei/Desktop/jupyter lab/ボイスケ更新/token.json"

def authorize_calendar():
    creds = None
    if os.path.exists(TOKEN_PATH):
        creds = Credentials.from_authorized_user_file(TOKEN_PATH, SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(CREDENTIALS_PATH, SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_PATH, 'w') as token:
            token.write(creds.to_json())
    return build('calendar', 'v3', credentials=creds)

def insert_event(service, title, start_dt, end_dt, calendar_id="primary", uid=None):
    event = {
        'summary': title,
        'start': {'dateTime': start_dt.isoformat(), 'timeZone': 'Asia/Tokyo'},
        'end': {'dateTime': end_dt.isoformat(), 'timeZone': 'Asia/Tokyo'},
    }
    if uid:
        event['id'] = uid.replace(":", "_")[:100]  # UID を Google カレンダーの ID 形式に合わせる

    try:
        service.events().update(calendarId=calendar_id, eventId=event['id'], body=event).execute()
        print(f"✅ 更新/登録完了: {start_dt.isoformat()} - {title}")
    except Exception as e:
        print(f"⚠️ 更新失敗、再試行（insert）: {e}")
        service.events().insert(calendarId=calendar_id, body=event).execute()
        print(f"✅ 登録完了（新規）: {start_dt.isoformat()} - {title}")
