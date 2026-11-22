"""Flujo de tres nodos (generar o reparar, parsear, validar) con presupuesto acotado."""
from __future__ import annotations

import time

from vera.adapters.base import LanguageAdapter
from vera.engines.base import ChatEngine, ChatOptions, EngineError
from vera.parsing import parse_model_output
from vera.prompts import OUTPUT_SCHEMA, generation_messages, repair_messages
from vera.types import Attempt, AuditOutcome, RunConfig, RunRecord

_FORMAT_DIAGNOSTIC = (
    "The previous response had an invalid or truncated format ({reason}). "
    'Return only one complete JSON object with the string fields "code" and "note".'
)


def _record(config: RunConfig, attempts: list[Attempt], stop_reason: str,
            audit: AuditOutcome | None = None, infra_error: str | None = None) -> RunRecord:
    return RunRecord(
        config=config,
        attempts=attempts,
        accepted=stop_reason == "accepted",
        stop_reason=stop_reason,  # type: ignore[arg-type]
        audit=audit,
        valid=stop_reason != "infra_failure",
        infra_error=infra_error,
    )


def run_workflow(config: RunConfig, engine: ChatEngine, adapter: LanguageAdapter) -> RunRecord:
    task = config.task
    options = ChatOptions(
        num_ctx=config.num_ctx,
        num_predict=config.num_predict,
        temperature=config.temperature,
        seed=config.seed,
        keep_alive=config.keep_alive,
    )
    attempts: list[Attempt] = []
    previous_code = ""
    diagnostic = ""

    for index in range(1 + config.condition.max_repairs):
        kind = "generate" if index == 0 else "repair"
        messages = (
            generation_messages(task) if index == 0
            else repair_messages(task, previous_code, diagnostic)
        )
        started = time.perf_counter()
        try:
            result = engine.chat(
                messages, model=config.model.name, options=options, json_schema=OUTPUT_SCHEMA
            )
        except EngineError as exc:
            return _record(config, attempts, "infra_failure",
                           infra_error=f"EngineError({exc.kind}): {exc}")

        parsed = parse_model_output(result.text)
        parse_ok = parsed.error is None and not result.truncated
        validation = None
        if parse_ok:
            assert parsed.code is not None
            validation = adapter.validate(task, parsed.code)

        attempts.append(Attempt(
            index=index,
            kind=kind,
            prompt=messages[-1]["content"],
            raw_response=result.text,
            parse_ok=parse_ok,
            parse_error=parsed.error,
            code=parsed.code,
            truncated=result.truncated,
            validation=validation,
            prompt_tokens=result.prompt_tokens,
            completion_tokens=result.completion_tokens,
            seconds=time.perf_counter() - started,
        ))

        if validation is None:
            reason = "truncated" if result.truncated else parsed.error
            diagnostic = _FORMAT_DIAGNOSTIC.format(reason=reason)
            previous_code = parsed.code or result.text
            continue
        if validation.infra_failure:
            return _record(config, attempts, "infra_failure",
                           infra_error=f"validation: {validation.diagnostic[:500]}")
        if validation.passed:
            assert parsed.code is not None
            return _record(config, attempts, "accepted", adapter.audit(task, parsed.code))
        diagnostic = validation.diagnostic
        previous_code = parsed.code or ""

    return _record(config, attempts, "budget_exhausted")
