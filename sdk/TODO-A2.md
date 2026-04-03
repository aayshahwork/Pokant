# TODO-A2: Integrate Person B's Modules into wrap.py and track.py

## Phase 1: TODO doc
- [x] Create sdk/TODO-A2.md

## Phase 2: Extend models.py
- [x] Append 17 enrichment fields to StepData (Pydantic)
- [x] Add CompiledStep and CompiledWorkflow dataclasses

## Phase 3: Update track.py
- [x] Add _safe_get_url() helper to TrackedPage
- [x] Extend _record_step with **kwargs
- [x] Enrich click() with selectors, metadata, intent, verification
- [x] Enrich fill() with selectors, metadata, intent, fill_value_template
- [x] Enrich type() with fill_value_template
- [x] Enrich goto() with pre/post URL, outcomes, verification
- [x] Enrich select_option/press with pre/post URL (via _tracked_action)
- [x] Keep _tracked_action for wait_for_selector (minimal enrichment)

## Phase 4: Update wrap.py
- [x] Replace inline budget enforcement with BudgetMonitor
- [x] Add second pass in _enrich_steps for intent from LLM reasoning
- [x] Add selector extraction from action objects
- [x] Update _serialize_step with new enrichment field names

## Phase 5: Update __init__.py exports
- [x] Add BudgetMonitor, BudgetExceededError
- [x] Add ActionVerifier, VerificationResult
- [x] Add extract_selectors, infer_intent_from_step
- [x] Comment placeholder for WorkflowCompiler (Person B Phase 2)

## Phase 6: Tests
- [x] test_track.py: verify enrichment fields on click/fill/goto steps
- [x] test_wrap.py: verify intent from next_goal, BudgetMonitor integration
- [x] 225 passed, 1 pre-existing failure (test_auto_generated_run_id_format)

## Notes
- Pre-existing test failure: TestRunIdGeneration expects 12-char hex ID but code uses UUID4 (36 chars)
- test_accumulated_cost_resets_on_retry renamed to test_budget_resets_on_retry (uses BudgetMonitor API)
