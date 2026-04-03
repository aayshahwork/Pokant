# A1: SDK Critical Bug Fixes

- [x] Discovery: read wrap.py _enrich_steps to find where tokens are extracted
- [x] Discovery: read browser_use source to find correct attribute paths for tokens in 0.12.x
- [x] Fix cost.py: update pricing constants if needed (check current Claude Sonnet/Haiku pricing)
- [x] Fix wrap.py _enrich_steps: find correct token attribute paths in browser_use 0.12.x AgentHistoryList
- [x] Fix wrap.py _enrich_steps: handle both old and new attribute paths with getattr fallbacks
- [x] Verify: mock agent with token metadata, assert cost_cents > 0 after enrichment
- [x] Add budget enforcement to wrap.py _on_step_end callback
- [x] In _on_step_end: extract tokens from latest step, accumulate cost, check against max_cost_cents
- [x] If budget exceeded: log warning, call agent.stop()
- [x] Add interrupt safety: wrap run() method body in try/finally
- [x] In finally block: save partial results (_save_run_metadata with status="interrupted")
- [x] Add SIGINT handler that sets a _interrupted flag checked in _on_step_end
- [x] Update _save_run_metadata to include enrichment fields when present (selectors, intent, etc. -- prepare for Phase 2)
- [x] All 452 existing tests still pass (486 passed, 4 pre-existing failures unrelated to changes)
