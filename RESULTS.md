# Results

All runs on 2026-09-28 (PKT, +0500). Temperature 0, one run per task unless noted.

## Machine

| | |
|---|---|
| Hardware | MacBook Pro, Apple M2 Max: 12-core CPU (8P + 4E), 38-core GPU, 32 GB unified memory |
| OS | macOS 26.6.2 (25G83) |
| Ollama | 0.34.4 |
| GPU memory limit | macOS default (~21 GB) at first, raised to 26624 MB with `sudo sysctl iogpu.wired_limit_mb=26624` at ~04:17 PKT. gemma's 8K/16K/32K speed runs happened before the raise; gemma 64K and every qwen run after it. |

## Models

| Model | Size on disk | Settings |
|---|---|---|
| `gemma4:26b` | 18 GB | tested with thinking on (default) and with `think: false` |
| `qwen3-coder:30b` | 18 GB (Q4, 30B-A3B mixture-of-experts) | no thinking mode |

## 1. Speed (`bench.py`, log: `bench.log`)

Same prompt at each context size, model reloaded each time. Generation tokens/sec as reported by Ollama.

| Context | gemma4:26b | qwen3-coder:30b |
|---|---|---|
| 8K | 79.6 tok/s, 100% GPU | 85.6 tok/s, 100% GPU (19.3 GB loaded) |
| 16K | 81.9 tok/s, 100% GPU | 81.1 tok/s, 100% GPU (20.1 GB) |
| 32K | 82.0 tok/s, 100% GPU | 86.4 tok/s, 100% GPU (21.8 GB) |
| 64K | 77.2 tok/s, 100% GPU | 66.4 tok/s (memory check returned "not loaded", likely partial CPU spill near the 26 GB limit) |

Caveats: Ollama 0.34.4 reports gemma4's loaded size as ~1.1 to 1.4 GB, which cannot be right for an 18 GB model, so only its GPU percentage is used. gemma's 40 s and 50 s load times were inflated by the qwen download running at the same time.

## 2. Small verified tasks (`bench.py`, logs: `bench.log`, `bench_gemma_nothink.log`)

4 tasks, graded by running hidden asserts: duration parser, LRU cache, fix a 3-bug interval merge, dependency sort with cycle detection.

| Model | Score | Notes |
|---|---|---|
| gemma4:26b, thinking on | 3/4 | dependency sort ran 337 s and returned no `build_order` (NameError). Consistent with spending the whole budget thinking; the reply was not saved (bench.py did not save replies then; it does now). |
| gemma4:26b, `think: false` | **4/4** | 2.5 to 35 s per task (the 35 s includes model load) |
| qwen3-coder:30b | **4/4** | first task took 483 s, the rest 3 to 4 s. Unexplained; likely memory pressure right after the 64K load. |

## 3. Django + Docker one-shot (`django_bench.py`, `fix_turn.py`; logs: `django.log`, `django_qwen_regrade.log`, `round2.log`; code: `django_runs/`)

One prompt: a complete Django 5 + Postgres 16 project (15 files: Dockerfile, compose with db healthcheck, env-based settings, models, admin, plain-Django JSON API). The harness builds it with `docker compose`, waits for `/api/health/`, then makes 19 API checks from outside.

| Model | Result | Root cause (verified in code / traceback) |
|---|---|---|
| gemma4:26b, thinking on | 0/19 | 16000 tokens generated, empty visible reply (`django_runs/bench_gemma426b/_response.md` is 0 bytes). All output went to thinking. |
| qwen3-coder:30b, one-shot | 0/19 | `validators=[lambda x: 1 <= x <= 5]` on the model field: `makemigrations` crashes ("Cannot serialize function: lambda"), and the lambda would not validate anyway (Django validators must raise). |
| qwen3-coder:30b, after 1 repair turn (given the crash log) | 2/19 | fixed the lambda, then: two views registered on the same URL (`projects/` -> list and create; Django uses the first, so create is unreachable), and `models.Count` used in views.py without importing `models` (500 on list). |
| gemma4:26b, `think: false` | **15/19** | one bug repeated in two views: `JsonResponse(list)` without `safe=False`, so both list endpoints return 500. The ordering and filtering logic behind them is correct. |

## 4. Real-world scenario suite (`suite/`, PAUSED)

Question under test: does asking a model to work test-first (TDD) improve results? Each code scenario runs three ways, all graded by hidden checks the model never sees:

- **one-shot**: write the solution
- **tests-first prompt**: write tests then implementation in one reply, nothing executed
- **TDD loop**: tests + stub, harness runs them (red), model implements, harness runs the model's own tests, up to 3 fix rounds on real failure output

Grader validation (`suite/validate_graders.py`, log: `suite/grader_validation.log`): all 8 reference solutions score 100% (98/98 checks); a wrong invoice solution scores 3/13; a plausible wrong SQL query 2/7; long-context decoy answers 0/4.

Finished before the pause (`suite/results.jsonl`, code and transcripts in `suite/runs/`):

| gemma4:26b (`think: false`) | one-shot | tests-first prompt | TDD loop |
|---|---|---|---|
| nginx log triage (Python) | 11/11, 42 s, 779 tok | 11/11, 37 s, 2225 tok | 11/11, 51 s, 2550 tok (red first, green with 0 fix rounds) |
| async fetcher (Python) | 10/10, 11 s, 539 tok | 10/10, 23 s, 1287 tok | 10/10, 33 s, 1514 tok (red first, green with 0 fix rounds) |
| invoice refactor (Python) | 13/13, 10 s, 492 tok | 13/13, 27 s, 1539 tok | interrupted (folder `suite/runs/gemma4_26b/py_refactor_invoice/TDD_loop/` is incomplete, not graded) |

Not yet run: the rest of gemma (tz bugfix, PHP/WordPress, TypeScript, Rust, bank CSV, SQL, bash, tool calling, long context, code review) and all of qwen3-coder. So far TDD has cost 2 to 3x the time and tokens with no score difference, because one-shot was already perfect on these three.

## Harness bugs found and fixed (so they are not mistaken for model failures)

1. `django_bench.py` file extractor required a newline between the opening and closing fence, so an empty file (`config/__init__.py`) swallowed the next file. qwen's first Django run was wrongly scored as missing settings.py; after the fix its own lambda bug was the real cause. Fixed with a line-anchored closing fence.
2. The bank-CSV grader applied `.replace()` to only part of the hidden-test string (operator precedence), so a helper was undefined and a correct solution scored 8/9. Found by the reference-solution validation before any model ran; fixed.

## Conclusions so far

- Use **`gemma4:26b` with `think: false`** for coding on this machine. With thinking on it can burn its entire output budget and write nothing.
- `qwen3-coder:30b` is as fast but made three basic Django mistakes where gemma made one.
- Evidence is thin: one run per task and a single Django task. Treat this as a clear signal, not a verdict.
- The TDD question is still open; the harder scenarios in the suite are where an effect would show.
