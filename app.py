import os
import re
import time
import threading
from datetime import datetime, timedelta
from http.server import HTTPServer, BaseHTTPRequestHandler
import requests
from bs4 import BeautifulSoup

# --- 1. Keep-Alive HTTP Server (for Render & cron-job.org) ---
class SimpleHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()
        self.wfile.write(b"ok")

    def do_HEAD(self):
        self.send_response(200)
        self.send_header("Content-type", "text/plain")
        self.end_headers()

    def log_message(self, format, *args):
        # Silence routine ping log noise
        return

def start_server():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), SimpleHandler)
    server.serve_forever()

# --- 2. Push Notification Function ---
NTFY_TOPIC = "zishan_bradford_prayers"

def send_alert(title, message):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] PUSH SENT -> {title}: {message}")
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "high",
                "Tags": "mosque,bell"
            },
            timeout=8
        )
        if resp.status_code == 200:
            print(">>> Push delivered to ntfy! <<<")
    except Exception as e:
        print(f"Push delivery error: {e}")

# --- 3. Scrapers ---

def fetch_masjid_noor():
    """Fetches Masjid Noor (62 Toller Lane) live schedule via Masjidbox."""
    times = {}
    headers = {"User-Agent": "Mozilla/5.0"}
    
    # Try the direct Masjidbox API first
    try:
        api_url = "https://api.masjidbox.com/1.0/masjidbox/masjids/masjid-noor/prayer-times"
        resp = requests.get(api_url, headers=headers, timeout=10)
        if resp.status_code == 200:
            data = resp.json().get("data", {}).get("today", {})
            if data:
                times["Fajr"] = data.get("fajr", {}).get("iqamah")
                times["Dhuhr"] = data.get("dhuhr", {}).get("iqamah")
                times["Asr"] = data.get("asr", {}).get("iqamah")
                # Maghrib targets beginning/sunset so it updates daily
                times["Maghrib"] = data.get("maghrib", {}).get("beginning") or data.get("maghrib", {}).get("iqamah")
                times["Isha"] = data.get("isha", {}).get("iqamah")
                if all(times.values()):
                    return times
    except Exception:
        pass

    # Fallback to HTML scrape on the web page
    try:
        url = "https://masjidbox.com/prayer-times/masjid-noor"
        resp = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        text = soup.get_text(" ")
        time_matches = re.findall(r"\b([0-2]?[0-9]:[0-5][0-9])\b", text)
        if len(time_matches) >= 5:
            # Map earliest parsed blocks to respective prayers
            times = {
                "Fajr": time_matches[0],
                "Dhuhr": time_matches[1],
                "Asr": time_matches[2],
                "Maghrib": time_matches[3],
                "Isha": time_matches[4]
            }
    except Exception as e:
        print(f"Error fetching Masjid Noor: {e}")

    return times

def fetch_masjid_umar():
    """Scrapes Masjid Umar timetable."""
    times = {}
    try:
        url = "https://masjidumar.co.uk/"
        resp = requests.get(url, headers={"User-Agent": "Mozilla/5.0"}, timeout=10)
        soup = BeautifulSoup(resp.text, "html.parser")
        rows = soup.find_all("tr")
        for row in rows:
            cols = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if len(cols) >= 3:
                name = cols[0].lower()
                if "fajr" in name:
                    times["Fajr"] = cols[2]
                elif "dhuhr" in name or "zuhr" in name:
                    times["Dhuhr"] = cols[2]
                elif "asr" in name:
                    times["Asr"] = cols[2]
                elif "maghrib" in name:
                    # Target sunset/beginning for daily movement
                    times["Maghrib"] = cols[1] if cols[1] else cols[2]
                elif "isha" in name:
                    times["Isha"] = cols[2]
    except Exception as e:
        print(f"Error fetching Masjid Umar: {e}")
    return times

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

            # Adjust standard UK afternoon prayer times to 24-hour format
            if prayer in ["Dhuhr", "Asr", "Maghrib", "Isha"] and hour < 11:
                hour += 12

            prayer_dt = datetime(target_date.year, target_date.month, target_date.day, hour, minute)
            clean_time_str = prayer_dt.strftime("%H:%M")

            # 30 minutes before
            alerts.append({
                "dt": prayer_dt - timedelta(minutes=30),
                "title": f"🕌🔔🕌 {prayer} in 30m ({mosque_name})",
                "message": f"{prayer} is at {clean_time_str} at {mosque_name}.",
                "fired": False
            })
            # 15 minutes before
            alerts.append({
                "dt": prayer_dt - timedelta(minutes=15),
                "title": f"🕌🔔🕌 {prayer} in 15m ({mosque_name})",
                "message": f"{prayer} is at {clean_time_str} at {mosque_name}.",
                "fired": False
            })
        except Exception as e:
            print(f"Error parsing {prayer} ({time_str}) for {mosque_name}: {e}")
            continue
    return alerts

# --- 5. Main Scheduler Loop ---

def main_loop():
    current_day = None
    alerts = []

    send_alert("🕌🔔🕌 Salah System Online", "Connected to Masjid Noor (Toller Lane) & Masjid Umar.")

    while True:
        now = datetime.now()

        # Re-fetch and re-arm every midnight (or at container launch)
        if current_day != now.date():
            print(f"\n[{now.strftime('%H:%M:%S')}] Date changed ({now.date()}). Scraping fresh prayer times...")
            current_day = now.date()
            alerts = []

            noor = fetch_masjid_noor()
            umar = fetch_masjid_umar()

            print(f"Masjid Noor (Toller Lane): {noor}")
            print(f"Masjid Umar: {umar}")

            alerts.extend(build_alerts_for_mosque("Masjid Noor", noor, current_day))
            alerts.extend(build_alerts_for_mosque("Masjid Umar", umar, current_day))

            print(f"[{now.strftime('%H:%M:%S')}] Armed {len(alerts)} alerts for today. Listening...")

        # Fire alerts
        for a in alerts:
            if not a["fired"] and a["dt"] <= now < (a["dt"] + timedelta(minutes=10)):
                send_alert(a["title"], a["message"])
                a["fired"] = True

        time.sleep(20)

if __name__ == "__main__":
    # Start the HTTP server thread so Render stays alive
    server_thread = threading.Thread(target=start_server, daemon=True)
    server_thread.start()

    # Run the notification loop
    main_loop()
