import os
import base64
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def authorize_calendar():
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file("credentials.json", SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def generate_uid(schedule):
    raw = f"{schedule['title']}:{schedule['date'].isoformat()}"
    uid_bytes = raw.encode("utf-8")
    safe_uid = base64.urlsafe_b64encode(uid_bytes).decode("ascii").rstrip("=")
    return safe_uid

def insert_event(service, title, start_dt, end_dt, calendar_id="primary", uid=None):
    event = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        "id": uid[:100] if uid else None  # 最大100文字
    }

    try:
        service.events().update(calendarId=calendar_id, eventId=event["id"], body=event).execute()
        print(f"✅ 更新完了: {title}（{event['id']}）")
    except HttpError as e:
        if e.status_code == 404:
            try:
                service.events().insert(calendarId=calendar_id, body=event).execute()
                print(f"✅ 新規登録: {title}（{event['id']}）")
            except Exception as insert_error:
                print(f"❌ insert 失敗: {insert_error}")
        else:
            print(f"❌ update 失敗: {e}")
