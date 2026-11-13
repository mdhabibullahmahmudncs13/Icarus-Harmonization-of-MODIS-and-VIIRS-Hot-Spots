"""The parameter file: ``config/params.yaml``.

The project documents this file as the single source of every tunable value,
and the hash of the file as the id that marks derived artifacts stale when a
value changes. This module is what makes that claim true: it reads the file
and hashes its bytes, so ``params_hash`` changes whenever the file changes.

Reading it needs no YAML library. The file is a flat two-level mapping of
scalars and simple lists, so a small parser covers it; adding PyYAML for this
one file would be a dependency for nothing.

The values themselves still live as constants in the modules that use them
(``harmonize.DEFAULT_CELL_KM``, ``calibrate.KAPPA``, ...). This module does not
re-export them or second-guess them; it is the file's identity, plus a reader
for anyone who wants to check the file against the code.
"""

from __future__ import annotations

import hashlib
import re
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]

#: The parameter file, at the path the docs name.
PARAMS_PATH = REPO_ROOT / "config" / "params.yaml"

#: ``key: value`` at the top level of a section.
_SECTION_RE = re.compile(r"^(?P<key>[A-Za-z_][\w]*):\s*(?P<value>.*)$")


def params_file_hash(path: Path = PARAMS_PATH) -> str:
    """The hash of the parameter file's bytes.

    This is what changes when a tunable changes, so it is what goes into
    ``params_hash``: the same parameters always hash the same, and a changed
    parameter never does.
    """
    return hashlib.sha256(path.read_bytes()).hexdigest()[:12]


def _scalar(text: str) -> Any:
    """One YAML scalar or inline list, in the subset the file uses."""
    value = text.strip()
    if not value:
        return None
    if value.startswith("[") and value.endswith("]"):
        inner = value[1:-1].strip()
        if not inner:
            return []
        return [_scalar(part) for part in inner.split(",")]
    if value.lower() in {"true", "false"}:
        return value.lower() == "true"
    if value.lower() in {"null", "none", "~"}:
        return None
    try:
        return int(value)
    except ValueError:
        pass
    try:
        return float(value)
    except ValueError:
        return value


def load_params(path: Path = PARAMS_PATH) -> dict[str, dict[str, Any]]:
    """The parameter file as ``{section: {key: value}}``.

    Only the two-level shape the file actually uses is supported: a section
    header, then indented ``key: value`` lines. A comment after a value is
    ignored; a line the parser does not understand raises ``ValueError``
    rather than being silently dropped, because a parameter nobody read is
    the problem this module exists to fix.
    """
    sections: dict[str, dict[str, Any]] = {}
    current: str | None = None
    for number, raw in enumerate(path.read_text().splitlines(), start=1):
        line = raw.split("#", 1)[0].rstrip() if not raw.strip().startswith("#") else ""
        if not line.strip():
            continue
        if not raw[0].isspace():
            header = _SECTION_RE.match(line.strip())
            if header is None or header.group("value"):
                raise ValueError(f"{path}:{number}: cannot read {raw!r}")
            current = header.group("key")
            sections[current] = {}
            continue
        if current is None:
            raise ValueError(f"{path}:{number}: {raw!r} is indented but has no section")
        entry = _SECTION_RE.match(line.strip())
        if entry is None:
            raise ValueError(f"{path}:{number}: cannot read {raw!r}")
        sections[current][entry.group("key")] = _scalar(entry.group("value"))
    return sections


def param(path: Path, section: str, key: str, default: Any = None) -> Any:
    """One parameter's value, or ``default`` if the file does not set it."""
    return load_params(path).get(section, {}).get(key, default)


__all__ = ["PARAMS_PATH", "REPO_ROOT", "load_params", "param", "params_file_hash"]
