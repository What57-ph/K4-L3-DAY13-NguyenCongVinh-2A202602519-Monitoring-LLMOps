from __future__ import annotations

import os
from contextlib import contextmanager
from typing import Any

try:
    from langfuse import get_client, observe, propagate_attributes

    LANGFUSE_SDK_AVAILABLE = True
except ImportError:  # pragma: no cover - chỉ dùng khi chưa cài requirements
    LANGFUSE_SDK_AVAILABLE = False

    def observe(*args: Any, **kwargs: Any):
        def decorator(func):
            return func

        return decorator

    class _DummyClient:
        def update_current_span(self, **kwargs: Any) -> None:
            return None

        def update_current_generation(self, **kwargs: Any) -> None:
            return None

        def flush(self) -> None:
            return None

    def get_client():
        return _DummyClient()

    @contextmanager
    def propagate_attributes(**kwargs: Any):
        yield


def get_langfuse_client():
    return get_client()


class _NoopObservation:
    def update(self, **kwargs: Any) -> None:
        return None


@contextmanager
def start_as_current_observation(
    client: Any,
    *,
    enabled: bool,
    **kwargs: Any,
):
    """Create an active Langfuse v4 child, or safely no-op when disabled."""
    starter = getattr(client, "start_as_current_observation", None)
    if not enabled or not callable(starter):
        yield _NoopObservation()
        return

    with starter(**kwargs) as observation:
        yield observation


def flush_traces() -> None:
    if not tracing_enabled():
        return
    try:
        get_langfuse_client().flush()
    except Exception:  # pragma: no cover - telemetry must not break shutdown
        return


def tracing_enabled() -> bool:
    return LANGFUSE_SDK_AVAILABLE and bool(
        os.getenv("LANGFUSE_PUBLIC_KEY") and os.getenv("LANGFUSE_SECRET_KEY")
    )
