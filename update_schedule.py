import hashlib
import re
from datetime import date, datetime, time, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

import requests
from icalendar import Calendar
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from calendar_utils import authorize_calendar, delete_events_by_ids, insert_event, list_event_ids_in_range

# ✅ GoogleカレンダーID（NG用）
NG_CALENDAR_ID = "heimao.s.outsource@17.media"

# 設定
LOGIN_URL = "https://artsvision-schedule.com/login"
SCHEDULE_BASE_URL = "https://artsvision-schedule.com/schedule"
EMAIL = "tetsue1113@gmail.com"
PASSWORD = "567artsvision"
OUTPUT_ICS_PATH = Path("existing_schedule.ics")
TIMEZONE = "Asia/Tokyo"
JST = ZoneInfo(TIMEZONE)
FETCH_MONTH_COUNT = 3
GOOGLE_EVENT_TITLE = "NG"
VOICE_EVENT_MANAGED_BY = "voice_schedule_ng_sync_v1"
ICLOUD_EVENT_MANAGED_BY = "icloud_public_ng_sync_v1"
ICLOUD_ICS_URL = "https://p192-caldav.icloud.com/published/2/NDE0NzUzNjQ1NDE0NzUzNlRjmffBnXeaL9KZ1nztY-NIKjwLl2tAvOqe3_6MiC27Z9rGcD1V5HyBwav5qR8rUFpHavwpeuT05ED3gtJoYgw"

# ChromeDriverの設定
options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)


def format_description(description):
    lines = description.split("\n")
    formatted_lines = []
    for line in lines:
        while len(line.encode("utf-8")) > 75:
            part = line[:75]
            formatted_lines.append(part)
            line = " " + line[75:]
        formatted_lines.append(line)
    return "\\n".join(formatted_lines)


def normalize_ics_url(url):
    if url.startswith("webcal://"):
        return "https://" + url[len("webcal://"):]
    return url


def to_jst_datetime(value):
    if isinstance(value, datetime):
        return value.astimezone(JST) if value.tzinfo else value.replace(tzinfo=JST)
    if isinstance(value, date):
        return datetime.combine(value, time(0, 0), tzinfo=JST)
    raise TypeError(f"未対応の日付型です: {type(value)}")


def generate_uid(schedule):
    raw = "|".join([
        schedule.get("source", ""),
        schedule.get("source_event_id", ""),
        schedule["title"],
        schedule["date"].date().isoformat(),
        schedule.get("time_range", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_time_with_overflow(date_value, time_str):
    hour, minute = map(int, time_str.split(":"))
    if hour >= 24:
        date_value += timedelta(days=1)
        hour -= 24
    return datetime(date_value.year, date_value.month, date_value.day, hour, minute, tzinfo=JST)


def parse_time_range(time_range):
    if not time_range:
        return "00:00", "23:59"

    time_range = time_range.strip()

    if " - " in time_range:
        start, end = time_range.split(" - ", 1)
        return start.strip(), end.strip()

    if "-" in time_range:
        start, end = time_range.split("-", 1)
        return start.strip(), end.strip()

    print(f"⚠️ 時間形式が不明のため終日扱いにします: {time_range}")
    return "00:00", "23:59"


def extract_event_date(schedule, year, month):
    day_element = schedule.find_element(
        By.XPATH,
        "./preceding::div[contains(concat(' ', normalize-space(@class), ' '), ' day ')][1]"
    )
    day_text = day_element.text.strip()
    match = re.search(r"\d+", day_text)
    if not match:
        raise ValueError(f"日付を取得できませんでした: {day_text}")

    current_day = int(match.group())
    return datetime(year, month, current_day, tzinfo=JST)


def iter_target_months(base_dt, count):
    base_month_index = base_dt.year * 12 + (base_dt.month - 1)
    for offset in range(count):
        month_index = base_month_index + offset
        yield month_index // 12, month_index % 12 + 1


def get_month_range(year, month):
    start_dt = datetime(year, month, 1, tzinfo=JST)
    if month == 12:
        end_dt = datetime(year + 1, 1, 1, tzinfo=JST)
    else:
        end_dt = datetime(year, month + 1, 1, tzinfo=JST)
    return start_dt, end_dt


def wait_for_schedule_page(driver):
    WebDriverWait(driver, 10).until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "div.day, a.schedule"))
    )


def create_ics_file(schedules, file_path):
    ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Organization//Your Calendar 1.0//EN
CALSCALE:GREGORIAN
"""
    for schedule in schedules:
        date_value = schedule["date"]
        start_str, end_str = parse_time_range(schedule["time_range"])

        try:
            start_dt = parse_time_with_overflow(date_value, start_str)
            end_dt = parse_time_with_overflow(date_value, end_str)
        except Exception as e:
            print(f"⚠️ 時間変換エラー: {e}")
            continue

        start_fmt = start_dt.strftime("%Y%m%dT%H%M%S")
        end_fmt = end_dt.strftime("%Y%m%dT%H%M%S")
        desc_fmt = format_description(schedule.get("description", ""))

        ics_content += f"""BEGIN:VEVENT
DTSTART;TZID={TIMEZONE}:{start_fmt}
DTEND;TZID={TIMEZONE}:{end_fmt}
SUMMARY:{schedule['title']}
DESCRIPTION:{desc_fmt}
UID:{schedule['uid']}
LOCATION:未指定
END:VEVENT
"""

    ics_content += "END:VCALENDAR"
    file_path.write_text(ics_content, encoding="utf-8")
    print(f"📤 ICSファイル更新完了: {file_path.resolve()}")


def build_google_calendar_datetimes(schedule):
    date_value = schedule["date"]
    start_str, end_str = parse_time_range(schedule["time_range"])

    start_dt = parse_time_with_overflow(date_value, start_str)
    end_dt = parse_time_with_overflow(date_value, end_str)

    if not (start_str == "00:00" and end_str == "23:59"):
        start_dt -= timedelta(minutes=60)
        end_dt += timedelta(minutes=60)

    return start_dt, end_dt


def fetch_icloud_schedules_from_public_ics(ics_url, sync_start, sync_end):
    normalized_url = normalize_ics_url(ics_url)
    response = requests.get(normalized_url, timeout=30)
    response.raise_for_status()

    calendar = Calendar.from_ical(response.content)
    schedules = []

    for component in calendar.walk():
        if component.name != "VEVENT":
            continue

        raw_start = component.get("dtstart")
        if raw_start is None:
            continue

        start_value = raw_start.dt
        start_dt = to_jst_datetime(start_value)

        if start_dt < sync_start or start_dt >= sync_end:
            continue

        summary = str(component.get("summary", "iCloud Event"))
        description = str(component.get("description", "")).strip()
        source_event_id = str(component.get("uid", ""))

        is_all_day = isinstance(start_value, date) and not isinstance(start_value, datetime)
        if is_all_day:
            time_range = ""
        else:
            raw_end = component.get("dtend")
            if raw_end is not None:
                end_dt = to_jst_datetime(raw_end.dt)
            else:
                end_dt = start_dt
            time_range = f"{start_dt.strftime('%H:%M')}-{end_dt.strftime('%H:%M')}"

        source_lines = ["【source】\niCloud", f"【original_title】\n{summary}"]
        if description:
            source_lines.append(f"【original_description】\n{description}")

        schedules.append({
            "source": "icloud",
            "source_event_id": source_event_id,
            "title": summary,
            "date": start_dt,
            "time_range": time_range,
            "description": "\n".join(source_lines),
        })

    return schedules


def sync_schedules_to_google(service, schedules, managed_by, sync_start, sync_end):
    desired_event_ids = set()

    for schedule in schedules:
        try:
            start_dt, end_dt = build_google_calendar_datetimes(schedule)
        except Exception as e:
            print(f"⚠️ Googleカレンダー用の時間変換エラー: {e}")
            continue

        desired_event_ids.add(schedule["uid"])
        insert_event(
            service,
            GOOGLE_EVENT_TITLE,
            start_dt,
            end_dt,
            calendar_id=NG_CALENDAR_ID,
            uid=schedule["uid"],
            managed_by=managed_by,
        )

    if desired_event_ids:
        existing_event_ids = list_event_ids_in_range(
            service,
            NG_CALENDAR_ID,
            sync_start,
            sync_end,
            summary_filter=GOOGLE_EVENT_TITLE,
            managed_by_filter=managed_by,
        )
        stale_event_ids = existing_event_ids - desired_event_ids
        if stale_event_ids:
            print(f"🧹 削除対象（タイトル: {GOOGLE_EVENT_TITLE} / managed_by: {managed_by}）イベント数: {len(stale_event_ids)}")
            delete_events_by_ids(service, NG_CALENDAR_ID, stale_event_ids)
        else:
            print(f"✅ 削除対象の『{GOOGLE_EVENT_TITLE}』管理イベントはありません。")
    else:
        print(f"⚠️ managed_by={managed_by} の取得スケジュールが0件だったため、誤削除防止で削除同期をスキップします。")


try:
    print("ログイン中...")
    driver.get(LOGIN_URL)
    driver.find_element(By.NAME, "mail_address").send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button.btn-login").click()
    print("ログイン成功！")

    voice_schedules = []
    today = datetime.now(JST)
    target_months = list(iter_target_months(today, FETCH_MONTH_COUNT))
    sync_start, _ = get_month_range(*target_months[0])
    _, sync_end = get_month_range(*target_months[-1])

    for year, month in target_months:
        schedule_url = f"{SCHEDULE_BASE_URL}?search_year={year}&search_month={month}"
        driver.get(schedule_url)
        print(f"📅 {year}年{month}月を取得中...")

        wait_for_schedule_page(driver)
        schedule_elements = driver.find_elements(By.CSS_SELECTOR, "a.schedule")

        for schedule in schedule_elements:
            try:
                event_date = extract_event_date(schedule, year, month)
                title = schedule.find_element(By.CSS_SELECTOR, ".title").text
                time_range = schedule.find_element(By.CSS_SELECTOR, ".time").text
                detail_link = schedule.get_attribute("href")

                voice_schedules.append({
                    "source": "voice",
                    "source_event_id": detail_link,
                    "title": title,
                    "date": event_date,
                    "time_range": time_range,
                    "detail_url": detail_link,
                })
            except Exception as e:
                print(f"⚠️ 日付取得エラー: {e}")

    print(f"✅ ボイスケ総数: {len(voice_schedules)} 件")

    for schedule in voice_schedules:
        driver.get(schedule["detail_url"])
        print(f"🔍 詳細: {schedule['detail_url']}")
        WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.CLASS_NAME, "detail-title")))

        detail_sections = {
            "スタジオ名": "", "制作会社名": "", "ディレクター名": "", "マネージャー名": "", "メモ": ""
        }

        items = driver.find_elements(By.CLASS_NAME, "detail-item")
        contents = driver.find_elements(By.CLASS_NAME, "detail-contents")

        for item, content in zip(items, contents):
            label = item.text.strip()
            value = content.text.strip()
            for key in detail_sections:
                if key in label:
                    detail_sections[key] = value

        desc = "\n".join([f"【{k}】\n{v}\n" for k, v in detail_sections.items() if v]).strip()
        schedule["description"] = desc
        schedule["uid"] = generate_uid(schedule)

    icloud_schedules = None
    try:
        icloud_schedules = fetch_icloud_schedules_from_public_ics(ICLOUD_ICS_URL, sync_start, sync_end)
        for schedule in icloud_schedules:
            schedule["uid"] = generate_uid(schedule)
        print(f"✅ iCloud総数: {len(icloud_schedules)} 件")
    except Exception as e:
        print(f"⚠️ iCloudカレンダー取得失敗のためiCloud同期をスキップします: {e}")

    all_schedules = voice_schedules + (icloud_schedules or [])
    create_ics_file(all_schedules, OUTPUT_ICS_PATH)

    service = authorize_calendar()
    sync_schedules_to_google(service, voice_schedules, VOICE_EVENT_MANAGED_BY, sync_start, sync_end)

    if icloud_schedules is not None:
        sync_schedules_to_google(service, icloud_schedules, ICLOUD_EVENT_MANAGED_BY, sync_start, sync_end)
    else:
        print("⚠️ iCloud同期は取得失敗のため未実行です。")

except Exception as e:
    print(f"❌ エラー発生: {type(e).__name__}")
    print(str(e))

    try:
        driver.save_screenshot("error_screenshot.png")
        print("📸 error_screenshot.png を保存しました")
    except Exception:
        pass

    raise

finally:
    driver.quit()
    print("🛑 ブラウザを閉じます。")
