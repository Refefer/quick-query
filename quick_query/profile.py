# -*- coding: utf-8 -*-
"""
Data model for a configuration *profile*.

The project's configuration file (a TOML file) contains a top‑level ``profile`` section
where each entry defines a named set of settings (model, credentials, tools, etc.).
This module defines a small, immutable dataclass that stores those settings.

The class purposefully does **not** perform any I/O – loading from the TOML file is
handled by helper functions in ``quick_query.config`` (see the upcoming
``read_profiles`` implementation).  Keeping the data class I/O‑free makes it easy
to instantiate programmatically and simplifies testing.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional


@dataclass(frozen=True)
class Profile:
    """Immutable representation of a single configuration profile.

    Attributes
    ----------
    name: str
        The identifier used in the TOML file (e.g. ``default``).
    model: Optional[str]
        Name of the model to use; may be ``None`` to let the server decide.
    credentials: Dict[str, Any]
        Dictionary of credential fields (e.g. ``host`` and ``api_key``) after
        the reference in the profile has been resolved.
    tools: Optional[List[str]]
        List of tool specifications defined for this profile.
    prompt_name: Optional[str]
        Optional name of a system‑prompt section associated with the profile.
    structured_streaming: Optional[bool]
        Whether the model should use structured streaming.  This mirrors the
        existing ``structured_streaming`` key that may appear in a profile.
    extra: Dict[str, Any]
        Catch‑all for any additional keys present in the TOML profile that
        are not explicitly modelled above.
    """

    name: str
    model: Optional[str] = None
    credentials: Dict[str, Any] = field(default_factory=dict)
    tools: Optional[List[str]] = None
    prompt_name: Optional[str] = None
    structured_streaming: Optional[bool] = None
    extra: Dict[str, Any] = field(default_factory=dict)

    def get_prompt_name(self) -> Optional[str]:
        """Return the associated system‑prompt name, if any."""
        return self.prompt_name

    def as_dict(self) -> Dict[str, Any]:
        """Convert the dataclass back to a plain ``dict``.  Useful for code that
        still expects the old dictionary structure.
        """
        base = {
            "model": self.model,
            "credentials": self.credentials,
            "tools": self.tools,
            "prompt": self.prompt_name,
            "structured_streaming": self.structured_streaming,
        }
        # Remove ``None`` values to keep the dict tidy.
        return {k: v for k, v in {**base, **self.extra}.items() if v is not None}

    # The class is frozen (immutable); if callers need a mutable copy they can
    # use ``dataclasses.replace`` or ``as_dict`` and construct a new instance.
