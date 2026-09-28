# ollama-bench

Full results and analysis: [RESULTS.md](RESULTS.md). Picking this up again: [HANDOFF.md](HANDOFF.md).

Local coding-model benchmarks for this Mac (M2 Max, 32 GB). Models tested: `gemma4:26b` (with `think: false`) and `qwen3-coder:30b`.

## Layout

- `bench.py`: speed at 8K/16K/32K/64K context plus 4 small verified Python tasks (`--nothink` turns gemma thinking off; replies saved to `bench_responses/`). Results in `bench.log`, `bench_gemma_nothink.log`.
- `django_bench.py`, `fix_turn.py`: one-shot Django 5 + Postgres project, built with docker compose and hit with 19 API checks. Results in `django.log`, `round2.log`, `django_qwen_regrade.log`; generated projects in `django_runs/`.
- `suite/`: real-world scenario suite (in progress).
  - `scenarios.py`: 8 code scenarios (Python, PHP/WordPress, TypeScript, Rust) with hidden checks, plus SQL, bash, tool-calling, long-context and code-review specs.
  - `run_suite.py`: runs each code scenario three ways (one-shot, tests-first prompt, real TDD loop) and grades with the hidden checks.
  - `ref/`: reference solutions. `validate_graders.py` proves every grader scores them 100% and scores wrong answers low (output: `grader_validation.log`).
  - `package.json`: pins TypeScript for grading; run `npm install` in `suite/` after cloning.
  - `results.jsonl`: one line per finished run. `runs/`: generated code and transcripts.

## Resume the suite

The run was stopped on 2026-09-28 at 05:29 PKT with 8 gemma runs done (nginx, async fetcher, 2 of 3 invoice arms). Rerunning starts from scratch and appends to `results.jsonl`, so clear it first for a clean run:

```
cd suite && rm -f results.jsonl && python3 run_suite.py gemma4:26b qwen3-coder:30b
```

Single scenarios: `python3 run_suite.py gemma4:26b --only=php_wp_query,rust_semver`.

Note: model-generated code runs directly on the host (not sandboxed), inside `suite/runs/`.

## Notes

- GPU memory limit was raised with `sudo sysctl iogpu.wired_limit_mb=26624`; it resets on reboot.
- gemma4 with thinking on can spend its whole output budget reasoning and emit no code; always pass `think: false` (CLI: `--think=false`).
