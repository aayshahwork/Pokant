"""Unit tests for workers.output_validator (OutputValidator + OutputExtractor)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from workers.output_validator import OutputExtractor, OutputValidator, ValidationError


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def validator() -> OutputValidator:
    return OutputValidator()


@pytest.fixture
def extractor() -> OutputExtractor:
    return OutputExtractor()


# ---------------------------------------------------------------------------
# OutputValidator — type coercion
# ---------------------------------------------------------------------------

class TestValidateTypeCoercion:
    def test_str_passthrough(self, validator: OutputValidator) -> None:
        result = validator.validate({"name": "Alice"}, {"name": "str"})
        assert result == {"name": "Alice"}

    def test_str_to_int(self, validator: OutputValidator) -> None:
        result = validator.validate({"count": "42"}, {"count": "int"})
        assert result == {"count": 42}

    def test_str_to_float(self, validator: OutputValidator) -> None:
        result = validator.validate({"price": "9.99"}, {"price": "float"})
        assert result == {"price": 9.99}

    def test_str_to_bool_true(self, validator: OutputValidator) -> None:
        for truthy in ("true", "yes", "1", "on"):
            result = validator.validate({"flag": truthy}, {"flag": "bool"})
            assert result["flag"] is True, f"Expected True for {truthy!r}"

    def test_str_to_bool_false(self, validator: OutputValidator) -> None:
        for falsy in ("false", "no", "0", "off"):
            result = validator.validate({"flag": falsy}, {"flag": "bool"})
            assert result["flag"] is False, f"Expected False for {falsy!r}"

    def test_int_to_float(self, validator: OutputValidator) -> None:
        result = validator.validate({"val": 3}, {"val": "float"})
        assert result == {"val": 3.0}

    def test_float_to_int_lossless(self, validator: OutputValidator) -> None:
        result = validator.validate({"val": 5.0}, {"val": "int"})
        assert result == {"val": 5}

    def test_float_to_int_lossy_raises(self, validator: OutputValidator) -> None:
        with pytest.raises(ValidationError):
            validator.validate({"val": 3.7}, {"val": "int"})

    def test_list_passthrough(self, validator: OutputValidator) -> None:
        result = validator.validate({"items": [1, 2]}, {"items": "list"})
        assert result == {"items": [1, 2]}

    def test_dict_passthrough(self, validator: OutputValidator) -> None:
        result = validator.validate(
            {"meta": {"a": 1}}, {"meta": "dict"}
        )
        assert result == {"meta": {"a": 1}}

    def test_parameterised_list(self, validator: OutputValidator) -> None:
        result = validator.validate(
            {"scores": ["1", "2", "3"]}, {"scores": "list[int]"}
        )
        assert result == {"scores": [1, 2, 3]}

    def test_parameterised_dict(self, validator: OutputValidator) -> None:
        result = validator.validate(
            {"counts": {"a": "1", "b": "2"}}, {"counts": "dict[str, int]"}
        )
        assert result == {"counts": {"a": 1, "b": 2}}


# ---------------------------------------------------------------------------
# OutputValidator — missing keys & errors
# ---------------------------------------------------------------------------

class TestValidateErrors:
    def test_missing_field_raises(self, validator: OutputValidator) -> None:
        with pytest.raises(ValidationError, match="missing"):
            validator.validate({}, {"price": "float"})

    def test_non_dict_input_raises(self, validator: OutputValidator) -> None:
        with pytest.raises(ValidationError, match="dict"):
            validator.validate("not a dict", {"x": "str"})

    def test_unknown_type_raises(self, validator: OutputValidator) -> None:
        with pytest.raises(ValidationError, match="Unknown type"):
            validator.validate({"x": 1}, {"x": "imaginary_type"})

    def test_extra_keys_preserved(self, validator: OutputValidator) -> None:
        result = validator.validate(
            {"a": "1", "extra": "keep"}, {"a": "int"}
        )
        assert result == {"a": 1, "extra": "keep"}


# ---------------------------------------------------------------------------
# OutputValidator — parse_llm_json
# ---------------------------------------------------------------------------

class TestParseLlmJson:
    def test_plain_json(self, validator: OutputValidator) -> None:
        result = validator.parse_llm_json('{"price": 9.99}')
        assert result == {"price": 9.99}

    def test_markdown_fenced(self, validator: OutputValidator) -> None:
        text = '```json\n{"status": "ok"}\n```'
        result = validator.parse_llm_json(text)
        assert result == {"status": "ok"}

    def test_embedded_in_prose(self, validator: OutputValidator) -> None:
        text = 'Here is the result: {"score": 42}'
        result = validator.parse_llm_json(text)
        assert result == {"score": 42}

    def test_empty_string_raises(self, validator: OutputValidator) -> None:
        with pytest.raises(ValueError, match="empty"):
            validator.parse_llm_json("")

    def test_no_json_raises(self, validator: OutputValidator) -> None:
        with pytest.raises(ValueError, match="No JSON"):
            validator.parse_llm_json("no json here at all")


# ---------------------------------------------------------------------------
# OutputValidator — format_schema
# ---------------------------------------------------------------------------

class TestFormatSchema:
    def test_empty_schema(self, validator: OutputValidator) -> None:
        assert validator.format_schema({}) == "(empty schema)"

    def test_normal_schema(self, validator: OutputValidator) -> None:
        result = validator.format_schema({"price": "float", "name": "str"})
        assert "price: float" in result
        assert "name: str" in result


# ---------------------------------------------------------------------------
# OutputExtractor
# ---------------------------------------------------------------------------

def _make_llm_response(json_str: str) -> MagicMock:
    """Build a mock LLM response object containing *json_str* as text."""
    block = MagicMock()
    block.type = "text"
    block.text = json_str
    response = MagicMock()
    response.content = [block]
    return response


def _make_page(
    visible_text: str = "Product: Widget\nPrice: $9.99",
    zone_html: str = "<div>Price: $9.99</div>",
) -> AsyncMock:
    page = AsyncMock()
    page.evaluate = AsyncMock(side_effect=[visible_text, zone_html])
    return page


class TestOutputExtractor:
    @pytest.mark.asyncio
    async def test_extract_success(self, extractor: OutputExtractor) -> None:
        page = _make_page()
        llm_client = MagicMock()
        llm_client.messages.create.return_value = _make_llm_response(
            '{"product": "Widget", "price": 9.99}'
        )

        result = await extractor.extract(
            page,
            {"product": "str", "price": "float"},
            llm_client,
        )
        assert result == {"product": "Widget", "price": 9.99}

    @pytest.mark.asyncio
    async def test_extract_retries_on_validation_failure(
        self, extractor: OutputExtractor
    ) -> None:
        page = _make_page()
        llm_client = MagicMock()
        # First call returns wrong type; second call returns correct data.
        llm_client.messages.create.side_effect = [
            _make_llm_response('{"count": "not-a-number"}'),
            _make_llm_response('{"count": 42}'),
        ]

        result = await extractor.extract(
            page, {"count": "int"}, llm_client
        )
        assert result == {"count": 42}
        assert llm_client.messages.create.call_count == 2

    @pytest.mark.asyncio
    async def test_extract_raises_after_retry_exhausted(
        self, extractor: OutputExtractor
    ) -> None:
        page = _make_page()
        llm_client = MagicMock()
        llm_client.messages.create.return_value = _make_llm_response(
            '{"count": "still-bad"}'
        )

        with pytest.raises(ValidationError, match="failed after retry"):
            await extractor.extract(
                page, {"count": "int"}, llm_client
            )

    @pytest.mark.asyncio
    async def test_extract_with_empty_page(
        self, extractor: OutputExtractor
    ) -> None:
        page = _make_page(visible_text="", zone_html="")
        llm_client = MagicMock()
        llm_client.messages.create.return_value = _make_llm_response(
            '{"status": "empty"}'
        )

        result = await extractor.extract(
            page, {"status": "str"}, llm_client
        )
        assert result == {"status": "empty"}
        llm_client.messages.create.assert_called_once()

    @pytest.mark.asyncio
    async def test_extract_calls_llm_with_schema(
        self, extractor: OutputExtractor
    ) -> None:
        page = _make_page()
        llm_client = MagicMock()
        llm_client.messages.create.return_value = _make_llm_response(
            '{"name": "test"}'
        )

        await extractor.extract(page, {"name": "str"}, llm_client)

        call_args = llm_client.messages.create.call_args
        prompt = call_args.kwargs["messages"][0]["content"]
        assert "name: str" in prompt
