#!/usr/bin/env python3
"""Race details for the "Bingo de course" automatic check: the final classification of each Formula 1 Grand Prix of the season
(position, driver, team, laps, time or reason of retirement, grid slot, points), the notes under the table (penalties) and a few
yes/no facts read from the race report (red flag, safety car, virtual safety car, rain).

Source: the English Wikipedia race articles (text licensed CC BY-SA 4.0). Only facts are extracted, never prose; the app credits Wikipedia.

  python3 Tools/race_details.py --results Resources/OpenResults/open-results.json --out race-details.json
  python3 Tools/race_details.py --results results.json --previous race-details.json --out race-details.json   # daily job: only new races

The list of rounds (and their dates) comes from the file written by open_results.py. A race whose article cannot be read is skipped
and listed under "errors"; the others are still written. Races older than 21 days are kept from the previous file (one request per new race)."""
import argparse, html, json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone, timedelta

UA = {"User-Agent": "MotorsportHubData/1.0 (https://github.com/mtpshub-prog; mtpshub@gmail.com)"}
FINAL_AFTER_DAYS = 21

def fetch(title, retries=3):
    url = "https://en.wikipedia.org/w/api.php?" + urllib.parse.urlencode(
        {"action": "parse", "page": title, "prop": "text", "format": "json", "formatversion": 2, "redirects": 1})
    for i in range(retries):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                d = json.loads(r.read())
            return d["parse"]["text"] if "parse" in d else None
        except Exception:
            time.sleep(1.5 * (i + 1))
    return None

def clean(s):
    s = re.sub(r"<(sup|style|script)[^>]*>.*?</\1>", "", s, flags=re.S)
    s = re.sub(r"<link[^>]*>", "", s)
    s = re.sub(r"<br\s*/?>", " ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace("\xa0", " ")).strip()

def int_or_none(text):
    m = re.match(r"^\s*(\d+)", text or "")
    return int(m.group(1)) if m else None

def classification(page):
    """The main race table: header with Pos., Laps, Time/Retired and Grid, not the one under a "Sprint" heading."""
    for m in re.finditer(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', page, re.S):
        rows = re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S)
        if not rows:
            continue
        head = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", rows[0], re.S)]
        if not (len(head) >= 8 and head[0].startswith("Pos") and "Laps" in head and any(h.startswith("Time") for h in head) and "Grid" in head):
            continue
        headings = re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", page[:m.start()], re.S)
        title = clean(headings[-1]) if headings else ""
        if re.search(r"sprint", title, re.I):
            continue
        idx = {name: head.index(name) for name in ("Pos.", "No.", "Driver", "Constructor", "Laps", "Grid", "Points") if name in head}
        tcol = next(i for i, h in enumerate(head) if h.startswith("Time"))
        out = []
        for tr in rows[1:]:
            cells = [clean(c) for c in re.findall(r"<t[dh][^>]*>(.*?)</t[dh]>", tr, re.S)]
            if len(cells) < len(head) or not cells[idx["Driver"]]:
                continue
            raw_time = cells[tcol]
            out.append({
                "pos": cells[idx["Pos."]],                       # "1", "2"… or "Ret", "DNS", "DSQ", "NC"
                "no": cells[idx["No."]],
                "driver": cells[idx["Driver"]],
                "team": cells[idx["Constructor"]],
                "laps": int_or_none(cells[idx["Laps"]]) or 0,
                "time": re.sub(r"(?<=\S)[a-z]$", "", raw_time) if re.search(r"[\d.]\s*[a-z]$", raw_time) else raw_time,   # drops the footnote letter
                "grid": re.sub(r"[a-z]$", "", cells[idx["Grid"]]) if re.match(r"^\d+[a-z]$", cells[idx["Grid"]]) else cells[idx["Grid"]],
                "pts": cells[idx["Points"]],
            })
        notes = []
        tail = page[m.end():m.end() + 12000]
        ul = re.search(r"<b>Notes</b>.*?<ul>(.*?)</ul>", tail, re.S)
        if ul:
            notes = [clean(li) for li in re.findall(r"<li>(.*?)</li>", ul.group(1), re.S)]
        if len(out) >= 10:
            return out, notes
    return None, []

def narrative(page):
    """Text of the race report: from the "Race" heading to the classification."""
    start = re.search(r'<h2[^>]*id="Race"[^>]*>', page)
    if not start:
        return ""
    end = re.search(r'<h2[^>]*id="(Race_classification|Championship_standings_after_the_race|Classification)"', page[start.end():])
    body = page[start.end():start.end() + (end.start() if end else 40000)]
    body = re.sub(r"<table.*?</table>", " ", body, flags=re.S)
    return clean(body)

def flags(text):
    return {
        "redFlag": bool(re.search(r"\bred[- ]flag", text, re.I)),
        "safetyCar": bool(re.search(r"(?<!virtual )(?<!Virtual )\bsafety car\b", text)) or bool(re.search(r"\bSafety car\b", text)),
        "vsc": bool(re.search(r"virtual safety car|\bVSC\b", text, re.I)),
        "rain": bool(re.search(r"\brain(ed|ing|y|fall)?\b|\bwet (track|conditions|weather|race)\b|\bdownpour\b|\bintermediate (tyres|tires)\b", text, re.I)),
    }

def race_record(season, rnd):
    title = f"{season} {rnd['name']}"
    page = fetch(title)
    if not page:
        return None, f"{title}: article not found"
    rows, notes = classification(page)
    if not rows:
        return None, f"{title}: no race classification table"
    text = narrative(page)
    return {"round": rnd["round"], "name": rnd["name"], "date": rnd.get("date"), "title": title,
            "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(title.replace(" ", "_")),
            "pole": rnd.get("pole"), "fastest": rnd.get("fastest"),
            "rows": rows, "notes": notes, "flags": flags(text)}, None

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", default="results.json")
    ap.add_argument("--previous", default="")
    ap.add_argument("--out", default="race-details.json")
    a = ap.parse_args()
    results = json.load(open(a.results, encoding="utf-8"))["championships"]["f1"]
    season, today = results["season"], datetime.now(timezone.utc).date()
    previous = {}
    if a.previous:
        try:
            old = json.load(open(a.previous, encoding="utf-8"))["championships"]["f1"]
            if old["season"] == season:
                previous = {r["round"]: r for r in old["races"]}
        except Exception:
            pass
    races, errors = [], {}
    for rnd in results["rounds"]:
        day = datetime.strptime(rnd["date"], "%Y-%m-%d").date() if rnd.get("date") else None
        if day is None or day > today:
            continue
        kept = previous.get(rnd["round"])
        if kept and (today - day) > timedelta(days=FINAL_AFTER_DAYS):
            races.append(kept)
            continue
        record, error = race_record(season, rnd)
        if record:
            races.append(record)
            print(f"round {rnd['round']:2d} {rnd['name']:32s} rows={len(record['rows'])} notes={len(record['notes'])} flags={[k for k, v in record['flags'].items() if v]}")
        else:
            errors[str(rnd["round"])] = error
            if kept:
                races.append(kept)
            print("skipped:", error, file=sys.stderr)
        time.sleep(1.0)   # one polite request at a time
    races.sort(key=lambda r: r["round"])
    doc = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
           "championships": {"f1": {"season": season, "races": races,
                                    "source": {"name": "Wikipedia", "license": "CC BY-SA 4.0", "licenseURL": "https://creativecommons.org/licenses/by-sa/4.0/"}}},
           "errors": errors}
    with open(a.out, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    print(f"{len(races)} races written to {a.out}; errors: {errors}")

if __name__ == "__main__":
    main()
