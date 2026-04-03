# B1: Foundation SDK Modules

## TODO Tracking

### Module 1: budget.py
- [x] Create `sdk/computeruse/budget.py`
  - [x] `BudgetExceededError` exception class
  - [x] `BudgetMonitor` dataclass (mutable, NOT frozen)
  - [x] `record_step_cost()` — uses `calculate_cost_cents`
  - [x] `record_cost_direct()`
  - [x] `total_cost_cents` property
  - [x] `spend_rate_cents_per_minute` property
  - [x] `projected_cost()`
  - [x] `check_anomaly()` — spend rate, threshold, spike detection (leave-one-out avg)

### Module 2: action_verifier.py
- [x] Create `sdk/computeruse/action_verifier.py`
  - [x] `VerificationResult` dataclass with `has_critical_failure` property
  - [x] `ActionVerifier` class
  - [x] `verify_action()` — orchestrates all checks
  - [x] `_check_url()` — regex match against current URL
  - [x] `_check_element()` — wait_for_selector with 3s timeout
  - [x] `_check_text()` — text in page content
  - [x] `_check_url_changed()` — navigate actions only
  - [x] `_check_form_value()` — input value verification
  - [x] `_safe_get_url()` — duck-typed URL access

### Module 3: step_enrichment.py
- [x] Create `sdk/computeruse/step_enrichment.py`
  - [x] `extract_selectors()` — 5 strategies (CSS, text, ARIA, testid, role)
  - [x] `extract_element_metadata()` — single eval_on_selector call
  - [x] `snapshot_dom_hash()` — SHA-256 of lightweight fingerprint
  - [x] `infer_expected_outcomes()` — URL pattern, dialog, title
  - [x] `infer_intent_from_step()` — pure Python heuristic
  - [x] `detect_parameterizable_values()` — email, phone, date, SSN, zip, URL
  - [x] `extract_desktop_selectors()` — UIA, name, window, coordinate strategies

### Tests
- [x] Create `sdk/tests/test_budget.py` (7 tests)
- [x] Create `sdk/tests/test_action_verifier.py` (9 tests)
- [x] Create `sdk/tests/test_step_enrichment.py` (7 tests)

### Verification
- [x] All 23 new tests pass
- [x] All 471 existing tests still pass (4 pre-existing failures unchanged)
- [x] Import check: `from computeruse.budget import BudgetMonitor; from computeruse.action_verifier import ActionVerifier`
