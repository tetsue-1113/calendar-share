import os
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from google.auth.transport.requests import Request
from googleapiclient.errors import HttpError

SCOPES = ["https://www.googleapis.com/auth/calendar"]

def authorize_calendar(credentials_path=None):
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", SCOPES)
    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            if credentials_path is None:
                credentials_path = os.path.join(os.path.dirname(__file__), "credentials.json")
            flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
            creds = flow.run_local_server(port=0)
        with open("token.json", "w") as token:
            token.write(creds.to_json())
    return build("calendar", "v3", credentials=creds)

def insert_event(service, title, start_dt, end_dt, calendar_id="primary", uid=None, managed_by=None):
    event = {
        "summary": title,
        "start": {"dateTime": start_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        "end": {"dateTime": end_dt.isoformat(), "timeZone": "Asia/Tokyo"},
        "id": uid[:100] if uid else None  # 最大100文字
    }

    if managed_by:
        event["extendedProperties"] = {
            "private": {
                "managed_by": managed_by
            }
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


def list_event_ids_in_range(service, calendar_id, time_min, time_max, summary_filter=None, managed_by_filter=None):
    event_ids = set()
    page_token = None

    while True:
        response = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min.isoformat(),
            timeMax=time_max.isoformat(),
            singleEvents=True,
            showDeleted=False,
            pageToken=page_token,
        ).execute()

        for event in response.get("items", []):
            event_id = event.get("id")
            summary = event.get("summary", "")
            managed_by = (
                event.get("extendedProperties", {})
                .get("private", {})
                .get("managed_by")
            )
            if summary_filter is not None and summary != summary_filter:
                continue
            if managed_by_filter is not None and managed_by != managed_by_filter:
                continue
            if event_id:
                event_ids.add(event_id)

        page_token = response.get("nextPageToken")
        if not page_token:
            break

    return event_ids


def delete_events_by_ids(service, calendar_id, event_ids):
    for event_id in sorted(event_ids):
        try:
            service.events().delete(calendarId=calendar_id, eventId=event_id).execute()
            print(f"🗑️ 削除完了: {event_id}")
        except HttpError as e:
            if e.status_code == 404:
                print(f"ℹ️ 既に存在しません: {event_id}")
            else:
                print(f"❌ 削除失敗: {event_id} / {e}")
