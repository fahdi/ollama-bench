"""Benchmark Ollama coding models: speed at several context sizes, GPU/CPU split, and correctness on small verified tasks."""
import json, re, subprocess, sys, time, urllib.request
from pathlib import Path

API = "http://localhost:11434/api"

def call(path, body=None):
    req = urllib.request.Request(f"{API}/{path}", data=json.dumps(body).encode() if body else None,
                                 headers={"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=1800) as r:
        return json.loads(r.read())

THINK = {"think": False} if "--nothink" in sys.argv else {}

def chat(model, prompt, num_ctx):
    t = time.time()
    r = call("chat", {"model": model, "stream": False, "keep_alive": "10m", **THINK,
                      "options": {"num_ctx": num_ctx, "temperature": 0},
                      "messages": [{"role": "user", "content": prompt}]})
    r["wall"] = time.time() - t
    return r

def processor(model):
    for m in call("ps").get("models", []):
        if m["name"].startswith(model):
            vram, size = m.get("size_vram", 0), m.get("size", 1)
            return f"{vram/size*100:.0f}% GPU, {size/1e9:.1f} GB loaded"
    return "not loaded"

def unload(model):
    call("generate", {"model": model, "keep_alive": 0})
    time.sleep(3)

TASKS = [
    ("parse_duration", """Write a Python function parse_duration(s: str) -> int that converts strings like "1h30m", "45s", "2h", "1h2m3s", "90m" into total seconds. Raise ValueError for empty strings, unknown units, or garbage like "abc" or "1x". Reply with only one ```python code block.""",
     """
assert parse_duration("1h30m")==5400; assert parse_duration("45s")==45; assert parse_duration("2h")==7200
assert parse_duration("1h2m3s")==3723; assert parse_duration("90m")==5400
for bad in ["", "abc", "1x", "h"]:
    try: parse_duration(bad); raise SystemExit(f"no error for {bad!r}")
    except ValueError: pass
"""),
    ("lru_cache", """Write a Python class LRUCache with __init__(self, capacity: int), get(self, key) returning -1 when missing, and put(self, key, value). Both operations must be O(1). Evicts the least recently used key when over capacity; get counts as a use. Reply with only one ```python code block.""",
     """
c=LRUCache(2); c.put(1,1); c.put(2,2); assert c.get(1)==1; c.put(3,3); assert c.get(2)==-1
c.put(4,4); assert c.get(1)==-1; assert c.get(3)==3; assert c.get(4)==4
c.put(3,33); assert c.get(3)==33
"""),
    ("fix_bug", """This Python function should merge overlapping intervals but has bugs. Return the fixed function named merge, reply with only one ```python code block.

def merge(intervals):
    out = []
    for s, e in intervals:
        if out and s < out[-1][1]:
            out[-1][1] = e
        else:
            out.append([s, e])
    return out
""",
     """
assert merge([[1,3],[2,6],[8,10],[15,18]])==[[1,6],[8,10],[15,18]]
assert merge([[1,4],[4,5]])==[[1,5]]
assert merge([[1,10],[2,3]])==[[1,10]]
assert merge([[8,10],[1,3],[2,6]])==[[1,6],[8,10]]
assert merge([])==[]
"""),
    ("topo_sort", """Write a Python function build_order(deps: dict[str, list[str]]) -> list[str] where deps maps each package to the packages it depends on. Return an order where every dependency comes before its dependents; packages only mentioned as dependencies must be included too. Raise ValueError if there is a cycle. Reply with only one ```python code block.""",
     """
o=build_order({"app":["lib","utils"],"lib":["utils"],"utils":[]})
assert o.index("utils")<o.index("lib")<o.index("app")
o=build_order({"a":["b"]}); assert set(o)=={"a","b"} and o.index("b")<o.index("a")
try: build_order({"a":["b"],"b":["a"]}); raise SystemExit("no cycle error")
except ValueError: pass
"""),
]

def run_task(code, test):
    m = re.search(r"```(?:python)?\n(.*?)```", code, re.S)
    src = (m.group(1) if m else code) + "\n" + test
    p = subprocess.run([sys.executable, "-c", src], capture_output=True, text=True, timeout=30)
    return p.returncode == 0, (p.stderr.strip().splitlines() or [""])[-1][:120]

SPEED_PROMPT = "Write a complete Python implementation of a thread-safe token bucket rate limiter class with docstrings and a short usage example."

def bench(model):
    print(f"\n=== {model} ===", flush=True)
    for ctx in (8192, 16384, 32768, 65536):
        unload(model)
        r = chat(model, SPEED_PROMPT, ctx)
        tps = r["eval_count"] / (r["eval_duration"] / 1e9)
        pps = r.get("prompt_eval_count", 0) / max(r.get("prompt_eval_duration", 1) / 1e9, 1e-9)
        print(f"ctx {ctx:>6}: {tps:5.1f} tok/s gen, {pps:6.1f} tok/s prompt, load {r.get('load_duration',0)/1e9:4.1f}s, {processor(model)}", flush=True)
    passed = 0
    for name, prompt, test in TASKS:
        r = chat(model, prompt, 16384)
        ok, err = run_task(r["message"]["content"], test)
        (Path(__file__).parent / "bench_responses").mkdir(exist_ok=True)
        (Path(__file__).parent / "bench_responses" / f"{model.replace(':', '_')}{'_nothink' if THINK else ''}_{name}.md").write_text(r["message"]["content"])
        passed += ok
        print(f"task {name:15} {'PASS' if ok else 'FAIL'} ({r['wall']:.1f}s){'' if ok else '  ' + err}", flush=True)
    print(f"score: {passed}/{len(TASKS)}", flush=True)
    unload(model)

# usage: bench.py MODEL [MODEL ...] [--nothink]
for m in [a for a in sys.argv[1:] if not a.startswith("--")]:
    bench(m)
