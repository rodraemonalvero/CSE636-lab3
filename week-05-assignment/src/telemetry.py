from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path
from time import perf_counter
from typing import Iterator

from opentelemetry import trace
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import (
    ConsoleSpanExporter,
    SimpleSpanProcessor,
)


PROJECT_ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = PROJECT_ROOT / "output"
SPAN_FILE = OUTPUT_DIR / "spans_sample.json"

TRACER_NAME = "week5-rca-agent"
GENAI_SYSTEM = "anthropic"
MODEL_NAME = "claude-sonnet-simulated"


def configure_tracer() -> tuple[trace.Tracer, object]:
    """
    Configure OpenTelemetry to write spans directly to a JSON text file.

    SimpleSpanProcessor is used so each completed span is written immediately,
    which is reliable for a short-running command-line assignment.
    """

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    span_output = SPAN_FILE.open(
        "w",
        encoding="utf-8",
    )

    provider = TracerProvider()

    provider.add_span_processor(
        SimpleSpanProcessor(
            ConsoleSpanExporter(
                out=span_output,
            )
        )
    )

    trace.set_tracer_provider(provider)

    tracer = trace.get_tracer(TRACER_NAME)

    return tracer, span_output


def estimate_tokens(text: str) -> int:
    """
    Estimate token count using whitespace-separated words.

    This is a simulation for the assignment and avoids API usage.
    """

    return max(1, len(text.split()))


def estimate_cost(
    input_tokens: int,
    output_tokens: int,
    input_price_per_1k: float = 0.003,
    output_price_per_1k: float = 0.015,
) -> float:
    """Estimate inference cost from token counts."""

    input_cost = (
        input_tokens / 1000
    ) * input_price_per_1k

    output_cost = (
        output_tokens / 1000
    ) * output_price_per_1k

    return round(
        input_cost + output_cost,
        6,
    )


@contextmanager
def genai_span(
    tracer: trace.Tracer,
    span_name: str,
    input_text: str,
    model_name: str = MODEL_NAME,
) -> Iterator[dict]:
    """
    Create an OpenTelemetry GenAI span and expose a mutable result dictionary.

    The caller should set:
    - result["output_text"]
    - result["tool_count"]
    - result["status"]

    before leaving the context.
    """

    start_time = perf_counter()

    result = {
        "output_text": "",
        "tool_count": 0,
        "status": "ok",
    }

    with tracer.start_as_current_span(
        span_name
    ) as span:

        span.set_attribute(
            "gen_ai.system",
            GENAI_SYSTEM,
        )

        span.set_attribute(
            "gen_ai.request.model",
            model_name,
        )

        input_tokens = estimate_tokens(
            input_text
        )

        span.set_attribute(
            "gen_ai.usage.input_tokens",
            input_tokens,
        )

        try:
            yield result

        except Exception as exc:
            result["status"] = "error"

            span.record_exception(exc)

            span.set_attribute(
                "error.type",
                type(exc).__name__,
            )

            span.set_attribute(
                "error.message",
                str(exc),
            )

            raise

        finally:
            output_text = str(
                result.get(
                    "output_text",
                    "",
                )
            )

            output_tokens = estimate_tokens(
                output_text
            )

            latency_ms = (
                perf_counter() - start_time
            ) * 1000

            estimated_cost = estimate_cost(
                input_tokens=input_tokens,
                output_tokens=output_tokens,
            )

            span.set_attribute(
                "gen_ai.usage.output_tokens",
                output_tokens,
            )

            span.set_attribute(
                "gen_ai.response.model",
                model_name,
            )

            span.set_attribute(
                "agent.tool_count",
                int(
                    result.get(
                        "tool_count",
                        0,
                    )
                ),
            )

            span.set_attribute(
                "agent.status",
                str(
                    result.get(
                        "status",
                        "ok",
                    )
                ),
            )

            span.set_attribute(
                "latency_ms",
                round(
                    latency_ms,
                    2,
                ),
            )

            span.set_attribute(
                "estimated_cost_usd",
                estimated_cost,
            )


def close_telemetry(
    span_output: object,
) -> None:
    """Flush and close the span output file."""

    span_output.flush()
    span_output.close()


def main() -> None:
    """Run a small self-test for the telemetry module."""

    tracer, span_output = configure_tracer()

    test_input = (
        "Analyze application metrics and logs "
        "for a simulated database incident."
    )

    with genai_span(
        tracer=tracer,
        span_name="telemetry_self_test",
        input_text=test_input,
    ) as result:

        result["output_text"] = (
            "The test span completed successfully."
        )

        result["tool_count"] = 2

    close_telemetry(span_output)

    print("Telemetry self-test complete.")
    print(f"Span file: {SPAN_FILE}")
    print(
        "File size:",
        SPAN_FILE.stat().st_size,
        "bytes",
    )


if __name__ == "__main__":
    main()