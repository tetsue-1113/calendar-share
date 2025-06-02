import os
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from calendar_utils import authorize_calendar, insert_event

# ✅ GoogleカレンダーID（NG用）
NG_CALENDAR_ID = "c_e360256dca0cfae181f48a877df0fb4c835645a801efb3e85f3c72ba7008a3c2@group.calendar.google.com"

# 設定
LOGIN_URL = "https://artsvision-schedule.com/login"
SCHEDULE_BASE_URL = "https://artsvision-schedule.com/schedule"
EMAIL = "tetsue1113@gmail.com"
PASSWORD = "567artsvision"
output_ics_path = Path("existing_schedule.ics")
timezone = "Asia/Tokyo"

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
    return f"{schedule['title']}:{schedule['date'].isoformat()}"

def parse_time_with_overflow(date, time_str):
    hour, minute = map(int, time_str.split(":"))
    if hour >= 24:
        date += timedelta(days=1)
        hour -= 24
    return datetime(date.year, date.month, date.day, hour, minute)

try:
    print("ログイン中...")
    driver.get(LOGIN_URL)
    driver.find_element(By.NAME, "mail_address").send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button.btn-login").click()
    print("ログイン成功！")

    schedules = []
    today = datetime.now()

    for offset in range(0, 3):
        target_date = today + timedelta(days=offset * 30)
        year = target_date.year
        month = target_date.month

        schedule_url = f"{SCHEDULE_BASE_URL}?search_year={year}&search_month={month}"
        driver.get(schedule_url)
        print(f"📅 {year}年{month}月を取得中...")

        WebDriverWait(driver, 10).until(
            EC.presence_of_all_elements_located((By.CSS_SELECTOR, "a.schedule"))
        )
        schedule_elements = driver.find_elements(By.CSS_SELECTOR, "a.schedule")

        for schedule in schedule_elements:
            try:
                day_element = schedule.find_element(By.XPATH, "./preceding::div[@class='day '][1]")
                current_day = int(day_element.text.strip())
                event_date = datetime(year, month, current_day)

                title = schedule.find_element(By.CSS_SELECTOR, ".title").text
                time_range = schedule.find_element(By.CSS_SELECTOR, ".time").text
                detail_link = schedule.get_attribute("href")

                schedules.append({
                    "title": title,
                    "date": event_date,
                    "time_range": time_range,
                    "detail_url": detail_link
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

    def create_ics_file(schedules, file_path):
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Organization//Your Calendar 1.0//EN
CALSCALE:GREGORIAN
"""
        for schedule in schedules:
            date = schedule["date"]
            try:
                start_str, end_str = schedule["time_range"].split(" - ")
            except:
                start_str, end_str = "00:00", "23:59"

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
DTSTART;TZID={timezone}:{start_fmt}
DTEND;TZID={timezone}:{end_fmt}
SUMMARY:{schedule["title"]}
DESCRIPTION:{desc_fmt}
UID:{schedule["uid"]}
LOCATION:未指定
END:VEVENT
"""

        ics_content += "END:VCALENDAR"
        file_path.write_text(ics_content, encoding="utf-8")
        print(f"📤 ICSファイル更新完了: {file_path.resolve()}")

    create_ics_file(schedules, output_ics_path)

    # 🔄 Googleカレンダーへ登録
    service = authorize_calendar()
    for schedule in schedules:
        date = schedule["date"]
        try:
            start_str, end_str = schedule["time_range"].split(" - ")
        except:
            start_str, end_str = "00:00", "23:59"

        try:
            start_dt = parse_time_with_overflow(date, start_str)
            end_dt = parse_time_with_overflow(date, end_str)

            if not (start_str == "00:00" and end_str == "23:59"):
                start_dt -= timedelta(minutes=60)
                end_dt += timedelta(minutes=60)

        except Exception as e:
            print(f"⚠️ Googleカレンダー用の時間変換エラー: {e}")
            continue

        insert_event(service, schedule["title"], start_dt, end_dt, calendar_id=NG_CALENDAR_ID, uid=schedule["uid"])

except Exception as e:
    print(f"❌ エラー発生: {e}")
finally:
    driver.quit()
    print("🛑 ブラウザを閉じます。")
