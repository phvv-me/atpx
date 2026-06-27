"""Pydantic v2 base models for atpx.

The house bases live in :mod:`patos`; atpx re-exports the mutable value object and the immutable
certificate/record base it uses, so call sites import them from one place.
"""

from patos import FrozenModel, Model

__all__ = ["FrozenModel", "Model"]
