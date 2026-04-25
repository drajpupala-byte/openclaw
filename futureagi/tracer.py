"""Tracing helpers wrapping fi_instrumentation / OpenTelemetry."""

from __future__ import annotations

import functools
from contextlib import contextmanager
from dataclasses import dataclass
from typing import Any, Callable, Generator, Optional


@dataclass
class TracerHandle:
    """Thin wrapper around the fi_instrumentation trace provider."""
    provider: Any  # fi_instrumentation TraceProvider or SDK-specific type
    _fi_tracer: Any = None

    def get_tracer(self, name: str) -> Any:
        return self.provider.get_tracer(name)


def setup_tracing(
    project_name: str,
    project_type: str = "OBSERVE",
    api_key: str = "",
    secret_key: str = "",
) -> TracerHandle:
    """
    Register with Future AGI and return a TracerHandle.

    Falls back to a no-op tracer when fi_instrumentation is not installed,
    so the rest of the code works without requiring the package at import time.
    """
    try:
        from fi_instrumentation import register
        from fi_instrumentation.fi_types import ProjectType

        pt = getattr(ProjectType, project_type, ProjectType.OBSERVE)

        kwargs: dict[str, Any] = dict(
            project_type=pt,
            project_name=project_name,
        )
        if api_key:
            kwargs["fi_api_key"] = api_key
        if secret_key:
            kwargs["fi_secret_key"] = secret_key

        provider = register(**kwargs)
        return TracerHandle(provider=provider)

    except ImportError:
        return TracerHandle(provider=_NoOpProvider())


# ------------------------------------------------------------------ #
# Decorators & context managers for manual instrumentation
# ------------------------------------------------------------------ #

_active_handle: Optional[TracerHandle] = None


def _get_handle() -> Optional[TracerHandle]:
    return _active_handle


def traced(func: Optional[Callable] = None, *, name: Optional[str] = None):
    """
    Decorator that wraps a function in a FutureAGI trace span.

    Usage::

        @traced
        def my_agent(prompt: str) -> str: ...

        @traced(name="custom-span-name")
        def my_agent(prompt: str) -> str: ...
    """
    def decorator(fn: Callable) -> Callable:
        span_name = name or fn.__qualname__

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            handle = _get_handle()
            if handle and not isinstance(handle.provider, _NoOpProvider):
                try:
                    from fi_instrumentation import FITracer
                    tracer = FITracer(handle.provider.get_tracer(fn.__module__))

                    @tracer.chain
                    def _inner(*a, **kw):
                        return fn(*a, **kw)

                    return _inner(*args, **kwargs)
                except Exception:
                    pass
            return fn(*args, **kwargs)

        return wrapper

    if func is not None:
        return decorator(func)
    return decorator


@contextmanager
def span(name: str, attributes: Optional[dict] = None) -> Generator[Any, None, None]:
    """
    Context manager for a manual trace span.

    Usage::

        with span("retrieve-docs", {"query": q}) as s:
            docs = vector_store.search(q)
    """
    handle = _get_handle()
    if handle and not isinstance(handle.provider, _NoOpProvider):
        try:
            from fi_instrumentation import FITracer
            tracer = FITracer(handle.provider.get_tracer(__name__))
            with tracer.span(name=name) as s:
                if attributes:
                    for k, v in attributes.items():
                        s.set_attribute(k, v)
                yield s
            return
        except Exception:
            pass
    # No-op fallback
    yield None


# ------------------------------------------------------------------ #
# No-op provider for when fi_instrumentation is not installed
# ------------------------------------------------------------------ #

class _NoOpProvider:
    def get_tracer(self, *_, **__):
        return _NoOpTracer()


class _NoOpTracer:
    def start_as_current_span(self, *_, **__):
        from contextlib import nullcontext
        return nullcontext()
