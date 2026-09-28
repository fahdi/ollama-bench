# Handoff

Paused 2026-09-28 05:29 PKT (00:29 UTC). Results so far are in [RESULTS.md](RESULTS.md); this file is how to pick the work back up.

## Where it stands

| Piece | State |
|---|---|
| Speed + small tasks (`bench.py`) | Done for both models |
| Django + Docker (`django_bench.py`, `fix_turn.py`) | Done: gemma (thinking off) 15/19, qwen 0/19, then 2/19 after one repair turn |
| Grader validation (`suite/validate_graders.py`) | Done, all graders valid |
| Scenario suite (`suite/run_suite.py`) | **Paused.** 8 of ~58 runs done (gemma: nginx and async in all 3 arms, invoice in 2). qwen not started. |

Current recommendation: `gemma4:26b` with `think: false`. The open question is whether TDD prompting helps; the finished runs show no difference yet because one-shot was already perfect on them.

## Resume checklist

1. **Ollama running** with both models present: `ollama list` shows `gemma4:26b` and `qwen3-coder:30b`.
2. **GPU memory limit** resets on reboot. Check with `sysctl iogpu.wired_limit_mb`; if it prints 0, run in a normal Terminal (it needs a password): `sudo sysctl iogpu.wired_limit_mb=26624`. Without it, qwen at 32K context spills to the CPU and runs slowly.
3. **TypeScript for grading**: `cd suite && npm install` (only needed on a fresh clone).
4. **Graders still valid**: `cd suite && python3 validate_graders.py` should end with `ALL GRADERS VALID`.
5. **Run**, clearing the partial results first:
   ```
   cd suite && rm -f results.jsonl && python3 run_suite.py gemma4:26b qwen3-coder:30b > suite.log 2>&1
   ```
   Expect roughly 40 to 60 minutes. Progress is one line per run in `suite.log`. To run a subset: `--only=php_wp_query,ts_cart_reducer`.
6. **Close heavy apps** first. Both models are 18 GB and the runner loads one at a time, but Docker Desktop, browsers and IDEs compete for the same 32 GB.

## After the run

1. Summarize `suite/results.jsonl` per model and arm: total checks passed, time and tokens. Key comparison: does the TDD loop beat one-shot on the harder scenarios (PHP, TypeScript, Rust, bank CSV)?
2. Spot-check every failure in `suite/runs/<model>/<scenario>/<arm>/` (`_hidden_output.txt`, `_transcript.json`) before blaming the model. Two harness bugs have already been caught this way (see RESULTS.md).
3. Update RESULTS.md section 4 and the conclusions, then commit and push.

## Known limitations to keep in mind

- One run per task at temperature 0. Consider 3 runs per task for the headline comparison.
- The TDD loop gets up to 4 model turns and one-shot gets 1, so compare time/tokens as well as scores.
- Model-generated code runs on the host, not in a sandbox, inside `suite/runs/`. The bash scenario only touches its fixture folder.
- Long-context prompt is ~20K tokens at a 32K window; qwen was near its memory limit at 64K.
- `run_suite.py` has no skip-completed option; a rerun redoes everything. Adding a `--skip-done` that reads `results.jsonl` would make resuming cheaper.

## Decisions still open

- Keep or delete `qwen3-coder:30b` (18 GB). It lost the Django test; the suite will give a broader picture before deciding.
- Whether to add `devstral-small-2` (15 GB, built for agentic tool use) as a third model. It was the runner-up in the original sizing and has not been tested.
