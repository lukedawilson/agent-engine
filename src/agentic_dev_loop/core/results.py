"""Typed result value object.

Expected conditions are modelled as values, never exceptions (DDD rule):
callers decide routing based on the error code. `unwrap()` exists for
programming errors only - calling it on an error is a bug.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Generic, TypeVar

T = TypeVar("T")
E = TypeVar("E")


@dataclass(frozen=True)
class Result(Generic[T, E]):
    """Exactly one of `value` / `error` is meaningful; see factory methods."""

    value: T | None
    error: E | None

    @staticmethod
    def ok(value: T | None) -> "Result[T, E]":
        return Result(value=value, error=None)

    @staticmethod
    def err(error: E) -> "Result[T, E]":
        return Result(value=None, error=error)

    def is_ok(self) -> bool:
        return self.error is None

    def is_err(self) -> bool:
        return self.error is not None

    def unwrap(self) -> T:
        if self.error is not None:
            raise ValueError(f"unwrap called on an error Result: {self.error!r}")
        return self.value
