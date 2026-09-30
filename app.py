import os
import sys
import time
import threading
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

UK_TZ = ZoneInfo("Europe/London")

def get_uk_now():
    return datetime.now(UK_TZ)

def log(msg):
    print(f"[{get_uk_now().strftime('%Y-%m-%d %H:%M:%S %Z')}] {msg}", flush=True)

# --- 1. Keep-Alive HTTP Server (for Render & cron-job.org) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"OK")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        return

def start_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. Push Notification Function ---
NTFY_TOPIC = "zishan_bradford_prayers"

def send_alert(title, message):
    log(f"PUSH SENT -> {title}: {message}")
    try:
        # Strip out multi-byte emoji characters from the HTTP header to avoid Latin-1 header errors
        clean_title = (
            title.replace("🕌", "")
            .replace("🔔", "")
            .strip()
        )
        
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": clean_title,
                "Priority": "urgent",
                "Tags": "mosque,bell"
            },
            timeout=10
        )
        log(f">>> Push status: {resp.status_code} <<<")
    except Exception as e:
        log(f"Push delivery error: {e}")

# --- 3. Dynamic Bradford Maghrib (Sunset) ---
def get_daily_maghrib(target_date):
    try:
        api_url = f"https://api.aladhan.com/v1/timingsByCity/{target_date.strftime('%d-%m-%Y')}?city=Bradford&country=GB&method=15"
        r = requests.get(api_url, timeout=6).json()
        return r["data"]["timings"].get("Maghrib", "18:49")
    except Exception:
        return "18:49"

# --- 4. Official Printed Timetables ---

def get_masjid_noor_times(target_date):
    """Masjid Noor (Toller Lane, Bradford) official printed schedule."""
    m = target_date.month
    d = target_date.day
    maghrib = get_daily_maghrib(target_date)

    if m == 1:
        fajr = "07:15" if d <= 15 else "07:00"
        dhuhr = "12:30"
        asr = "14:45" if d <= 15 else "15:00"
        isha = "19:15" if d <= 15 else "19:30"
    elif m == 2:
        fajr = "06:45" if d <= 15 else "06:30"
        dhuhr = "12:30"
        asr = "15:30" if d <= 15 else "16:00"
        isha = "19:30" if d <= 15 else "19:45"
    elif m == 3:
        if d <= 15:
            fajr, dhuhr, asr, isha = "06:00", "12:30", "16:30", "20:00"
        elif d <= 28:
            fajr, dhuhr, asr, isha = "05:45", "12:30", "16:45", "20:15"
        else:
            fajr, dhuhr, asr, isha = "06:15", "13:30", "18:00", "21:30"
    elif m == 4:
        dhuhr = "13:30"
        fajr = "05:30" if d <= 15 else "05:00"
        asr = "18:15" if d <= 15 else "18:30"
        isha = "21:45" if d <= 15 else "22:00"
    elif m == 5:
        dhuhr = "13:30"
        fajr = "04:30" if d <= 15 else "04:15"
        asr = "19:00" if d <= 15 else "19:15"
        isha = "22:30" if d <= 15 else "22:45"
    elif m == 6:
        fajr = "04:00"
        dhuhr = "13:30"
        asr = "20:00"
        isha = "23:00"
    elif m == 7:
        dhuhr = "13:30"
        fajr = "04:00" if d <= 15 else "04:15"
        asr = "20:00" if d <= 15 else "19:45"
        isha = "23:00" if d <= 15 else "22:45"
    elif m == 8:
        dhuhr = "13:30"
        fajr = "04:30" if d <= 15 else "05:00"
        asr = "19:00" if d <= 15 else "18:30"
        isha = "22:15" if d <= 15 else "21:30"
    elif m == 9:
        dhuhr = "13:30"
        fajr = "05:30" if d <= 15 else "06:00"
        asr = "18:00" if d <= 15 else "17:45"
        isha = "21:00" if d <= 15 else "20:30"
    elif m == 10:
        dhuhr = "13:30" if d < 30 else "12:30"
        if d < 8:
            fajr, asr, isha = "06:30", "17:15", "20:15"
        elif d < 15:
            fajr, asr, isha = "06:45", "17:00", "20:00"
        elif d < 22:
            fajr, asr, isha = "07:00", "16:45", "19:45"
        elif d < 30:
            fajr, asr, isha = "07:15", "16:30", "19:45"
        else:
            fajr, asr, isha = "06:45", "15:30", "19:00"
    elif m == 11:
        dhuhr = "12:30"
        fajr = "06:45" if d <= 15 else "07:00"
        asr = "15:15" if d <= 15 else "15:00"
        isha = "19:00"
    elif m == 12:
        dhuhr = "12:30"
        fajr = "07:15"
        asr = "14:45"
        isha = "19:00"
    else:
        fajr, dhuhr, asr, isha = "06:00", "13:30", "17:45", "20:30"

    return {"Fajr": fajr, "Dhuhr": dhuhr, "Asr": asr, "Maghrib": maghrib, "Isha": isha}

def get_masjid_umar_times(target_date):
    """Masjid E Umar (Girlington) official printed 2026 calendar."""
    m = target_date.month
    d = target_date.day
    maghrib = get_daily_maghrib(target_date)

    if m == 1:
        dhuhr = "12:45"
        isha = "18:30" if d < 26 else "19:45"
        fajr = "07:15"
        asr = "14:45" if d < 10 else ("15:00" if d < 24 else "15:15")
    elif m == 2:
        dhuhr = "12:45"
        fajr = "07:00" if d < 7 else ("06:45" if d < 14 else ("06:30" if d < 18 else "05:32"))
        asr = "15:45" if d < 7 else ("16:00" if d < 14 else ("16:15" if d < 21 else "16:30"))
        isha = "18:45" if d < 8 else ("19:00" if d < 15 else ("19:15" if d < 18 else "19:15"))
    elif m == 3:
        if d < 29:
            dhuhr = "12:45"
            fajr = "05:08" if d < 7 else ("04:51" if d < 14 else ("04:33" if d < 21 else "04:09"))
            asr = "16:45" if d < 7 else ("17:00" if d < 14 else ("17:15" if d < 21 else "17:30"))
            isha = "19:45" if d < 7 else ("20:00" if d < 14 else ("20:15" if d < 21 else "20:30"))
        else:
            fajr, dhuhr, asr, isha = "06:00", "13:45", "18:45", "21:35"
    elif m == 4:
        dhuhr = "13:45"
        fajr = "06:00" if d < 4 else ("05:45" if d < 11 else ("05:30" if d < 18 else ("05:15" if d < 25 else "05:00")))
        asr = "18:45" if d < 4 else ("19:00" if d < 11 else ("19:15" if d < 18 else ("19:30" if d < 25 else "19:45")))
        isha = "21:35" if d < 4 else ("21:45" if d < 18 else "22:00")
    elif m == 5:
        dhuhr = "13:45"
        fajr = "05:00" if d < 9 else ("04:45" if d < 16 else ("04:30" if d < 23 else "04:15"))
        asr = "19:45" if d < 9 else "20:00"
        isha = "22:00" if d < 9 else ("22:15" if d < 16 else ("22:30" if d < 23 else "22:45"))
    elif m == 6:
        dhuhr = "13:45"
        fajr = "04:10"
        asr = "20:00"
        isha = "22:40" if d < 6 else ("22:45" if d < 13 else "22:50")
    elif m == 7:
        dhuhr = "13:45"
        fajr = "04:10" if d < 4 else ("04:15" if d < 11 else ("04:20" if d < 18 else ("04:30" if d < 25 else "04:40")))
        asr = "20:00" if d < 25 else "19:45"
        isha = "22:50" if d < 11 else ("22:45" if d < 18 else ("22:30" if d < 25 else "22:15"))
    elif m == 8:
        dhuhr = "13:45"
        fajr = "05:00" if d < 8 else ("05:15" if d < 15 else ("05:30" if d < 22 else ("05:45" if d < 29 else "05:45")))
        asr = "19:45" if d < 8 else ("19:30" if d < 15 else ("19:15" if d < 22 else ("19:00" if d < 29 else "18:45")))
        isha = "22:10" if d < 8 else ("22:00" if d < 15 else ("21:40" if d < 22 else ("21:20" if d < 29 else "21:00")))
    elif m == 9:
        dhuhr = "13:45"
        if d < 5:
            fajr, asr, isha = "05:45", "19:00", "21:40"
        elif d < 12:
            fajr, asr, isha = "06:00", "18:30", "21:25"
        elif d < 19:
            fajr, asr, isha = "06:00", "18:15", "21:15"
        elif d < 26:
            fajr, asr, isha = "06:15", "18:00", "21:00"
        else:
            fajr, asr, isha = "06:30", "17:45", "20:40"
    elif m == 10:
        if d < 25:
            dhuhr = "13:45"
            if d < 3:
                fajr, asr, isha = "06:30", "17:45", "20:40"
            elif d < 10:
                fajr, asr, isha = "06:45", "17:30", "20:20"
            elif d < 17:
                fajr, asr, isha = "07:00", "17:15", "20:00"
            elif d < 24:
                fajr, asr, isha = "07:15", "17:00", "19:45"
            else:
                fajr, asr, isha = "07:15", "16:45", "19:30"
        else:
            dhuhr = "12:45"
            fajr = "06:30" if d < 31 else "06:40"
            asr = "15:45" if d < 31 else "15:30"
            isha = "18:30"
    elif m == 11:
        dhuhr = "12:45"
        fajr = "06:40" if d < 7 else ("06:45" if d < 14 else ("07:00" if d < 21 else ("07:10" if d < 28 else "07:15")))
        asr = "15:45" if d < 7 else ("15:30" if d < 14 else ("15:15" if d < 21 else ("15:00" if d < 28 else "14:45")))
        isha = "18:30"
    elif m == 12:
        dhuhr = "12:45"
        fajr = "07:15"
        asr = "14:45" if d < 12 else ("14:45" if d < 26 else "15:00")
        isha = "18:30"
    else:
        fajr, dhuhr, asr, isha = "06:00", "13:45", "18:00", "20:45"

    return {"Fajr": fajr, "Dhuhr": dhuhr, "Asr": asr, "Maghrib": maghrib, "Isha": isha}

# --- 5. Alert Builder (Timezone Aware) ---

def build_alerts(mosque_name, prayer_dict, target_date):
    alerts = []
    for prayer, time_str in prayer_dict.items():
        if not time_str:
            continue
        try:
            parts = str(time_str).strip().split(":")
            hour = int(parts[0])
            minute = int(parts[1][:2])

            if prayer in ["Dhuhr", "Asr", "Maghrib", "Isha"] and hour < 11:
                hour += 12

            prayer_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute, tzinfo=UK_TZ)
            clean_time_str = prayer_dt.strftime("%H:%M")

            alerts.append({
                "dt": prayer_dt - timedelta(minutes=30),
                "title": f"{prayer} in 30m ({mosque_name})",
                "message": f"{prayer} Jama'ah is at {clean_time_str}.",
                "fired": False
            })
            alerts.append({
                "dt": prayer_dt - timedelta(minutes=15),
                "title": f"{prayer} in 15m ({mosque_name})",
                "message": f"{prayer} Jama'ah is at {clean_time_str}.",
                "fired": False
            })
        except Exception as e:
            log(f"Error parsing {prayer} ({time_str}): {e}")
    return alerts

# --- 6. Main 24/7 Scheduling Loop ---

def main_loop():
    current_day = None
    alerts = []

    # Startup test push to verify ntfy delivery on boot
    send_alert("Salah System Active", "Timezone locked to UK (BST/GMT).")

    while True:
        try:
            now = get_uk_now()

            if current_day != now.date():
                log(f"Loading scheduled times for UK date: {now.date()}...")
                current_day = now.date()
                alerts = []

                noor_times = get_masjid_noor_times(current_day)
                umar_times = get_masjid_umar_times(current_day)

                log(f"Masjid Noor: {noor_times}")
                log(f"Masjid Umar: {umar_times}")

                alerts.extend(build_alerts("Masjid Noor", noor_times, current_day))
                alerts.extend(build_alerts("Masjid Umar", umar_times, current_day))

                log(f"Armed {len(alerts)} UK alerts. Listening...")

            for a in alerts:
                if not a["fired"] and a["dt"] <= now < (a["dt"] + timedelta(minutes=10)):
                    send_alert(a["title"], a["message"])
                    a["fired"] = True
                    time.sleep(1)

        except Exception as err:
            log(f"Unexpected loop exception: {err}")

        time.sleep(25)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    main_loop()
