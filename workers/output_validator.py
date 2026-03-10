"""
workers/output_validator.py — Output validation and LLM-based page extraction.

OutputValidator: validates and coerces LLM output against a caller-supplied
schema (adapted from sdk/computeruse/validator.py for worker-side use).

OutputExtractor: extracts structured data from a browser page by sending
visible text and HTML to an LLM and validating the response.
"""

from __future__ import annotations

import json
import re
from typing import Any, Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------

class ValidationError(Exception):
    """Raised when output validation or extraction fails."""

    def __init__(self, message: str = "Output validation failed") -> None:
        self.message = message
        super().__init__(message)


# ---------------------------------------------------------------------------
# Module-level constants (mirrored from SDK validator)
# ---------------------------------------------------------------------------

_SCALAR_TYPES: frozenset[str] = frozenset(
    {"str", "int", "float", "bool", "list", "dict"}
)

_PARAMETERISED_RE = re.compile(r"^(list|dict)\[(.+)\]$", re.IGNORECASE)
_CODE_BLOCK_RE = re.compile(r"```(?:json)?\s*(\{.*?\})\s*```", re.DOTALL)
_BARE_OBJECT_RE = re.compile(r"\{.*\}", re.DOTALL)


# ---------------------------------------------------------------------------
# OutputValidator
# ---------------------------------------------------------------------------

class OutputValidator:
    """Validates and coerces LLM task output against a caller-supplied schema.

    Supported type strings: str, int, float, bool, list, dict,
    list[T], dict[str, T] (and nested combinations).
    """

    def validate(
        self, result: Dict[str, Any], schema: Dict[str, str]
    ) -> Dict[str, Any]:
        """Validate and coerce *result* against *schema*."""
        if not isinstance(result, dict):
            raise ValidationError(
                f"Expected a dict as task output, got {type(result).__name__!r}."
            )

        validated: Dict[str, Any] = dict(result)

        for field, type_str in schema.items():
            if field not in result:
                raise ValidationError(
                    f"Required field {field!r} is missing from the task output.\n"
                    f"  Expected schema : {self.format_schema(schema)}\n"
                    f"  Fields received : {list(result.keys()) or '(none)'}"
                )
            try:
                validated[field] = self.validate_type(result[field], type_str)
            except ValidationError:
                raise
            except Exception as exc:
                raise ValidationError(
                    f"Field {field!r}: unexpected error while validating "
                    f"value {result[field]!r} as {type_str!r}: {exc}"
                ) from exc

        return validated

    def parse_llm_json(self, text: str) -> Dict[str, Any]:
        """Extract and parse a JSON object from free-form LLM output."""
        if not text or not text.strip():
            raise ValueError("Cannot parse JSON from an empty string")

        code_match = _CODE_BLOCK_RE.search(text)
        if code_match:
            candidate = code_match.group(1)
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
            except json.JSONDecodeError:
                pass

        bare_match = _BARE_OBJECT_RE.search(text)
        if bare_match:
            candidate = bare_match.group(0)
            try:
                parsed = json.loads(candidate)
                if isinstance(parsed, dict):
                    return parsed
                raise ValueError(
                    f"JSON was parsed but is not an object "
                    f"(got {type(parsed).__name__!r})."
                )
            except json.JSONDecodeError as exc:
                raise ValueError(
                    f"Found a JSON-like substring but could not parse it: {exc}"
                ) from exc

        raise ValueError(
            "No JSON object found in the LLM response.\n"
            f"  Response preview: {text[:200]!r}"
        )

    def validate_type(self, value: Any, type_str: str) -> Any:
        """Coerce *value* to the type described by *type_str*."""
        outer, params = self._parse_type_string(type_str)

        if outer == "list" and params:
            return self._coerce_typed_list(value, item_type=params[0])
        if outer == "dict" and params:
            value_type = params[1] if len(params) == 2 else params[0]
            return self._coerce_typed_dict(value, value_type=value_type)

        target_map: dict[str, type] = {
            "str": str, "int": int, "float": float,
            "bool": bool, "list": list, "dict": dict,
        }
        target = target_map[outer]

        if isinstance(value, target):
            if target is int and isinstance(value, bool):
                raise ValidationError(
                    f"Cannot use bool {value!r} as int."
                )
            return value

        try:
            if target is bool:
                return _coerce_bool(value)
            if target is int:
                return _coerce_int(value)
            if target is float:
                return _coerce_float(value)
            if target is str:
                return str(value)
            if target is list:
                return _coerce_bare_list(value)
            if target is dict:
                return _coerce_bare_dict(value)
        except (ValueError, TypeError) as exc:
            raise ValidationError(
                f"Cannot convert {value!r} ({type(value).__name__}) "
                f"to {type_str!r}: {exc}"
            ) from exc

        raise ValidationError(f"Unhandled type {type_str!r}")

    def format_schema(self, schema: Dict[str, str]) -> str:
        """Format *schema* as a compact string for LLM prompts."""
        if not schema:
            return "(empty schema)"
        return ", ".join(
            f"{field}: {type_str}" for field, type_str in schema.items()
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _parse_type_string(
        self, type_str: str
    ) -> Tuple[str, Optional[List[str]]]:
        cleaned = type_str.strip().lower()
        if cleaned in _SCALAR_TYPES:
            return (cleaned, None)

        match = _PARAMETERISED_RE.match(cleaned)
        if not match:
            supported = ", ".join(sorted(_SCALAR_TYPES))
            raise ValidationError(
                f"Unknown type expression {type_str!r}.\n"
                f"  Supported bare types : {supported}\n"
                f"  Parameterised forms  : list[T], dict[str, T]"
            )

        outer = match.group(1)
        inner = match.group(2).strip()
        params = _split_top_level(inner)

        for param in params:
            self._parse_type_string(param)

        return (outer, params)

    def _coerce_typed_list(self, value: Any, item_type: str) -> List[Any]:
        raw = _coerce_bare_list(value)
        result: List[Any] = []
        for i, item in enumerate(raw):
            try:
                result.append(self.validate_type(item, item_type))
            except ValidationError as exc:
                raise ValidationError(
                    f"Element at index {i} of list[{item_type}] is invalid: {exc}"
                ) from exc
        return result

    def _coerce_typed_dict(
        self, value: Any, value_type: str
    ) -> Dict[str, Any]:
        raw = _coerce_bare_dict(value)
        result: Dict[str, Any] = {}
        for k, v in raw.items():
            try:
                result[k] = self.validate_type(v, value_type)
            except ValidationError as exc:
                raise ValidationError(
                    f"Value for key {k!r} in dict[str, {value_type}] "
                    f"is invalid: {exc}"
                ) from exc
        return result


# ---------------------------------------------------------------------------
# OutputExtractor
# ---------------------------------------------------------------------------

class OutputExtractor:
    """Extracts structured data from a browser page using LLM analysis."""

    def __init__(self, validator: Optional[OutputValidator] = None) -> None:
        self._validator = validator or OutputValidator()

    async def extract(
        self,
        page: Any,
        output_schema: Dict[str, str],
        llm_client: Any,
    ) -> Dict[str, Any]:
        """Extract data from *page* matching *output_schema*.

        1. Reads visible text (truncated to 8 K chars) and body HTML
           (truncated to 5 K chars) from the page.
        2. Sends an extraction prompt to the LLM.
        3. Parses the LLM JSON and validates against the schema.
        4. On validation failure, retries once with error feedback.
        5. Raises ``ValidationError`` if the retry also fails.
        """
        # Step 1 — Gather page content.
        visible_text = await page.evaluate(
            "() => document.body?.innerText?.substring(0, 8192) || ''"
        )
        zone_html = await page.evaluate(
            "() => document.body?.innerHTML?.substring(0, 5120) || ''"
        )

        schema_str = self._validator.format_schema(output_schema)

        # Step 2 — First extraction attempt.
        prompt = self._build_prompt(schema_str, visible_text, zone_html)
        raw_text = self._call_llm(llm_client, prompt)

        first_error_msg = ""
        try:
            parsed = self._validator.parse_llm_json(raw_text)
            return self._validator.validate(parsed, output_schema)
        except (ValidationError, ValueError) as first_err:
            first_error_msg = str(first_err)

        # Step 3 — Retry with error feedback.
        correction_prompt = (
            f"Your previous response failed validation: {first_error_msg}\n"
            f"Please try again. Return a JSON object matching: {schema_str}\n\n"
            f"--- PAGE TEXT ---\n{visible_text}\n"
        )
        retry_text = self._call_llm(llm_client, correction_prompt)

        try:
            parsed = self._validator.parse_llm_json(retry_text)
            return self._validator.validate(parsed, output_schema)
        except (ValidationError, ValueError) as second_err:
            raise ValidationError(
                f"Output extraction failed after retry: {second_err}"
            ) from second_err

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    @staticmethod
    def _build_prompt(
        schema_str: str, visible_text: str, zone_html: str
    ) -> str:
        return (
            "Extract the following data from the page content below.\n"
            f"Return a JSON object matching this schema: {schema_str}\n\n"
            f"--- PAGE TEXT ---\n{visible_text}\n\n"
            f"--- PAGE HTML ---\n{zone_html}\n"
        )

    @staticmethod
    def _call_llm(llm_client: Any, prompt: str) -> str:
        response = llm_client.messages.create(
            model="claude-sonnet-4-5-20250514",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw_text = ""
        for block in response.content:
            if getattr(block, "type", None) == "text":
                raw_text += getattr(block, "text", "")
        return raw_text


# ---------------------------------------------------------------------------
# Module-level coercion helpers
# ---------------------------------------------------------------------------

def _coerce_bool(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, int):
        if value in (0, 1):
            return bool(value)
        raise ValueError(
            f"Integer {value!r} is ambiguous as bool. Only 0 and 1 accepted."
        )
    if isinstance(value, str):
        lowered = value.strip().lower()
        if lowered in ("true", "1", "yes", "on"):
            return True
        if lowered in ("false", "0", "no", "off"):
            return False
        raise ValueError(f"String {value!r} is not a recognised boolean literal.")
    raise TypeError(f"Cannot convert {type(value).__name__!r} to bool.")


def _coerce_int(value: Any) -> int:
    if isinstance(value, bool):
        raise TypeError(f"Cannot use bool {value!r} as int.")
    if isinstance(value, float):
        if not value.is_integer():
            raise ValueError(
                f"Cannot losslessly convert {value!r} to int."
            )
        return int(value)
    return int(value)


def _coerce_float(value: Any) -> float:
    if isinstance(value, bool):
        raise TypeError(f"Cannot use bool {value!r} as float.")
    return float(value)


def _coerce_bare_list(value: Any) -> list:
    if isinstance(value, list):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, list):
                return parsed
        except json.JSONDecodeError:
            pass
        raise ValueError(f"String {value!r} cannot be parsed as a JSON array.")
    raise TypeError(
        f"Expected a list or JSON array string, got {type(value).__name__!r}."
    )


def _coerce_bare_dict(value: Any) -> dict:
    if isinstance(value, dict):
        return value
    if isinstance(value, str):
        try:
            parsed = json.loads(value)
            if isinstance(parsed, dict):
                return parsed
        except json.JSONDecodeError:
            pass
        raise ValueError(
            f"String {value!r} cannot be parsed as a JSON object."
        )
    raise TypeError(
        f"Expected a dict or JSON object string, got {type(value).__name__!r}."
    )


def _split_top_level(s: str) -> List[str]:
    """Split *s* on commas not inside square brackets."""
    parts: List[str] = []
    depth = 0
    current: List[str] = []
    for ch in s:
        if ch == "[":
            depth += 1
            current.append(ch)
        elif ch == "]":
            depth -= 1
            current.append(ch)
        elif ch == "," and depth == 0:
            parts.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        parts.append("".join(current).strip())
    return [p for p in parts if p]
