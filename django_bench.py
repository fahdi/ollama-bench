"""Long Django + Docker task: model generates a full project, harness builds it with docker compose and hits the API."""
import json, os, re, shutil, subprocess, sys, time, urllib.error, urllib.request
from pathlib import Path

API = "http://localhost:11434/api"
HERE = Path(__file__).parent
PORT = 18080

SPEC = """You are building a complete, runnable Django project from scratch. Produce EVERY file needed; the result will be built and run with `docker compose up --build` with no human edits.

## Stack
- Python 3.12 (Docker image python:3.12-slim), Django 5.x, PostgreSQL 16 (image postgres:16-alpine), gunicorn, psycopg (v3, binary).
- No Django REST Framework. Use plain Django views returning JsonResponse and parsing JSON request bodies.

## Required files (exact paths)
- requirements.txt
- Dockerfile
- docker-compose.yml
- manage.py
- config/__init__.py, config/settings.py, config/urls.py, config/wsgi.py
- todo/__init__.py, todo/apps.py, todo/models.py, todo/views.py, todo/urls.py, todo/admin.py
- todo/migrations/__init__.py

## docker-compose.yml
- Service `db`: postgres:16-alpine, env POSTGRES_DB=todo, POSTGRES_USER=todo, POSTGRES_PASSWORD=todo, a healthcheck using pg_isready. Do NOT publish the db port to the host.
- Service `web`: built from the Dockerfile, depends on db being healthy, publishes "${WEB_PORT:-8000}:8000".
- web's command must run, in order: `python manage.py makemigrations todo`, `python manage.py migrate --noinput`, then gunicorn config.wsgi on 0.0.0.0:8000.
- web gets env vars POSTGRES_DB, POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_HOST=db, DJANGO_SECRET_KEY, DJANGO_DEBUG=0.

## settings.py
- Read DB settings and SECRET_KEY from those env vars. DEBUG from DJANGO_DEBUG. ALLOWED_HOSTS = ["*"].
- INSTALLED_APPS must include django.contrib.admin, auth, contenttypes, sessions, messages, staticfiles, and todo.

## Models (app `todo`)
- Project: name (CharField max 100, unique), created_at (auto_now_add).
- Task: project (FK to Project, related_name="tasks", on_delete CASCADE), title (CharField max 200, required, non-blank), done (bool, default False), priority (int 1..5 inclusive, default 3), due_date (DateField, nullable), created_at (auto_now_add).
- Register both in admin.

## JSON API (all under /api/, CSRF must not block these endpoints, all responses JSON)
1. GET /api/health/ -> 200 {"status": "ok", "db": true} (db true only if a DB query succeeds).
2. POST /api/projects/ body {"name": str} -> 201 {"id", "name", "task_count": 0}. Missing/blank name -> 400. Duplicate name -> 400. Body always returns {"error": str} on 400.
3. GET /api/projects/ -> 200 list of {"id", "name", "task_count"} ordered by name.
4. POST /api/projects/<id>/tasks/ body {"title", "priority"?, "due_date"? "YYYY-MM-DD"} -> 201 task object. Unknown project -> 404. Blank title, priority outside 1..5 or not an int, bad date -> 400 {"error"}. Invalid JSON body -> 400.
5. GET /api/projects/<id>/tasks/ -> 200 list of task objects ordered by priority DESC then id ASC. Optional query ?done=true or ?done=false filters. Unknown project -> 404.
6. PATCH /api/tasks/<id>/ body with any of {"title","done","priority","due_date"} -> 200 updated task object, same validation as create. Unknown task -> 404.
7. DELETE /api/tasks/<id>/ -> 204 empty body. Unknown task -> 404.
8. Wrong HTTP method on any endpoint -> 405.
- Task object shape: {"id", "project_id", "title", "done", "priority", "due_date" (string "YYYY-MM-DD" or null)}.

## Output format
For every file, output a line `### FILE: <path>` followed immediately by one fenced code block with the full file contents. No other prose between files. Do not omit or abbreviate any file."""


def chat(model, prompt, think=None):
    body = {"model": model, **({"think": think} if think is not None else {}), "stream": False, "keep_alive": "5m",
            "options": {"num_ctx": 32768, "temperature": 0, "num_predict": 16000},
            "messages": [{"role": "user", "content": prompt}]}
    req = urllib.request.Request(f"{API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"})
    t = time.time()
    with urllib.request.urlopen(req, timeout=3600) as r:
        out = json.loads(r.read())
    out["wall"] = time.time() - t
    return out


def extract(text, dest):
    # body ends at the first line that starts with ```, so empty blocks (```python\n```) parse correctly
    files = re.findall(r"###\s*FILE:\s*`?([^\s`]+)`?\s*\n+```[^\n]*\n(.*?)^```", text, re.S | re.M)
    for path, body in files:
        p = dest / path.strip().lstrip("./")
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body)
    return [f[0] for f in files]


def req(method, path, body=None):
    data = json.dumps(body).encode() if isinstance(body, (dict, list)) else (body.encode() if isinstance(body, str) else None)
    r = urllib.request.Request(f"http://localhost:{PORT}{path}", data=data, method=method,
                               headers={"Content-Type": "application/json"})
    try:
        with urllib.request.urlopen(r, timeout=15) as resp:
            raw = resp.read()
            return resp.status, (json.loads(raw) if raw else None)
    except urllib.error.HTTPError as e:
        raw = e.read()
        try:
            return e.code, json.loads(raw) if raw else None
        except Exception:
            return e.code, "<non-json>"
    except Exception as e:
        return None, str(e)[:80]


def checks():
    results = []
    def check(name, cond):
        results.append((name, bool(cond)))

    s, b = req("GET", "/api/health/")
    check("health 200 + db true", s == 200 and isinstance(b, dict) and b.get("db") is True)
    s, b = req("POST", "/api/projects/", {"name": "Beta"})
    check("create project 201", s == 201 and isinstance(b, dict) and b.get("name") == "Beta" and b.get("task_count") == 0)
    pid = b.get("id") if isinstance(b, dict) else None
    req("POST", "/api/projects/", {"name": "Alpha"})
    s, b = req("POST", "/api/projects/", {"name": "Beta"})
    check("duplicate project 400 + error", s == 400 and isinstance(b, dict) and "error" in b)
    s, b = req("POST", "/api/projects/", {"name": "  "})
    check("blank project name 400", s == 400)
    s, b = req("POST", "/api/projects/", "{not json")
    check("invalid JSON 400", s == 400)
    s, b = req("POST", f"/api/projects/{pid}/tasks/", {"title": "low", "priority": 1})
    t_low = b.get("id") if isinstance(b, dict) else None
    check("create task 201 + shape", s == 201 and isinstance(b, dict) and b.get("project_id") == pid and b.get("done") is False and b.get("due_date") is None)
    s, b = req("POST", f"/api/projects/{pid}/tasks/", {"title": "high", "priority": 5, "due_date": "2026-10-01"})
    t_high = b.get("id") if isinstance(b, dict) else None
    check("due_date round-trips", s == 201 and isinstance(b, dict) and b.get("due_date") == "2026-10-01")
    req("POST", f"/api/projects/{pid}/tasks/", {"title": "default"})
    s, _ = req("POST", f"/api/projects/{pid}/tasks/", {"title": "x", "priority": 9})
    check("priority out of range 400", s == 400)
    s, _ = req("POST", f"/api/projects/{pid}/tasks/", {"title": "x", "due_date": "2026-13-45"})
    check("bad date 400", s == 400)
    s, _ = req("POST", f"/api/projects/{pid}/tasks/", {"title": ""})
    check("blank title 400", s == 400)
    s, _ = req("POST", "/api/projects/99999/tasks/", {"title": "x"})
    check("task on missing project 404", s == 404)
    s, b = req("GET", f"/api/projects/{pid}/tasks/")
    check("list ordered priority desc", s == 200 and isinstance(b, list) and [t.get("title") for t in b] == ["high", "default", "low"])
    s, b = req("PATCH", f"/api/tasks/{t_high}/", {"done": True})
    check("patch done 200", s == 200 and isinstance(b, dict) and b.get("done") is True)
    s, b = req("GET", f"/api/projects/{pid}/tasks/?done=true")
    check("filter done=true", s == 200 and isinstance(b, list) and [t.get("title") for t in b] == ["high"])
    s, b = req("GET", f"/api/projects/{pid}/tasks/?done=false")
    check("filter done=false", s == 200 and isinstance(b, list) and len(b) == 2)
    s, b = req("GET", "/api/projects/")
    check("project list sorted + task_count", s == 200 and isinstance(b, list) and [p.get("name") for p in b] == ["Alpha", "Beta"] and b[1].get("task_count") == 3)
    s, _ = req("DELETE", f"/api/tasks/{t_low}/")
    check("delete 204", s == 204)
    s, _ = req("DELETE", f"/api/tasks/{t_low}/")
    check("delete missing 404", s == 404)
    s, _ = req("PUT", "/api/projects/", {"name": "x"})
    check("wrong method 405", s == 405)
    return results


def compose(proj, *args, timeout=900):
    env = {**os.environ, "WEB_PORT": str(PORT)}
    return subprocess.run(["docker", "compose", "-p", proj, *args], cwd=proj_dir(proj), env=env,
                          capture_output=True, text=True, timeout=timeout)


def proj_dir(proj):
    return HERE / "django_runs" / proj


def run(model, regrade=False, think=None):
    proj = "bench_" + re.sub(r"[^a-z0-9]", "", model.lower()) + ("_nothink" if think is False else "")
    d = proj_dir(proj)
    saved = (d / "_response.md").read_text() if regrade else None
    shutil.rmtree(d, ignore_errors=True)
    d.mkdir(parents=True)
    print(f"\n=== {model}{' (thinking off)' if think is False else ''} (Django + Docker task{', re-graded from saved reply' if regrade else ''}) ===", flush=True)
    if regrade:
        text = saved
    else:
        r = chat(model, SPEC, think)
        text = r["message"]["content"]
        tps = r["eval_count"] / (r["eval_duration"] / 1e9)
        print(f"generated {r['eval_count']} tokens in {r['wall']:.0f}s ({tps:.1f} tok/s), done_reason={r.get('done_reason')}", flush=True)
        # free model memory before docker builds
        urllib.request.urlopen(urllib.request.Request(f"{API}/generate", json.dumps({"model": model, "keep_alive": 0}).encode()))
    (d / "_response.md").write_text(text)
    files = extract(text, d)
    print(f"files written ({len(files)}): {', '.join(files)}", flush=True)

    b = compose(proj, "build")
    print(f"docker build: {'OK' if b.returncode == 0 else 'FAILED'}", flush=True)
    if b.returncode != 0:
        print("  " + "\n  ".join(b.stderr.strip().splitlines()[-8:]), flush=True)
        print("score: build failed (0 checks run)", flush=True)
        return
    compose(proj, "up", "-d")
    up = False
    for _ in range(60):
        s, _ = req("GET", "/api/health/")
        if s == 200:
            up = True
            break
        time.sleep(3)
    print(f"server up: {'yes' if up else 'NO (180s timeout)'}", flush=True)
    if not up:
        logs = compose(proj, "logs", "--tail", "25", "web").stdout
        print("  " + "\n  ".join(logs.strip().splitlines()[-15:]), flush=True)
    res = checks()
    for name, ok in res:
        print(f"  {'PASS' if ok else 'FAIL'}  {name}", flush=True)
    print(f"score: {sum(ok for _, ok in res)}/{len(res)}", flush=True)
    compose(proj, "down", "-v")


if __name__ == "__main__":
    # usage: django_bench.py MODEL [--regrade] [--nothink]
    args = sys.argv[1:]
    run(args[0], regrade="--regrade" in args, think=False if "--nothink" in args else None)
