"""
Application-Side Structured Output Validator & Self-Healing Engine.
Strips fences, parses JSON, validates against Pydantic schema,
and on validation failure retries with errors fed back (max 3 attempts).
"""

from __future__ import annotations
import json
import re
from typing import Optional, Dict, Any, Tuple, Type
from pathlib import Path

from backend.ir.models import ProcessIR
from backend.llm.base import LLMProvider


def strip_markdown_fences(text: str) -> str:
    """Removes ```json or ``` code fences and trims whitespace."""
    if not text:
        return ""
    
    # Check for markdown code block
    match = re.search(r"```(?:json)?\s*([\s\S]*?)\s*```", text, re.IGNORECASE)
    if match:
        return match.group(1).strip()

    # If no fences, find boundary between first { and last }
    first_brace = text.find("{")
    last_brace = text.rfind("}")
    if first_brace != -1 and last_brace != -1 and last_brace > first_brace:
        return text[first_brace:last_brace + 1].strip()

    return text.strip()


def parse_and_validate_json(
    raw_text: str,
    target_cls: Type[ProcessIR] = ProcessIR
) -> Tuple[Optional[ProcessIR], Optional[str]]:
    """
    Attempts to parse text into JSON and validate against target Pydantic class.
    Returns (instance, error_message).
    """
    cleaned = strip_markdown_fences(raw_text)
    if not cleaned:
        return None, "Empty response received."

    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as jde:
        return None, f"JSON syntax error at line {jde.lineno}, col {jde.colno}: {jde.msg}"

    if not isinstance(data, dict):
        return None, f"Expected a JSON object, but got: {type(data).__name__}"

    try:
        instance = target_cls.from_dict(data)
        return instance, None
    except Exception as ex:
        return None, f"Schema validation error: {str(ex)}"


def extract_with_self_healing(
    provider: LLMProvider,
    prompt: str,
    prompts_dir: Path,
    system_message: str = "You are a senior BPMN 2.0 process architect.",
    max_attempts: int = 3,
    temperature: float = 0.1,
    max_tokens: int = 4096,
) -> Tuple[ProcessIR, Dict[str, Any]]:
    """
    Executes an extraction prompt with up to 3 retry attempts feeding validation errors back.
    """
    messages = [
        {"role": "system", "content": system_message},
        {"role": "user", "content": prompt}
    ]

    total_usage = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}
    last_raw_text = ""
    last_error = ""

    # Load repair template
    repair_template_path = prompts_dir / "repair_syntax.md"
    repair_template = ""
    if repair_template_path.exists():
        repair_template = repair_template_path.read_text(encoding="utf-8")

    for attempt in range(1, max_attempts + 1):
        parsed_json, raw_text, usage = provider.complete(
            messages=messages,
            temperature=temperature,
            max_tokens=max_tokens
        )
        last_raw_text = raw_text

        for k in total_usage:
            total_usage[k] += usage.get(k, 0)

        # Check for fatal transport / network errors
        if any(err_kw in raw_text for err_kw in ["Connection refused", "ConnectError", "NameResolutionError", "401 Unauthorized", "Could not resolve host"]):
            raise ConnectionError(f"LLM endpoint connection failed: {raw_text}")

        # Attempt parse and validation
        instance, error_msg = parse_and_validate_json(raw_text, ProcessIR)
        if instance is not None:
            return instance, total_usage

        last_error = error_msg or "Unknown validation error"
        print(f"[Process2BPMN] Extraction attempt {attempt}/{max_attempts} failed validation: {last_error}", file=sys.stderr)

        if attempt < max_attempts:
            # Build repair prompt using /prompts/repair_syntax.md
            if repair_template:
                repair_prompt = (
                    repair_template
                    .replace("{{VALIDATION_ERRORS}}", last_error)
                    .replace("{{INVALID_JSON}}", raw_text[:2000])
                )
            else:
                repair_prompt = (
                    f"The previous output was invalid:\n{last_error}\n\n"
                    f"Please correct the JSON according to the schema and return ONLY valid JSON."
                )

            # Append assistant response and new user prompt
            messages.append({"role": "assistant", "content": raw_text})
            messages.append({"role": "user", "content": repair_prompt})

    # If all attempts failed, raise with details
    raise ValueError(f"Failed to generate valid Process IR after {max_attempts} attempts. Last error: {last_error}\nResponse was:\n{last_raw_text[:500]}")
