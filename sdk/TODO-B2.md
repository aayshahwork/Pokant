# TODO B2: WorkflowCompiler & ReplayExecutor

## Phase 1: Compiler Core (`compiler.py`)
- [x] Define CompiledStep, CompiledWorkflow dataclasses, CompilationError
- [x] Action-type mapping table + wait_after_ms defaults
- [x] compile_from_steps() — map fields, sort selectors, detect params, infer intent
- [x] compile_from_run() — load JSON, validate, delegate to compile_from_steps
- [x] save_workflow() — serialize to JSON
- [x] generate_playwright_script() — template with PARAMS, ast.parse() verification

## Phase 2: Selector Healer (`selector_healer.py`)
- [x] _convert_selector() — dict to Playwright selector string
- [x] heal() — try alternate selectors after primary fails
- [x] heal_with_text_search() — last-resort Playwright built-in locators

## Phase 3: Replay Executor (`replay_executor.py`)
- [x] ReplayConfig, ReplayResult, ReplayStepError dataclasses
- [x] _execute_step() — 4-tier cascade (Tier 0 direct, Tier 1 healer, Tier 2 AI, Tier 3 stub)
- [x] execute() — loop steps with BudgetMonitor + ActionVerifier (caller provides page)
- [x] execute_from_file() — load JSON, delegate to execute()

## Phase 4: Tests
- [x] test_compiler.py — 7 tests (all pass)
- [x] test_replay_executor.py — 7 tests (all pass)

## Phase 5: Verification
- [x] All existing tests still pass (23/23)
- [x] All new tests pass (14/14)
- [x] Import check passes
