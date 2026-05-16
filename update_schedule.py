import hashlib
import re
from datetime import datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriver_manager.chrome import ChromeDriverManager

from calendar_utils import authorize_calendar, delete_events_by_ids, insert_event, list_event_ids_in_range

# ✅ GoogleカレンダーID（NG用）
NG_CALENDAR_ID = "c_e360256dca0cfae181f48a877df0fb4c835645a801efb3e85f3c72ba7008a3c2@group.calendar.google.com"

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


def generate_uid(schedule):
    raw = "|".join([
        schedule["title"],
        schedule["date"].date().isoformat(),
        schedule.get("time_range", ""),
        schedule.get("detail_url", ""),
    ])
    return hashlib.sha256(raw.encode("utf-8")).hexdigest()


def parse_time_with_overflow(date, time_str):
    hour, minute = map(int, time_str.split(":"))
    if hour >= 24:
        date += timedelta(days=1)
        hour -= 24
    return datetime(date.year, date.month, date.day, hour, minute, tzinfo=JST)


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
        date = schedule["date"]
        start_str, end_str = parse_time_range(schedule["time_range"])

        try:
            start_dt = parse_time_with_overflow(date, start_str)
            end_dt = parse_time_with_overflow(date, end_str)
        except Exception as e:
            print(f"⚠️ 時間変換エラー: {e}")
            continue

        start_fmt = start_dt.strftime("%Y%m%dT%H%M%S")
        end_fmt = end_dt.strftime("%Y%m%dT%H%M%S")
        desc_fmt = format_description(schedule["description"])

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
    date = schedule["date"]
    start_str, end_str = parse_time_range(schedule["time_range"])

    start_dt = parse_time_with_overflow(date, start_str)
    end_dt = parse_time_with_overflow(date, end_str)

    if not (start_str == "00:00" and end_str == "23:59"):
        start_dt -= timedelta(minutes=60)
        end_dt += timedelta(minutes=60)

    return start_dt, end_dt


try:
    print("ログイン中...")
    driver.get(LOGIN_URL)
    driver.find_element(By.NAME, "mail_address").send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button.btn-login").click()
    print("ログイン成功！")

    schedules = []
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

                schedules.append({
                    "title": title,
                    "date": event_date,
                    "time_range": time_range,
                    "detail_url": detail_link,
                })
            except Exception as e:
                print(f"⚠️ 日付取得エラー: {e}")

    print(f"✅ スケジュール総数: {len(schedules)} 件")

    for schedule in schedules:
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

    create_ics_file(schedules, OUTPUT_ICS_PATH)

    service = authorize_calendar()
    desired_event_ids = set()

    for schedule in schedules:
        try:
            start_dt, end_dt = build_google_calendar_datetimes(schedule)
        except Exception as e:
            print(f"⚠️ Googleカレンダー用の時間変換エラー: {e}")
            continue

        desired_event_ids.add(schedule["uid"])
        insert_event(service, GOOGLE_EVENT_TITLE, start_dt, end_dt, calendar_id=NG_CALENDAR_ID, uid=schedule["uid"])

    # 専用の同期用カレンダーを前提に、取得対象期間に存在する不要イベントを削除する
    if desired_event_ids:
        existing_event_ids = list_event_ids_in_range(service, NG_CALENDAR_ID, sync_start, sync_end)
        stale_event_ids = existing_event_ids - desired_event_ids
        if stale_event_ids:
            print(f"🧹 削除対象イベント数: {len(stale_event_ids)}")
            delete_events_by_ids(service, NG_CALENDAR_ID, stale_event_ids)
        else:
            print("✅ 削除対象イベントはありません。")
    else:
        print("⚠️ 取得スケジュールが0件だったため、誤削除防止で削除同期をスキップします。")

except Exception as e:
    print(f"❌ エラー発生: {type(e).__name__}")
    print(str(e))

    try:
        driver.save_screenshot("error_screenshot.png")
        print("📸 error_screenshot.png を保存しました")
    except:
        pass

    raise

finally:
    driver.quit()
    print("🛑 ブラウザを閉じます。")
