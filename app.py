"""Daglige gjøremål – a simple TODO app built from the weekly plan in data/.

Run:  python app.py
Then the browser opens at http://localhost:8000
"""

import csv
import json
import re
import uuid
import webbrowser
from datetime import datetime
from http.server import HTTPServer, SimpleHTTPRequestHandler
from pathlib import Path
from urllib.parse import parse_qs, urlparse

ROOT = Path(__file__).parent
DATA_DIR = ROOT / "data"
REVOLVING_FILE = DATA_DIR / "rullerende.json"
COMMENTS_FILE = DATA_DIR / "kommentarer.json"
NAMES_FILE = DATA_DIR / "vakter.json"
PLAN_FILE = DATA_DIR / "plan.json"
HISTORY_FILE = DATA_DIR / "plan_historikk.json"
HISTORY_SIZE = 10
TODO_FILE = DATA_DIR / "todo.json"
PORT = 8000

DAYS = ["Mandag", "Tirsdag", "Onsdag", "Torsdag", "Fredag", "Lørdag", "Søndag"]
SHIFTS = ["Dag", "Kveld", "Natt"]
SEASONS = ["spring", "summer", "fall", "winter"]
STATUSES = ["partly", "not"]

# Split a cell into sentences, but not on things like "1. etg" or "kl 20.30."
SENTENCE_SPLIT = re.compile(r"(?<=[.!?)])\s+(?=[A-ZÆØÅ])")


def split_tasks(text):
    tasks = []
    for line in text.splitlines():
        for part in SENTENCE_SPLIT.split(line.strip()):
            part = part.strip()
            if part:
                tasks.append(part)
    return tasks


def parse_csv():
    """Read the original sheet into {"rows": {day: {shift: [row, ...]}}, "asNeeded": [...]}."""
    csv_file = next(DATA_DIR.glob("*.csv"))
    rows = {day: {shift: [] for shift in SHIFTS} for day in DAYS}
    as_needed = []
    day = shift = None

    with open(csv_file, encoding="utf-8-sig", newline="") as f:
        for row in csv.reader(f, delimiter=";"):
            row += [""] * (4 - len(row))
            col_day, col_shift, col_task = row[1].strip(), row[2].strip(), row[3].strip()

            if col_shift.lower().startswith("ved behov"):
                as_needed = [t.strip() for t in re.split(r",| eller ", col_shift.split(":", 1)[1]) if t.strip()]
                break  # the rest of the sheet is only notes ("Husk å snu arket", "Annet")
            if col_day in DAYS:
                day = col_day
            if col_shift in SHIFTS:
                shift = col_shift
            if day and shift and col_task:
                rows[day][shift].append("\n".join(" ".join(line.split()) for line in col_task.splitlines()))

    return {"rows": rows, "asNeeded": as_needed}


def load_base():
    """The editable plan: data/plan.json once someone has edited it, otherwise the CSV."""
    if PLAN_FILE.exists():
        return json.loads(PLAN_FILE.read_text(encoding="utf-8"))
    return parse_csv()


def load_plan():
    """{"days": {day: {shift: [task, ...]}}, "rows": {...}, "asNeeded": [...]}.

    "days" has each sentence as its own task (for the app's checklist), while "rows"
    keeps the sheet's rows, which is what gets one signature on the printout.
    """
    base = load_base()
    days = {d: {s: [t for row in base["rows"][d][s] for t in split_tasks(row)] for s in SHIFTS} for d in DAYS}
    return {"days": days, **base}


# ---------- Editing the fixed chores, with the last HISTORY_SIZE edits kept ----------
# A section key is "Mandag|Dag", "asNeeded" (Ved behov) or "*" (the whole plan, used by reset).

def get_section(base, key):
    if key == "*":
        return base
    if key == "asNeeded":
        return base["asNeeded"]
    day, shift = key.split("|")
    return base["rows"][day][shift]


def set_section(base, key, value):
    if key == "*":
        return value
    if key == "asNeeded":
        base["asNeeded"] = value
    else:
        day, shift = key.split("|")
        base["rows"][day][shift] = value
    return base


def valid_key(key):
    if key in ("asNeeded", "*"):
        return True
    day, _, shift = str(key).partition("|")
    return day in DAYS and shift in SHIFTS


def load_history():
    if HISTORY_FILE.exists():
        return json.loads(HISTORY_FILE.read_text(encoding="utf-8"))
    return []


def apply_edit(key, new_value, kind="edit", note=""):
    base = load_base()
    before = get_section(base, key)
    if before == new_value:
        return
    base = set_section(base, key, new_value)
    PLAN_FILE.write_text(json.dumps(base, ensure_ascii=False, indent=2), encoding="utf-8")

    history = load_history()
    history.insert(0, {"id": uuid.uuid4().hex[:8], "time": datetime.now().isoformat(timespec="minutes"),
                       "key": key, "kind": kind, "note": note, "before": before, "after": new_value})
    HISTORY_FILE.write_text(json.dumps(history[:HISTORY_SIZE], ensure_ascii=False, indent=2), encoding="utf-8")


def clean_rows(rows):
    return [str(r).strip()[:2000] for r in rows if str(r).strip()]


def load_revolving():
    """Rotating chores: [{"id", "text", "timesPerYear", "seasons": ["spring", "summer", ...]}]."""
    if not REVOLVING_FILE.exists():
        return []
    chores = json.loads(REVOLVING_FILE.read_text(encoding="utf-8"))
    for c in chores:  # older entries had a single "season" ("all" or one season)
        if "season" in c:
            old = c.pop("season")
            c["seasons"] = list(SEASONS) if old == "all" else [old]
    return chores


def save_revolving(chores):
    REVOLVING_FILE.write_text(json.dumps(chores, ensure_ascii=False, indent=2), encoding="utf-8")


def load_comments():
    """Comments per date and task: {"2026-10-16": {"Dag0": {"comment", "status", "task"}}}."""
    if COMMENTS_FILE.exists():
        return json.loads(COMMENTS_FILE.read_text(encoding="utf-8"))
    return {}


def save_comments(comments):
    COMMENTS_FILE.write_text(json.dumps(comments, ensure_ascii=False, indent=2), encoding="utf-8")


def load_names():
    """Who is on each shift: {"2026-10-16": {"Dag": "Kari", "Kveld": "Ola"}}."""
    if NAMES_FILE.exists():
        return json.loads(NAMES_FILE.read_text(encoding="utf-8"))
    return {}


def save_names(names):
    NAMES_FILE.write_text(json.dumps(names, ensure_ascii=False, indent=2), encoding="utf-8")


def load_todos():
    """Free-standing TODO lists: [{"id", "name", "items": [{"id", "text", "done", "comment"}]}]."""
    if TODO_FILE.exists():
        return json.loads(TODO_FILE.read_text(encoding="utf-8"))
    return []


def save_todos(lists):
    TODO_FILE.write_text(json.dumps(lists, ensure_ascii=False, indent=2), encoding="utf-8")


def edit_todos(data):
    """Apply one change ("op") to the TODO lists. Returns the lists, or None if the request is invalid."""
    lists, op = load_todos(), data.get("op")
    text = lambda key: str(data.get(key, "")).strip()[:500]
    new_id = lambda: uuid.uuid4().hex[:8]

    if op == "createList":
        if not text("name"):
            return None
        lists.append({"id": new_id(), "name": text("name"), "items": []})
    elif op == "deleteList":
        lists = [l for l in lists if l["id"] != data.get("list")]
    else:
        todo = next((l for l in lists if l["id"] == data.get("list")), None)
        if not todo:
            return None
        if op == "renameList" and text("name"):
            todo["name"] = text("name")
        elif op == "addItem" and text("text"):
            todo["items"].append({"id": new_id(), "text": text("text"), "done": False, "comment": ""})
        elif op in ("updateItem", "deleteItem"):
            item = next((i for i in todo["items"] if i["id"] == data.get("item")), None)
            if not item:
                return None
            if op == "deleteItem":
                todo["items"].remove(item)
            else:
                if "done" in data:
                    item["done"] = bool(data["done"])
                if "comment" in data:
                    item["comment"] = str(data["comment"]).strip()[:2000]
                if "text" in data and text("text"):
                    item["text"] = text("text")
        else:
            return None

    save_todos(lists)
    return lists


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT / "static"), **kwargs)

    def send_json(self, data, status=200):
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        url = urlparse(self.path)
        if url.path == "/api/plan":
            self.send_json(load_plan())
        elif url.path == "/api/revolving":
            self.send_json(load_revolving())
        elif url.path == "/api/comments":
            date = parse_qs(url.query).get("date", [""])[0]
            self.send_json(load_comments().get(date, {}))
        elif url.path == "/api/names":
            self.send_json(load_names())
        elif url.path == "/api/plan/history":
            self.send_json(load_history())
        elif url.path == "/api/todo":
            self.send_json(load_todos())
        else:
            super().do_GET()

    def do_POST(self):
        length = int(self.headers.get("Content-Length", 0))
        data = json.loads(self.rfile.read(length) or b"{}")

        if self.path == "/api/comments":
            return self.save_comment(data)
        if self.path == "/api/names":
            return self.save_name(data)
        if self.path == "/api/todo":
            lists = edit_todos(data)
            return self.send_json(lists) if lists is not None else self.send_json({"error": "Ugyldig endring"}, 400)
        if self.path.startswith("/api/plan/"):
            return self.edit_plan(self.path.removeprefix("/api/plan/"), data)

        chores = load_revolving()
        if self.path in ("/api/revolving", "/api/revolving/update"):
            text = str(data.get("text", "")).strip()
            picked = data.get("seasons") or []
            seasons = [s for s in SEASONS if s in picked]
            try:
                times = max(1, min(52, int(data.get("timesPerYear", 4))))
            except (TypeError, ValueError):
                times = 4
            if not text or not seasons:
                return self.send_json({"error": "Ugyldig gjøremål"}, 400)
            fields = {"text": text, "timesPerYear": times, "seasons": seasons}

            if self.path == "/api/revolving":
                chores.append({"id": uuid.uuid4().hex[:8], **fields})
            else:  # keep the id, so the chore keeps its ticks and comments
                chore = next((c for c in chores if c["id"] == data.get("id")), None)
                if not chore:
                    return self.send_json({"error": "Fant ikke gjøremålet"}, 404)
                chore.update(fields)
        elif self.path == "/api/revolving/delete":
            chores = [c for c in chores if c["id"] != data.get("id")]
        else:
            return self.send_json({"error": "Ukjent adresse"}, 404)

        save_revolving(chores)
        self.send_json(chores)

    def save_comment(self, data):
        date, task_id = str(data.get("date", "")), str(data.get("taskId", ""))
        comment = str(data.get("comment", "")).strip()
        status = data.get("status") if data.get("status") in STATUSES else None
        if not date or not task_id:
            return self.send_json({"error": "Mangler dato eller gjøremål"}, 400)

        comments = load_comments()
        day = comments.setdefault(date, {})
        if comment or status:
            day[task_id] = {"comment": comment, "status": status, "task": str(data.get("task", ""))}
        else:
            day.pop(task_id, None)
            if not day:
                comments.pop(date)
        save_comments(comments)
        self.send_json(comments.get(date, {}))

    def edit_plan(self, action, data):
        if action == "edit":  # replace one section's rows
            key, rows = data.get("key"), data.get("rows")
            if not valid_key(key) or key == "*" or not isinstance(rows, list):
                return self.send_json({"error": "Ugyldig endring"}, 400)
            apply_edit(key, clean_rows(rows))
        elif action == "revert":  # put a section back to how it was before an edit
            entry = next((h for h in load_history() if h["id"] == data.get("id")), None)
            if not entry:
                return self.send_json({"error": "Fant ikke endringen"}, 404)
            apply_edit(entry["key"], entry["before"], kind="revert", note=entry["id"])
        elif action == "reset":  # back to the original CSV
            apply_edit("*", parse_csv(), kind="reset")
        else:
            return self.send_json({"error": "Ukjent adresse"}, 404)
        self.send_json({"plan": load_plan(), "history": load_history()})

    def save_name(self, data):
        date, shift = str(data.get("date", "")), data.get("shift")
        name = str(data.get("name", "")).strip()[:60]
        if not date or shift not in SHIFTS:
            return self.send_json({"error": "Mangler dato eller vakt"}, 400)

        names = load_names()
        day = names.setdefault(date, {})
        if name:
            day[shift] = name
        else:
            day.pop(shift, None)
            if not day:
                names.pop(date)
        save_names(names)
        self.send_json(names)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    url = f"http://localhost:{PORT}"
    print(f"Daglige gjøremål kjører på {url}  (Ctrl+C for å stoppe)")
    webbrowser.open(url)
    HTTPServer(("localhost", PORT), Handler).serve_forever()
