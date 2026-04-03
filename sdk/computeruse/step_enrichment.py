"""computeruse/step_enrichment.py — Rich step data capture.

Functions for extracting selectors, element metadata, DOM state,
and inferring intent from browser actions.  All async functions
accept ``page: Any`` (duck-typed) and never import Playwright.
"""

from __future__ import annotations

import hashlib
import re
from typing import Any
from urllib.parse import urlparse


# ---------------------------------------------------------------------------
# Async functions (require a page object)
# ---------------------------------------------------------------------------


async def extract_selectors(page: Any, selector: str) -> list[dict]:
    """Extract multiple selector strategies for the element matched by *selector*.

    Strategies attempted (each wrapped in try/except):
    1. Original CSS selector — confidence 0.9
    2. Text content — confidence 0.7
    3. ARIA label — confidence 0.8
    4. data-testid — confidence 0.85
    5. Role + name — confidence 0.75
    """
    results: list[dict] = []

    # Strategy 1: Original CSS selector (always present)
    results.append({"type": "css", "value": selector, "confidence": 0.9})

    # Strategy 2: Text content
    try:
        text = await page.eval_on_selector(selector, "el => el.innerText")
        if text and text.strip():
            results.append({"type": "text", "value": text.strip(), "confidence": 0.7})
    except Exception:
        pass

    # Strategy 3: ARIA label
    try:
        aria = await page.eval_on_selector(
            selector, "el => el.getAttribute('aria-label')"
        )
        if aria:
            results.append(
                {"type": "css", "value": f'[aria-label="{aria}"]', "confidence": 0.8}
            )
    except Exception:
        pass

    # Strategy 4: data-testid
    try:
        testid = await page.eval_on_selector(
            selector, "el => el.getAttribute('data-testid')"
        )
        if testid:
            results.append(
                {
                    "type": "css",
                    "value": f'[data-testid="{testid}"]',
                    "confidence": 0.85,
                }
            )
    except Exception:
        pass

    # Strategy 5: Role + name
    try:
        role_info = await page.eval_on_selector(
            selector,
            "el => ({role: el.getAttribute('role'), "
            "name: el.getAttribute('name') || el.innerText})",
        )
        if role_info and role_info.get("role"):
            name = role_info.get("name", "")
            results.append(
                {
                    "type": "role",
                    "value": f"role={role_info['role']}[name='{name}']",
                    "confidence": 0.75,
                }
            )
    except Exception:
        pass

    return results


async def extract_element_metadata(page: Any, selector: str) -> dict:
    """Extract metadata about the acted-on element.

    Uses a single ``page.eval_on_selector`` call to get all attributes.
    Returns empty dict on failure.
    """
    try:
        meta = await page.eval_on_selector(
            selector,
            "el => ({"
            "text: el.innerText || '', "
            "tag: el.tagName.toLowerCase(), "
            "role: el.getAttribute('role') || '', "
            "aria_label: el.getAttribute('aria-label') || '', "
            "placeholder: el.getAttribute('placeholder') || '', "
            "name: el.getAttribute('name') || '', "
            "type: el.getAttribute('type') || ''"
            "})",
        )
        return meta if meta else {}
    except Exception:
        return {}


async def snapshot_dom_hash(page: Any) -> str:
    """SHA-256 of a lightweight page state fingerprint.

    Captures URL + title + count of interactable elements + first 50
    element tags/texts.  NOT the full DOM — must complete in <200ms.
    """
    try:
        state = await page.evaluate(
            "() => {"
            "const els = Array.from(document.querySelectorAll("
            "'a, button, input, select, textarea, [role]'));"
            "const first50 = els.slice(0, 50).map("
            "el => el.tagName + ':' + (el.innerText || '').slice(0, 50));"
            "return {"
            "url: location.href,"
            "title: document.title,"
            "count: els.length,"
            "elements: first50"
            "};"
            "}"
        )
        parts = [
            str(state.get("url", "")),
            str(state.get("title", "")),
            str(state.get("count", 0)),
        ]
        parts.extend(state.get("elements", []))
        fingerprint = "|".join(parts)
        return hashlib.sha256(fingerprint.encode()).hexdigest()
    except Exception:
        return ""


async def infer_expected_outcomes(
    page: Any, action_type: str, pre_url: str
) -> dict:
    """After a successful action, capture what 'success' looks like.

    Logic:
    - If URL changed from pre_url: url_pattern = regex-escaped current URL
    - If action_type == "click" and [role="dialog"] appeared: expected_element
    - Capture current page title as expected_text
    """
    result: dict[str, str] = {
        "url_pattern": "",
        "expected_element": "",
        "expected_text": "",
    }
    try:
        current_url = page.url if hasattr(page, "url") else ""

        # URL changed → capture pattern
        if current_url and current_url != pre_url:
            result["url_pattern"] = re.escape(current_url)

        # Click + dialog appeared
        if action_type == "click":
            try:
                dialog = await page.wait_for_selector(
                    '[role="dialog"]', timeout=1000
                )
                if dialog:
                    result["expected_element"] = '[role="dialog"]'
            except Exception:
                pass

        # Capture page title
        try:
            title = await page.evaluate("() => document.title")
            if title:
                result["expected_text"] = title
        except Exception:
            pass
    except Exception:
        pass
    return result


# ---------------------------------------------------------------------------
# Pure Python functions (no page access, no async)
# ---------------------------------------------------------------------------


def infer_intent_from_step(
    action_type: str, element_meta: dict
) -> tuple[str, str]:
    """Pure heuristic intent inference — no LLM, no page access.

    Returns (intent, intent_detail).
    """
    text = element_meta.get("text", "").strip()
    tag = element_meta.get("tag", "")
    placeholder = element_meta.get("placeholder", "")
    role = element_meta.get("role", "")
    name = element_meta.get("name", "")

    if action_type == "click":
        label = text or name or role or "element"
        tag_label = tag or role or "element"
        intent = f"Click {label} {tag_label}"
        # Infer detail from common button patterns
        lower_label = label.lower()
        if any(kw in lower_label for kw in ("submit", "send", "save")):
            detail = "Submit the form"
        elif any(kw in lower_label for kw in ("next", "continue")):
            detail = "Proceed to next step"
        elif any(kw in lower_label for kw in ("login", "sign in", "log in")):
            detail = "Sign in to the account"
        else:
            detail = f"Click the {label} {tag_label}"
        return (intent, detail)

    if action_type in ("type", "fill"):
        field_name = placeholder or name or "field"
        return (f"Enter {field_name}", f"Fill {field_name} field")

    if action_type == "navigate":
        url = element_meta.get("url", "")
        if url:
            try:
                domain = urlparse(url).netloc or url
                return (f"Navigate to {domain}", f"Open {url}")
            except Exception:
                pass
        return ("Navigate to page", "Open page URL")

    if action_type == "select":
        option = text or "option"
        return (f"Select {option}", "Choose from dropdown")

    if action_type == "scroll":
        return ("Scroll page", "Scroll the page")

    if action_type == "wait":
        return ("Wait", "Wait for page or element")

    return (f"Perform {action_type}", f"Execute {action_type} action")


def detect_parameterizable_values(fill_value: str) -> str:
    """Detect if a fill value should be parameterized.

    Returns ``{{email}}`` for email-like values, ``{{phone}}`` for phone
    numbers, etc.  Returns the literal value if no pattern matches.
    """
    if not fill_value:
        return fill_value

    # Email pattern (contains @ with a dot after it)
    if "@" in fill_value and "." in fill_value.split("@")[-1]:
        return "{{email}}"

    # SSN pattern (XXX-XX-XXXX) — check before phone to avoid overlap
    if re.match(r"^\d{3}-\d{2}-\d{4}$", fill_value):
        return "{{ssn}}"

    # Date patterns (YYYY-MM-DD or MM/DD/YYYY)
    if re.match(r"^\d{4}-\d{2}-\d{2}$", fill_value) or re.match(
        r"^\d{2}/\d{2}/\d{4}$", fill_value
    ):
        return "{{date}}"

    # Phone pattern (10+ digits when non-digits stripped)
    digits = re.sub(r"\D", "", fill_value)
    if len(digits) >= 10:
        return "{{phone}}"

    # Zip code (exactly 5 digits)
    if re.match(r"^\d{5}$", fill_value):
        return "{{zip_code}}"

    # URL
    if re.match(r"^https?://", fill_value):
        return "{{url}}"

    return fill_value


def extract_desktop_selectors(
    window_title: str,
    control_type: str,
    control_name: str,
    coordinates: tuple,
) -> list[dict]:
    """Extract selector strategies for desktop elements.

    Pure Python — no page access needed.
    """
    results: list[dict] = []

    # UIA: control_type + control_name
    if control_type and control_name:
        results.append(
            {
                "type": "uia",
                "value": f"{control_type}:{control_name}",
                "confidence": 0.9,
            }
        )

    # Name-based
    if control_name:
        results.append(
            {"type": "name", "value": control_name, "confidence": 0.8}
        )

    # Window + control type
    if window_title and control_type:
        results.append(
            {
                "type": "window_control",
                "value": f"{window_title} > {control_type}",
                "confidence": 0.7,
            }
        )

    # Coordinate fallback
    if coordinates and len(coordinates) >= 2:
        results.append(
            {
                "type": "coordinate",
                "value": f"{coordinates[0]},{coordinates[1]}",
                "confidence": 0.5,
            }
        )

    return results
