"""Build an iCalendar feed from a Nutrislice school lunch menu (stdlib only)."""
import datetime as dt, json, urllib.request, pathlib

DISTRICT = "lvjusdchildnutrition"
SCHOOL   = "arroyo-seco-elementary"
MENU     = "elementary-lunch-menu"
WEEKS    = 6                      # current week + 5 ahead
TITLE    = "Arroyo Seco Lunch"
OUT      = pathlib.Path("public/lunch.ics")
UA       = {"User-Agent": "Mozilla/5.0"}

def fetch_week(d):
    url = (f"https://{DISTRICT}.api.nutrislice.com/menu/api/weeks/school/{SCHOOL}"
           f"/menu-type/{MENU}/{d.year}/{d.month:02d}/{d.day:02d}/?format=json")
    with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=20) as r:
        return json.load(r).get("days", [])

def parse_day(day):
    sections, cur = {}, "Menu"
    for it in day.get("menu_items", []):
        food = it.get("food") or {}
        if it.get("is_section_title") or (it.get("text") and not food):
            cur = (it.get("text") or "").strip() or cur
            continue
        name = (food.get("name") or "").strip()
        if name:
            sections.setdefault(cur, []).append(name)
    return sections

def esc(s):
    return s.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")

def fold(line):
    b, out = line.encode(), []
    while len(b) > 75:
        cut = 75 if not out else 74
        while (b[cut] & 0xC0) == 0x80: cut -= 1   # don't split UTF-8 chars
        out.append(b[:cut].decode()); b = b[cut:]
    out.append(b.decode())
    return "\r\n ".join(out)

def main():
    today = dt.date.today()
    sunday = today - dt.timedelta(days=(today.weekday() + 1) % 7)
    stamp = dt.datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//lunch-menu-ics//EN",
             "CALSCALE:GREGORIAN", f"X-WR-CALNAME:{TITLE}",
             "REFRESH-INTERVAL;VALUE=DURATION:PT12H", "X-PUBLISHED-TTL:PT12H"]
    for w in range(WEEKS):
        start = sunday + dt.timedelta(weeks=w)
        try:
            days = fetch_week(start)
        except Exception as e:
            print(f"week {start}: {e}"); continue
        for day in days:
            date = dt.date.fromisoformat(day["date"])
            secs = parse_day(day)
            if date.weekday() >= 5 or not secs:
                continue
            first = next(iter(secs.values()))
            summary = "🍎 " + " / ".join(first[:2])
            desc = "\n\n".join(f"{k}:\n" + "\n".join(f"• {f}" for f in v) for k, v in secs.items())
            link = f"https://{DISTRICT}.nutrislice.com/menu/{SCHOOL}/{MENU}/{date}"
            lines += ["BEGIN:VEVENT", f"UID:{SCHOOL}-{date:%Y%m%d}@lunch-menu-ics",
                      f"DTSTAMP:{stamp}", f"DTSTART;VALUE=DATE:{date:%Y%m%d}",
                      f"DTEND;VALUE=DATE:{date + dt.timedelta(days=1):%Y%m%d}",
                      f"SUMMARY:{esc(summary)}", f"DESCRIPTION:{esc(desc + chr(10)*2 + link)}",
                      f"URL:{link}", "TRANSP:TRANSPARENT", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text("\r\n".join(fold(l) for l in lines) + "\r\n", encoding="utf-8")
    print(f"wrote {OUT} ({sum(l == 'BEGIN:VEVENT' for l in lines)} events)")

if __name__ == "__main__":
    main()
