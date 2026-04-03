# TODO-B3: Integration Tests — Explore-to-Replay Pipeline

## Tests

- [x] Test 1: Full pipeline — run JSON → compile → save → script → replay
- [x] Test 2: Post-action verification catches wrong URL
- [x] Test 3: Budget circuit breaker stops the agent via wrap() on_step_end
- [x] Test 4: Selector healing falls back to alternate in replay
- [x] Test 5: Enrichment graceful degradation in track()
- [x] Test 6: Parameter substitution through full pipeline (compile → replay → verify fill value)

## Acceptance Criteria

- [x] All 6 integration tests pass
- [x] All existing SDK tests still pass (4 pre-existing failures unrelated)
- [x] No import errors from any module
- [x] Works on fresh clone (no external deps)
