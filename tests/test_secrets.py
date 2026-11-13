"""No secret may reach a tracked file.

``config/params.yaml`` and the API keys live in ``.env``, which is gitignored
and read only from the working copy. This test holds that line: a credential
in a tracked file is in the repository, in every clone, and in the history
forever — and ``git rm`` does not remove it from the history.

The check looks at *config-shaped* assignments only — a name and a literal
value, the shape a credential takes in ``.env``, a YAML file or a CI config.
Python source is not scanned: ``token = load_token(environ)`` is code, not a
credential, and a scanner that flags it would be turned off.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]

#: A name that says the value is a credential. The match is not anchored to a
#: word boundary: ``FIRMS_MAP_KEY`` and ``EARTHDATA_TOKEN`` carry the secret
#: word after an underscore, and ``_`` is a word character, so ``\b`` would
#: never fire there.
SECRET_NAME = re.compile(
    r"(?i)(api[_-]?key|map[_-]?key|access[_-]?key|token|password|passwd|secret|credential)"
)

#: ``NAME=value`` or ``name: value``, at the start of a line.
ASSIGNMENT = re.compile(
    r"^\s*(?:export\s+)?(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*[=:]\s*(?P<value>.+?)\s*$"
)

#: A value that is not a credential: empty, a placeholder, or a reference to
#: the environment rather than a literal.
PLACEHOLDER = re.compile(
    r"(?i)^(?:|\{\{.*\}\}|<.*>|\$[A-Za-z_]\w*|none|null|changeme|your[_-]?.*|x{3,}|\.\.\.)$"
)

#: A literal credential: a quoted string, or a bare token with no spaces and
#: no code punctuation. ``"KEY"`` and ``eyJ0eXAi...`` qualify; ``load_token()``
#: and ``root / "secret.md"`` do not.
LITERAL = re.compile(r"""^(?:"[^"]*"|'[^']*'|[A-Za-z0-9+/_\-]{16,})$""")

#: Only these files can hold a credential in the first place.
SCANNED_SUFFIXES = {".yaml", ".yml", ".toml", ".ini", ".cfg", ".conf", ".env", ".example"}

#: Directories that are not the project's own code: vendored skills, build
#: output, third-party data. A secret there is someone else's to fix, and
#: failing this project's build over it helps nobody.
SKIP_DIRECTORIES = {".agents", ".venv", "node_modules", "dist", "build", ".git"}

#: Files that are allowed to name a credential: they are about credentials.
#: ``.env.example`` lists the keys to fill in; its values are empty.
ALLOWED = {".env.example"}


def tracked_files() -> list[Path]:
    """The files git tracks, from git itself.

    Git is the authority on what is committed; guessing from the filesystem
    would scan ``.env`` and the build directories as well.
    """
    result = subprocess.run(
        ["git", "ls-files", "-z"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=True,
    )
    return [REPO_ROOT / name for name in result.stdout.split("\0") if name]


def candidates() -> list[tuple[Path, str, str]]:
    """``(path, name, value)`` for every credential-looking literal."""
    found: list[tuple[Path, str, str]] = []
    for path in tracked_files():
        if SKIP_DIRECTORIES & set(path.parts):
            continue
        if path.suffix not in SCANNED_SUFFIXES and path.name != ".env":
            continue
        try:
            text = path.read_text(encoding="utf-8")
        except (UnicodeDecodeError, OSError):
            continue
        for number, line in enumerate(text.splitlines(), start=1):
            match = ASSIGNMENT.match(line)
            if match is None:
                continue
            name, value = match.group("name"), match.group("value")
            if not SECRET_NAME.search(name):
                continue
            if PLACEHOLDER.match(value):
                continue
            if not LITERAL.match(value):
                continue
            found.append((path, f"{name} (line {number})", value))
    return found


def test_no_tracked_file_carries_a_credential() -> None:
    """The whole point: a secret in a tracked file is a published secret."""
    offenders = [
        f"{path.relative_to(REPO_ROOT)}: {name} = {value}"
        for path, name, value in candidates()
        if str(path.relative_to(REPO_ROOT)) not in ALLOWED
    ]
    assert not offenders, "a credential is in a tracked file:\n" + "\n".join(offenders)


def test_the_scanner_would_catch_a_real_credential(tmp_path: Path, monkeypatch) -> None:
    """The scanner must actually catch the thing it is for.

    A guard that cannot fail is worse than no guard: it teaches the reader
    that the check passes, and the next secret goes in unnoticed.
    """
    fake = tmp_path / "config.yaml"
    fake.write_text("FIRMS_MAP_KEY: 7fc1e4d4c1a3dd941954bec9f2b36d30\n")
    monkeypatch.setattr(
        "tests.test_secrets.tracked_files",
        lambda: [fake],
    )
    found = candidates()
    assert found, "the scanner missed a real credential"
    assert "FIRMS_MAP_KEY" in found[0][1]


def test_the_scanner_ignores_code(tmp_path: Path, monkeypatch) -> None:
    """A scanner that flags ordinary code gets switched off."""
    fake = tmp_path / "module.py"
    fake.write_text("token = load_token(environ)\nmap_key: str = \"\"\n")
    monkeypatch.setattr(
        "tests.test_secrets.tracked_files",
        lambda: [fake],
    )
    assert candidates() == []


def test_the_env_file_is_not_tracked() -> None:
    """``.env`` holds the developer's keys; it must never be committed."""
    assert ".env" not in {str(path.relative_to(REPO_ROOT)) for path in tracked_files()}


def test_the_gitignore_covers_the_env_file() -> None:
    """The ignore rule is what keeps the keys out of the repository."""
    ignored = (REPO_ROOT / ".gitignore").read_text().splitlines()
    assert any(line.strip() == ".env" for line in ignored)


@pytest.mark.parametrize("name", ["FIRMS_MAP_KEY", "EARTHDATA_TOKEN", "NASA_API_KEY"])
def test_the_env_example_names_the_keys_without_their_values(name: str) -> None:
    """The template lists what to fill in; it never carries a value."""
    text = (REPO_ROOT / ".env.example").read_text()
    assert name in text
    for line in text.splitlines():
        stripped = line.strip().lstrip("#").strip()
        if stripped.startswith(f"{name}="):
            assert not stripped.split("=", 1)[1].strip(), f"{name} has a value in .env.example"
