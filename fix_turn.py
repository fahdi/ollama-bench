"""One repair turn: send the model its own reply plus the container error, merge corrected files, rebuild, re-test."""
import json, re, sys, time, urllib.request
import django_bench as db

model, proj, err_file = sys.argv[1], sys.argv[2], sys.argv[3]
think = False if "--nothink" in sys.argv else None
d = db.proj_dir(proj)
first = (d / "_response.md").read_text()
err = open(err_file).read()[-4000:]
msg = ("The project was built and started with `docker compose up --build`. The web container crashed with this output:\n\n"
       f"```\n{err}\n```\n\nFix the cause. Output ONLY the files you change, each as `### FILE: <path>` followed by one fenced code block with the full file.")
body = {"model": model, "stream": False, "options": {"num_ctx": 32768, "temperature": 0, "num_predict": 16000},
        **({"think": think} if think is not None else {}),
        "messages": [{"role": "user", "content": db.SPEC}, {"role": "assistant", "content": first}, {"role": "user", "content": msg}]}
t = time.time()
r = json.loads(urllib.request.urlopen(urllib.request.Request(f"{db.API}/chat", json.dumps(body).encode(), {"Content-Type": "application/json"}), timeout=3600).read())
print(f"\n=== {model} repair turn: {r['eval_count']} tokens in {time.time()-t:.0f}s ===", flush=True)
(d / "_repair.md").write_text(r["message"]["content"])
urllib.request.urlopen(urllib.request.Request(f"{db.API}/generate", json.dumps({"model": model, "keep_alive": 0}).encode()))
changed = db.extract(r["message"]["content"], d)
print(f"files changed: {', '.join(changed) or 'NONE'}", flush=True)
b = db.compose(proj, "build")
print(f"docker build: {'OK' if b.returncode == 0 else 'FAILED'}", flush=True)
if b.returncode:
    print("\n".join(b.stderr.splitlines()[-8:])); sys.exit()
db.compose(proj, "up", "-d")
for _ in range(60):
    if db.req("GET", "/api/health/")[0] == 200: break
    time.sleep(3)
else:
    print("server up: NO"); print("\n".join(db.compose(proj, "logs", "--tail", "15", "web").stdout.splitlines()[-12:]))
res = db.checks()
for n, ok in res: print(f"  {'PASS' if ok else 'FAIL'}  {n}")
print(f"score after repair: {sum(ok for _, ok in res)}/{len(res)}", flush=True)
db.compose(proj, "down", "-v")
