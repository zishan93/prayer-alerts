import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import os
import time
from datetime import datetime, timedelta
import requests
from bs4 import BeautifulSoup

NTFY_TOPIC = "zishan_bradford_prayers"

def send_alert(title, message):
    print(f"\n[{datetime.now().strftime('%H:%M:%S')}] PUSH SENT -> {title}: {message}")
    
    # Phone Push (ntfy app)
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "high",
                "Tags": "mosque,bell"
            },
            timeout=5
        )
        if resp.status_code == 200:
            print(">>> Phone push delivered successfully to ntfy! <<<")
        else:
            print(f"ntfy status: {resp.status_code}")
    except Exception as e:
        print(f"Phone push error: {e}")

    # 2. Phone Push (ntfy app)
    try:
        resp = requests.post(
            f"https://ntfy.sh/{NTFY_TOPIC}",
            data=message.encode("utf-8"),
            headers={
                "Title": title.encode("utf-8"),
                "Priority": "high",
                "Tags": "mosque,bell"
            },
            timeout=5
        )
        if resp.status_code == 200:
            print(">>> Phone push delivered successfully to ntfy! <<<")
        else:
            print(f"ntfy status: {resp.status_code}")
    except Exception as e:
        print(f"Phone push error: {e}")

def fetch_masjid_noor():
    """Masjidbox API with proper browser User-Agent header to avoid 403."""
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Referer": "https://masjidbox.com/prayer-times/masjid-noor"
    }
    try:
        url = "https://api.masjidbox.com/1.0/masjidbox/public/landing/masjid-noor"
        resp = requests.get(url, headers=headers, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        timetable = data.get("timetable", {}).get("today", {})
        if timetable:
            return {
                "Fajr": timetable.get("fajr", {}).get("iqama", "06:00"),
                "Dhuhr": timetable.get("dhuhr", {}).get("iqama", "13:30"),
                "Asr": timetable.get("asr", {}).get("iqama", "18:15"),
                "Maghrib": timetable.get("maghrib", {}).get("iqama", "19:40"),
                "Isha": timetable.get("isha", {}).get("iqama", "21:15")
            }
    except Exception as e:
        print(f"Masjid Noor API error: {e}")
    return {"Fajr": "06:00", "Dhuhr": "13:30", "Asr": "18:15", "Maghrib": "19:40", "Isha": "21:15"}

def fetch_masjid_umar():
    """Masjid Umar Girlington timetable."""
    try:
        headers = {"User-Agent": "Mozilla/5.0"}
        resp = requests.get("https://www.masjid-e-umar.com/prayer-times", headers=headers, timeout=10)
        resp.raise_for_status()
        soup = BeautifulSoup(resp.text, "html.parser")
        
        now = datetime.now()
        day_str = f"{now.day:02d}"
        for row in soup.find_all("tr"):
            cells = [c.get_text(strip=True) for c in row.find_all(["td", "th"])]
            if cells and cells[0].startswith(day_str) and len(cells) >= 11:
                # Jama'ah times are the last 5 columns
                return {
                    "Fajr": cells[-5],
                    "Dhuhr": cells[-4],
                    "Asr": cells[-3],
                    "Maghrib": cells[-2],
                    "Isha": cells[-1]
                }
    except Exception as e:
        print(f"Masjid Umar error: {e}")
    return {"Fajr": "06:00", "Dhuhr": "13:30", "Asr": "18:15", "Maghrib": "19:40", "Isha": "21:15"}

def parse_to_dt(time_str, is_pm=False):
    today = datetime.now().date()
    clean = time_str.strip().upper()
    for fmt in ("%H:%M", "%I:%M %p", "%I:%M%p", "%I:%M"):
        try:
            t = datetime.strptime(clean, fmt).time()
            dt = datetime.combine(today, t)
            if is_pm and dt.hour < 12:
                dt += timedelta(hours=12)
            return dt
        except ValueError:
            continue
    return None

def run():
    print("Connecting...")
    # IMMEDIATE TEST ALERT - verifies phone connection on launch
    send_alert("🕌 Salah System Active", "Phone linked! 30-min & 15-min alerts will arrive here.")

    current_date = None
    alerts = []

    while True:
        now = datetime.now()
        
        if current_date != now.date():
            print(f"\n--- Loading times for {now.strftime('%d/%m/%Y')} ---")
            noor = fetch_masjid_noor()
            umar = fetch_masjid_umar()
            print(f"Masjid Noor (Toller Lane): {noor}")
            print(f"Masjid Umar (Girlington):  {umar}")
            
            alerts = []
            for m_name, schedule in [("Masjid Noor", noor), ("Masjid Umar", umar)]:
                for prayer, t_str in schedule.items():
                    is_pm = prayer in ["Dhuhr", "Asr", "Maghrib", "Isha"]
                    jamat_dt = parse_to_dt(t_str, is_pm)
                    if not jamat_dt:
                        continue
                    
                    alerts.append({"dt": jamat_dt - timedelta(minutes=30), "prayer": prayer, "mins": 30, "t": t_str, "m": m_name, "fired": False})
                    alerts.append({"dt": jamat_dt - timedelta(minutes=15), "prayer": prayer, "mins": 15, "t": t_str, "m": m_name, "fired": False})
            
            current_date = now.date()
            print(f"Armed {len(alerts)} alerts for today. Listening...")

        for a in alerts:
            if not a["fired"] and now >= a["dt"] and now < (a["dt"] + timedelta(minutes=5)):
                send_alert(f"🕌 {a['prayer']} in {a['mins']}m ({a['m']})", f"{a['prayer']} Jama'ah is at {a['t']} at {a['m']}.")
                a["fired"] = True

        time.sleep(20)
def keep_alive():
    port = int(os.environ.get("PORT", 10000))
    server = HTTPServer(("0.0.0.0", port), BaseHTTPRequestHandler)
    server.serve_forever()


if __name__ == "__main__":
    threading.Thread(target=keep_alive, daemon=True).start()
    run()

