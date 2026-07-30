"""A small ``Result`` type used at service boundaries.

Services return :class:`Result` instead of raising for *expected* failures
(a conflict, a rejected plan, a missing game). Unexpected failures still raise
:class:`~gta_mod_manager.core.exceptions.ModManagerError`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Generic, TypeVar

T = TypeVar("T")
U = TypeVar("U")


@dataclass(frozen=True, slots=True)
class Result(Generic[T]):
    """Outcome of an operation that may fail in an expected way.

    Attributes:
        value: The payload when the operation succeeded.
        error: Human readable failure description when it did not.
        code: Optional machine readable failure code.
        warnings: Non-fatal messages produced along the way.
    """

    value: T | None = None
    error: str | None = None
    code: str | None = None
    warnings: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_ok(self) -> bool:
        """Return ``True`` when the operation succeeded."""
        return self.error is None

    @property
    def is_error(self) -> bool:
        """Return ``True`` when the operation failed."""
        return self.error is not None

    def unwrap(self) -> T:
        """Return the payload or raise if the result is a failure.

        Raises:
            ValueError: If the result represents a failure.
        """
        if self.error is not None:
            raise ValueError(f"Cannot unwrap a failed Result: {self.error}")
        # ``None`` is a legitimate payload for Result[None]; cast is safe here.
        return self.value  # type: ignore[return-value]

    def unwrap_or(self, fallback: T) -> T:
        """Return the payload, or ``fallback`` when the result failed."""
        return self.value if self.is_ok and self.value is not None else fallback

    def map(self, transform: Callable[[T], U]) -> "Result[U]":
        """Apply ``transform`` to the payload when the result succeeded.

        The constructor is deliberately called unsubscripted: ``Result[U](...)``
        makes ``typing`` assign ``__orig_class__`` on the new instance, which a
        frozen ``slots=True`` dataclass rejects.
        """
        if self.is_error or self.value is None:
            return Result(error=self.error, code=self.code, warnings=self.warnings)
        return Result(value=transform(self.value), warnings=self.warnings)

    def with_warning(self, message: str) -> "Result[T]":
        """Return a copy of this result with an extra warning attached."""
        return Result(
            value=self.value,
            error=self.error,
            code=self.code,
            warnings=(*self.warnings, message),
        )

    @staticmethod
    def ok(value: T, *warnings: str) -> "Result[T]":
        """Build a successful result."""
        return Result(value=value, warnings=tuple(warnings))

    @staticmethod
    def fail(error: str, code: str | None = None, *warnings: str) -> "Result[T]":
        """Build a failed result."""
        return Result(error=error, code=code, warnings=tuple(warnings))
