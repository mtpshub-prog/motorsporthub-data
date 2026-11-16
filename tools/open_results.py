#!/usr/bin/env python3
"""Open results for the Results tab: winner of every round and the season standings, read from the English Wikipedia
season articles (text licensed CC BY-SA 4.0; results and standings are facts, credited per championship in the output).

  python3 Tools/open_results.py --out results.json           # all championships
  python3 Tools/open_results.py --only f1,wec --out /tmp/r.json

Written once a day by a GitHub Action (the pages are large, a phone or a free Worker should not parse them).
The app reads the small `results.json` and shows the credit "Wikipédia · CC BY-SA 4.0" next to it.
Every championship is independent: a page that changes shape is skipped, the others are still written."""
import argparse, html, json, re, sys, time, urllib.parse, urllib.request
from datetime import datetime, timezone

UA = {"User-Agent": "MotorsportHubData/1.0 (https://github.com/mtpshub-prog; mtpshub@gmail.com)"}
MONTHS = {m: i + 1 for i, m in enumerate("january february march april may june july august september october november december".split())}
MONTHS.update({m[:3]: i for m, i in list(MONTHS.items())})

def titles(year):
    yy = lambda y: str(y)[2:]
    fe = lambda y: f"{y - 1}–{yy(y)} Formula E World Championship"
    fe2 = lambda y: f"{y}–{yy(y + 1)} Formula E World Championship"
    return {
        "f1": [f"{year} Formula One World Championship"],
        "f2": [f"{year} Formula 2 Championship"],
        "f3": [f"{year} FIA Formula 3 Championship"],
        "fe": [fe(year), fe2(year)],
        "indycar": [f"{year} IndyCar Series"],
        "indy_nxt": [f"{year} Indy NXT"],
        "super_formula": [f"{year} Super Formula Championship"],
        "wec": [f"{year} FIA World Endurance Championship"],
        "imsa": [f"{year} IMSA SportsCar Championship"],
        "elms": [f"{year} European Le Mans Series"],
        "alms": [f"{year - 1}–{yy(year)} Asian Le Mans Series", f"{year}–{yy(year + 1)} Asian Le Mans Series"],
        "gtwc_europe": [f"{year} GT World Challenge Europe"],
        "dtm": [f"{year} Deutsche Tourenwagen Masters", f"{year} DTM"],
        "british_gt": [f"{year} British GT Championship"],
        "wrc": [f"{year} World Rally Championship"],
        "erc": [f"{year} European Rally Championship"],
        "nascar_cup": [f"{year} NASCAR Cup Series"],
        "nascar_xfinity": [f"{year} NASCAR O'Reilly Auto Parts Series", f"{year} NASCAR Xfinity Series"],
        "nascar_trucks": [f"{year} NASCAR Craftsman Truck Series"],
        "supercars": [f"{year} Supercars Championship"],
        "btcc": [f"{year} British Touring Car Championship"],
    }

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

# ---------- HTML tables -> grids ----------
def clean(s):
    s = re.sub(r"<(sup|style|script)[^>]*>.*?</\1>", "", s, flags=re.S)
    s = re.sub(r"<br\s*/?>", " / ", s)
    s = re.sub(r"<[^>]+>", "", s)
    return re.sub(r"\s+", " ", html.unescape(s).replace(" ", " ")).strip()

def tables(h):
    out = []
    for m in re.finditer(r'<table[^>]*class="[^"]*wikitable[^"]*"[^>]*>(.*?)</table>', h, re.S):
        heads = re.findall(r"<h[2-4][^>]*>(.*?)</h[2-4]>", h[:m.start()], re.S)
        heading = clean(heads[-1]).replace("[edit]", "").strip() if heads else ""
        grid, pending = [], {}
        for tr in re.findall(r"<tr[^>]*>(.*?)</tr>", m.group(1), re.S):
            row, col = [], 0
            cells = re.findall(r"<(t[hd])([^>]*)>(.*?)</\1>", tr, re.S)
            def fill():
                nonlocal col
                while col in pending:
                    text, left = pending[col]
                    row.append(text)
                    if left <= 1: del pending[col]
                    else: pending[col] = (text, left - 1)
                    col += 1
            for tag, attrs, body in cells:
                fill()
                text = clean(body)
                rs = int((re.search(r'rowspan="?(\d+)', attrs) or [0, 1])[1])
                cs = int((re.search(r'colspan="?(\d+)', attrs) or [0, 1])[1])
                for k in range(cs):
                    row.append(text)
                    if rs > 1: pending[col] = (text, rs - 1)
                    col += 1
            fill()
            if row: grid.append(row)
        if len(grid) >= 2: out.append((heading, grid))
    return out

def find_col(header, *patterns):
    for i, h in enumerate(header):
        if any(re.search(p, h, re.I) for p in patterns): return i
    return None

def first_col(header, patterns):
    """Index of the first column matching the earliest pattern of the list."""
    for p in patterns:
        i = find_col(header, p)
        if i is not None: return i
    return None

def parse_date(text, year):
    """Last day of "6–9 November", "November 6–9", "8 March 2026", "Feb 15" -> YYYY-MM-DD or None."""
    t = text.lower().replace("–", "-").replace("—", "-")
    months = [(m.start(), MONTHS[m.group(0)]) for m in re.finditer(r"\b(" + "|".join(sorted(MONTHS, key=len, reverse=True)) + r")\b", t)]
    if not months: return None
    mon = months[-1][1]
    nums = [int(n) for n in re.findall(r"\b(\d{1,2})\b(?!\d)", re.sub(r"\b(19|20)\d{2}\b", " ", t))]
    if not nums: return None
    day = nums[-1] if t.rfind(str(nums[-1])) > months[-1][0] or len(nums) == 1 else nums[-1]
    y = re.search(r"\b(20\d{2})\b", t)
    yr = int(y.group(1)) if y else year
    try: return datetime(yr, mon, day).strftime("%Y-%m-%d")
    except ValueError: return None

def num(text):
    m = re.search(r"-?\d[\d,]*\.?\d*", text.replace("−", "-"))
    if not m: return None
    try: return float(m.group(0).replace(",", ""))
    except ValueError: return None

def parse_page(h, season_year):
    rounds, dates, standings = [], {}, []
    for heading, grid in tables(h):
        head = grid[0]
        # calendar / schedule: round -> date
        rc, dc = first_col(head, [r"^(round|rnd|rd|no|event)\.?$"]), find_col(head, r"date")
        if rc is not None and dc is not None and find_col(head, r"winn") is None:
            for row in grid[1:]:
                n = num(row[rc]) if rc < len(row) else None
                d = parse_date(row[dc], season_year) if dc < len(row) else None
                if n is not None and d: dates.setdefault(int(n), d)
            continue
        # round results: has a winner column (driver first; otherwise the winning team / class winners)
        wall = [i for i, c in enumerate(head) if re.search(r"winn", c, re.I)
                and not re.search(r"co-?driver|navigator|time|independent|jst|points", c, re.I)]
        wdrv = [i for i in wall if not re.search(r"team|constructor|manufacturer|entrant", head[i], re.I)]
        wcols = wdrv or wall
        # a colspan repeats its header: keep the first column of each run
        wcols = [i for k, i in enumerate(wcols) if k == 0 or not (i == wcols[k - 1] + 1 and head[i] == head[wcols[k - 1]])]
        # several winner columns only when each names a class ("Hypercar winners", "GTP Winning Drivers"); otherwise the first one
        if len(wcols) > 1 and not all(re.sub(r"(?i)\s*(overall\s+)?(winning|winners?).*", "", head[i]).strip() for i in wcols):
            wcols = wcols[:1]
        if wcols and rc is not None and not rounds:
            cars = {}
            masked = ["" if i in wall else c for i, c in enumerate(head)]
            nc = first_col(masked, [r"grand prix", r"^event", r"race name|^race$|^race ", r"^rally", r"stage", r"circuit|track"])
            tc = find_col(head, r"winning (team|constructor|manufacturer|entrant)") if wdrv else None
            pc, fc = find_col(head, r"pole"), find_col(head, r"fastest")
            for row in grid[1:]:
                n = num(row[rc]) if rc < len(row) else None
                if n is None or len(row) <= max(wcols): continue
                winners = [(head[i], row[i]) for i in wcols if row[i] and not re.search(r"^(tbc|tba|cancelled|canceled|—|-|n/a|\W*)$", row[i], re.I)]
                if not winners: continue
                name_cell = row[nc] if nc is not None and nc < len(row) else ""
                if name_cell and all(w == name_cell for _, w in winners): continue   # footnote row repeated by a rowspan
                # prototype/GT tables list the winning car (No. 38 ...) on one row and its drivers on the next one
                if all(re.match(r"^(no\.?|#)\s*\d+", w, re.I) for _, w in winners):
                    cars[int(n)] = winners
                    continue
                r = {"round": int(n), "name": row[nc] if nc is not None and nc < len(row) and row[nc] else f"Round {int(n)}"}
                r["winner"] = winners[0][1]
                if len(winners) > 1 or re.search(r"winners", head[wcols[0]], re.I):
                    r["winners"] = [{"class": re.sub(r"\s*(winning|winners?).*", "", c, flags=re.I).strip() or None, "name": w} for c, w in winners]
                    car = {c: w for c, w in cars.pop(int(n), [])}
                    for item in r["winners"]:
                        for key, w in car.items():
                            if key and item["class"] and key.split()[0] == item["class"].split()[0]: item["team"] = w
                    if len(winners) > 1: r["winner"] = " · ".join((f"{x['class']}: " if x["class"] else "") + x["name"] for x in r["winners"][:3])
                if tc is not None and tc < len(row) and row[tc]: r["team"] = row[tc]
                if pc is not None and pc < len(row): r["pole"] = row[pc]
                if fc is not None and fc < len(row): r["fastest"] = row[fc]
                rounds.append(r)
            for n, ws in cars.items():   # cars without a drivers row: show the cars
                if not any(x["round"] == n for x in rounds): rounds.append({"round": n, "name": f"Round {n}", "winner": " · ".join(w for _, w in ws[:3])})
            rounds.sort(key=lambda x: x["round"])
            continue
        # standings: Pos. + a name column ... + points
        if re.match(r"^pos", head[0], re.I) and len(head) >= 3:
            nc = find_col(head, r"driver|rider|constructor|manufacturer|team|entrant|car")
            pc = find_col(head[::-1], r"^(points|pts)\.?$")
            pts_col = len(head) - 1 - pc if pc is not None else None
            if nc is None or pts_col is None: continue
            tc = find_col(head, r"^team$|^entrant$") if find_col(head, r"driver|rider") is not None else None
            rows = []
            for row in grid[1:]:
                if len(row) <= pts_col: continue
                pos = num(row[0]) if re.match(r"^\d+", row[0]) else None
                pts = num(row[pts_col])
                if pos is None or pts is None or not row[nc]: continue
                item = {"pos": int(pos), "name": row[nc], "points": pts}
                if tc is not None and tc < len(row) and tc != nc and row[tc]: item["team"] = row[tc]
                rows.append(item)
            if len(rows) >= 3:
                cat = re.sub(r"\s*(standings|championship)s?\b.*", "", heading, flags=re.I).strip(" '’") or head[nc]
                standings.append({"category": cat, "rows": rows[:25]})
    for r in rounds:
        if r["round"] in dates: r["date"] = dates[r["round"]]
    # keep the first table per category name
    seen, uniq = set(), []
    for s in standings:
        if s["category"] in seen: continue
        seen.add(s["category"]); uniq.append(s)
    return rounds, uniq

def collect(only=None, year=None):
    year = year or datetime.now(timezone.utc).year
    out, errors = {}, {}
    cands = titles(year)
    for cid, options in cands.items():
        if only and cid not in only: continue
        best = None
        for t in options + ([o.replace(str(year), str(year - 1)) for o in options] if cid not in ("fe", "alms") else []):
            h = fetch(t)
            if not h: continue
            sy = int((re.search(r"(20\d\d)", t) or [0, year])[1])
            rounds, standings = parse_page(h, sy)
            if rounds or standings:
                cand = {"title": t, "season": sy, "rounds": rounds, "standings": standings}
                if best is None or (rounds and not best["rounds"]): best = cand
                if rounds: break
        if not best:
            errors[cid] = "no usable table"
            continue
        best["source"] = {"name": "Wikipedia", "url": "https://en.wikipedia.org/wiki/" + urllib.parse.quote(best["title"].replace(" ", "_")),
                          "license": "CC BY-SA 4.0", "licenseURL": "https://creativecommons.org/licenses/by-sa/4.0/"}
        out[cid] = best
    return out, errors

if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", default="results.json")
    ap.add_argument("--only", default="")
    ap.add_argument("--year", type=int, default=0)
    a = ap.parse_args()
    data, errors = collect(set(filter(None, a.only.split(","))), a.year or None)
    doc = {"generatedAt": datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"), "championships": data, "errors": errors}
    with open(a.out, "w", encoding="utf-8") as f: json.dump(doc, f, ensure_ascii=False, separators=(",", ":"))
    for cid, c in data.items():
        print(f"{cid:15s} {c['title'][:44]:44s} rounds={len(c['rounds']):2d} last={c['rounds'][-1]['winner'] if c['rounds'] else '-':22s} standings={[ (s['category'], len(s['rows'])) for s in c['standings']][:3]}")
    print("errors:", errors)
