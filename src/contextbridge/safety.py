"""Conservative path boundaries; no file-content secret scanning."""

import os
import re
from pathlib import (
    Path,
    PurePosixPath
)


class BridgeError(ValueError):
    """A user-facing validation or operational error."""


def sensitive(path: str) -> bool:
    """Suppress potentially sensitive names, including their parent folders."""
    parts = path.replace("\\", "/").lower().split("/")
    for part in parts:
        if part.startswith((".env", ".ssh", ".aws", ".azure", ".gnupg")):
            return True
        if part in {".git", ".npmrc", ".pypirc", ".netrc", "id_rsa",
                    "id_ed25519", "kubeconfig", ".kube"}:
            return True
        if re.search(r"secret|credential|password|token|private[-_]?key", part):
            return True
        if part.endswith((".pem", ".key", ".p12", ".pfx", ".keystore")):
            return True
    return False


def internal(path: str) -> bool:
    return ".contextbridge" in path.replace("\\", "/").split("/")


def valid_git_path(path: str) -> bool:
    p = PurePosixPath(path)
    return (bool(path) and not p.is_absolute() and ".." not in p.parts
            and not re.match(r"^[A-Za-z]:", path)
            and "\x00" not in path and not sensitive(path)
            and not internal(path))


def checked_path(path: Path) -> Path:
    """Reject symlink/junction ancestors before resolving a managed path."""
    path = Path(os.path.abspath(path))
    for item in (*reversed(path.parents), path):
        junction = getattr(item, "is_junction", lambda: False)()
        if item.is_symlink() or junction:
            raise BridgeError(
                "Linked paths are not allowed for this operation.")
        # Python 3.11 on Windows has no Path.is_junction().
        if os.name == "nt" and item.exists():
            if item.lstat().st_file_attributes & 0x400:
                raise BridgeError("Reparse points are not allowed.")
    return path


def read_text(path: Path, limit: int = 1_048_576) -> str:
    path = checked_path(path)
    if not path.is_file():
        raise BridgeError(
            "Requested JSON file does not exist or is not a file.")
    with path.open("rb") as stream:
        content = stream.read(limit + 1)
    if len(content) > limit:
        raise BridgeError("JSON input exceeds the 1 MiB size limit.")
    try:
        return content.decode("utf-8-sig")
    except UnicodeError as exc:
        raise BridgeError("JSON input must be UTF-8.") from exc
