"""Read commits and files from a git repository, without a working checkout.

The source is a bare clone, so any commit on any branch can be read by SHA.
"""

from __future__ import annotations

import hashlib
import shutil
import subprocess
import tempfile

DASH_SKOGAI_URL = "https://github.com/skogai2/dash-skogai"


class SourceError(Exception):
    pass


def blob_sha(data: bytes) -> str:
    """The git blob SHA of data. The same value `git hash-object` prints."""
    h = hashlib.sha1(b"blob %d\0" % len(data))
    h.update(data)
    return h.hexdigest()


class GitSource:
    def __init__(self, url: str):
        self.url = url
        self._dir = tempfile.mkdtemp(prefix="skogai-src-")
        proc = subprocess.run(
            ["git", "clone", "--bare", "--quiet", url, self._dir],
            capture_output=True,
        )
        if proc.returncode != 0:
            self.close()
            raise SourceError(f"cannot clone {url}: {_text(proc.stderr)}")

    def close(self) -> None:
        shutil.rmtree(self._dir, ignore_errors=True)

    def __enter__(self) -> "GitSource":
        return self

    def __exit__(self, *exc) -> None:
        self.close()

    def _git(self, *args: str) -> bytes:
        proc = subprocess.run(["git", "-C", self._dir, *args], capture_output=True)
        if proc.returncode != 0:
            raise SourceError(f"git {args[0]}: {_text(proc.stderr) or 'failed'}")
        return proc.stdout

    def resolve(self, ref: str = "HEAD") -> str:
        """The full commit SHA that ref points to."""
        try:
            out = self._git("rev-parse", "--verify", "--quiet", f"{ref}^{{commit}}")
        except SourceError:
            raise SourceError(f"unknown ref '{ref}' in {self.url}") from None
        return out.decode().strip()

    def subject(self, sha: str) -> str:
        """The first line of the commit message at sha."""
        return self._git("log", "-1", "--format=%s", sha).decode().strip()

    def mode(self, sha: str, path: str) -> int:
        """The file mode at commit sha: 0o755 if executable, else 0o644."""
        out = self._git("ls-tree", sha, "--", path).decode()
        if not out:
            raise SourceError(f"{path} does not exist at {sha[:12]}")
        return 0o755 if out.split()[0] == "100755" else 0o644

    def read(self, sha: str, path: str) -> bytes:
        """The contents of path at commit sha."""
        try:
            return self._git("cat-file", "blob", f"{sha}:{path}")
        except SourceError:
            raise SourceError(f"{path} does not exist at {sha[:12]}") from None


def _text(data: bytes) -> str:
    return data.decode(errors="replace").strip()
