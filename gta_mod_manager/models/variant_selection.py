"""User choice between Add-On and Replace halves of a dual-variant package."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True, slots=True)
class VariantSelection:
    """Which halves of a dual Add-On / Replace package to install.

    For packages that only ship one half, both flags are treated as "install
    whatever is present" by the layout/plan builders.
    """

    addon: bool = False
    replace: bool = False

    @property
    def any_selected(self) -> bool:
        """Return whether at least one half is selected."""
        return self.addon or self.replace

    @classmethod
    def for_package(cls, *, has_addon: bool, has_replace: bool) -> VariantSelection:
        """Return the initial selection for a freshly analysed package.

        Dual packages start with nothing selected so the user must choose.
        Single-route packages install everything present.
        """
        if has_addon and has_replace:
            return cls(addon=False, replace=False)
        return cls(addon=True, replace=True)
