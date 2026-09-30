import os
import sys
import time
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests

def log(msg):
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] {msg}", flush=True)

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
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "high",
                "Tags": "mosque,bell"
            },
            timeout=10
        )
        if resp.status_code == 200:
            log(">>> Push delivered to ntfy! <<<")
    except Exception as e:
        log(f"Push delivery error: {e}")

# --- 3. Scrapers & Timetable Providers ---

def fetch_masjid_noor():
    """Pulls Masjid Noor Toller Lane directly from Masjidbox API."""
    times = {}
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)",
        "Accept": "application/json"
    }
    
    # 1. Direct Masjidbox API endpoint
    try:
        api_url = "https://api.masjidbox.com/1.0/masjidbox/masjids/masjid-noor/prayer-times"
        r = requests.get(api_url, headers=headers, timeout=10)
        if r.status_code == 200:
            data = r.json().get("data", {}).get("today", {})
            if data:
                times["Fajr"] = data.get("fajr", {}).get("iqamah")
                times["Dhuhr"] = data.get("dhuhr", {}).get("iqamah")
                times["Asr"] = data.get("asr", {}).get("iqamah")
                times["Maghrib"] = data.get("maghrib", {}).get("beginning") or data.get("maghrib", {}).get("iqamah")
                times["Isha"] = data.get("isha", {}).get("iqamah")
                if all(times.values()):
                    return times
    except Exception as e:
        log(f"Masjidbox API error: {e}")

    # 2. Live Bradford Fallback (Aladhan Method 15 - UK Unified)
    try:
        api_url = "https://api.aladhan.com/v1/timingsByCity?city=Bradford&country=GB&method=15"
        r = requests.get(api_url, timeout=10).json()
        timings = r["data"]["timings"]
        times = {
            "Fajr": "06:00",
            "Dhuhr": "13:30",
            "Asr": "17:30",
            "Maghrib": timings.get("Maghrib", "18:50"),
            "Isha": "20:30"
        }
    except Exception as e:
        log(f"Fallback API error: {e}")
        times = {"Fajr": "06:00", "Dhuhr": "13:30", "Asr": "17:30", "Maghrib": "18:50", "Isha": "20:30"}

    return times

def fetch_masjid_umar():
    """Masjid Umar timetable aligned with daily sunset calculation."""
    noor = fetch_masjid_noor()
    return {
        "Fajr": noor.get("Fajr", "06:00"),
        "Dhuhr": "13:30",
        "Asr": noor.get("Asr", "17:30"),
        "Maghrib": noor.get("Maghrib", "18:50"),
        "Isha": noor.get("Isha", "20:30")
    }

# --- 4. Alert Builder ---

def build_alerts_for_mosque(mosque_name, prayer_dict, target_date):
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

            prayer_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
            clean_time_str = prayer_dt.strftime("%H:%M")

            alerts.append({
                "dt": prayer_dt - timedelta(minutes=30),
                "title": f"🕌🔔 {prayer} in 30m ({mosque_name})",
                "message": f"{prayer} is at {clean_time_str} at {mosque_name}.",
                "fired": False
            })
            alerts.append({
                "dt": prayer_dt - timedelta(minutes=15),
                "title": f"🕌🔔 {prayer} in 15m ({mosque_name})",
                "message": f"{prayer} is at {clean_time_str} at {mosque_name}.",
                "fired": False
            })
        except Exception as e:
            log(f"Error parsing {prayer} for {mosque_name}: {e}")
    return alerts

# --- 5. Main Resilient Scheduling Loop ---

def main_loop():
    current_day = None
    alerts = []

    send_alert("🕌 Salah System Restored", "Live connection active for Masjid Noor & Umar.")

    while True:
        try:
            now = datetime.now()

            if current_day != now.date():
                log(f"Loading fresh schedule for {now.date()}...")
                current_day = now.date()
                alerts = []

                noor = fetch_masjid_noor()
                umar = fetch_masjid_umar()

                log(f"Masjid Noor: {noor}")
                log(f"Masjid Umar: {umar}")

                alerts.extend(build_alerts_for_mosque("Masjid Noor", noor, current_day))
                alerts.extend(build_alerts_for_mosque("Masjid Umar", umar, current_day))

                log(f"Armed {len(alerts)} alerts. Active and listening...")

            for a in alerts:
                if not a["fired"] and a["dt"] <= now < (a["dt"] + timedelta(minutes=10)):
                    send_alert(a["title"], a["message"])
                    a["fired"] = True

        except Exception as err:
            log(f"Unexpected loop exception caught: {err}")

        time.sleep(25)

if __name__ == "__main__":
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()
    main_loop()
