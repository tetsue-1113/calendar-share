import os
import hashlib
from datetime import datetime, timedelta
from pathlib import Path
from bs4 import BeautifulSoup
import pytz
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager

from calendar_utils import authorize_calendar, insert_event

# -----------------------------
# 📌 設定と定数
# -----------------------------

# ✅ GoogleカレンダーID（NG用）
NG_CALENDAR_ID = "c_e360256dca0cfae181f48a877df0fb4c835645a801efb3e85f3c72ba7008a3c2@group.calendar.google.com"

# サイトURLとログイン情報
LOGIN_URL = "https://artsvision-schedule.com/login"
SCHEDULE_BASE_URL = "https://artsvision-schedule.com/schedule"
EMAIL = "tetsue1113@gmail.com"
PASSWORD = "567artsvision"

# タイムゾーン設定
timezone = "Asia/Tokyo"
tokyo = pytz.timezone(timezone)

# ファイルパス設定
BASE_DIR = Path.home() / "Desktop" / "Python" / "ボイスケ更新"
output_ics_path = BASE_DIR / "existing_schedule.ics"

# -----------------------------
# 🧭 WebDriver（ヘッドレスChrome）の初期化
# -----------------------------

options = Options()
options.add_argument("--headless")
driver = webdriver.Chrome(service=Service(ChromeDriverManager().install()), options=options)

# -----------------------------
# 関数定義
# -----------------------------

def format_description(description):
    """
    説明文を75バイトごとに改行し、ICSファイルのフォーマットに対応させる。
    """
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
    """
    スケジュールのタイトルと日付から一意のUIDを生成する。
    """
    raw = f"{schedule['title']}:{schedule['date'].isoformat()}"
    return hashlib.sha256(raw.encode()).hexdigest()

def parse_time_with_overflow(date, time_str):
    """
    時刻文字列を解析し、24時越えを考慮してdatetimeオブジェクトを返す。
    """
    hour, minute = map(int, time_str.split(":"))
    if hour >= 24:
        date += timedelta(days=1)
        hour -= 24
    dt = datetime(date.year, date.month, date.day, hour, minute)
    return tokyo.localize(dt)

try:
    # -----------------------------
    # 🔐 サイトにログイン
    # -----------------------------
    print("ログイン中...")
    driver.get(LOGIN_URL)
    driver.find_element(By.NAME, "mail_address").send_keys(EMAIL)
    driver.find_element(By.NAME, "password").send_keys(PASSWORD)
    driver.find_element(By.CSS_SELECTOR, "button.btn-login").click()
    print("ログイン成功！")

    # -----------------------------
    # 📅 スケジュールページの巡回とデータ抽出
    # -----------------------------
    schedules = []
    today = datetime.now(tokyo)

    for offset in range(0, 3):
        target_date = today + timedelta(days=offset * 30)
        year = target_date.year
        month = target_date.month

        schedule_url = f"{SCHEDULE_BASE_URL}?search_year={year}&search_month={month}"
        driver.get(schedule_url)
        print(f"📅 {year}年{month}月を取得中...")

        WebDriverWait(driver, 10)
        schedule_elements = driver.find_elements(By.CSS_SELECTOR, "a.schedule")
        for schedule in schedule_elements:
            try:
                day_element = schedule.find_element(By.XPATH, "./preceding::div[@class='day '][1]")
                current_day = int(day_element.text.strip())
                event_date = datetime(year, month, current_day)
                event_date = tokyo.localize(event_date)

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

    # 詳細ページから追加情報を取得
    for schedule in schedules:
        driver.get(schedule["detail_url"])
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

    # -----------------------------
    # 🗓️ ICSファイルの生成
    # -----------------------------
    def create_ics_file(schedules, file_path):
        ics_content = """BEGIN:VCALENDAR
VERSION:2.0
PRODID:-//Your Organization//Your Calendar 1.0//EN
CALSCALE:GREGORIAN
"""
        for schedule in schedules:
            date = schedule["date"]
            time_range = schedule["time_range"]
            try:
                start_str, end_str = time_range.split(" - ")
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

    # -----------------------------
    # 📤 Googleカレンダーへのイベント登録
    # -----------------------------
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

            # イベント時間の前後に余裕を持たせる（60分）
            if not (start_str == "00:00" and end_str == "23:59"):
                start_dt -= timedelta(minutes=60)
                end_dt += timedelta(minutes=60)

        except Exception as e:
            print(f"⚠️ Googleカレンダー用の時間変換エラー: {e}")
            continue

        insert_event(service, "NG", start_dt, end_dt, calendar_id=NG_CALENDAR_ID, uid=schedule["uid"])

except Exception as e:
    print(f"❌ エラー発生: {e}")

finally:
    # -----------------------------
    # 🧹 ブラウザ終了処理
    # -----------------------------
    driver.quit()
    print("🛑 ブラウザを閉じます。")
