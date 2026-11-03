"""Default repository paths used by sweep planning."""

import os
import subprocess
from pathlib import Path

LOCAL_MASTER_CONFIG = "configs/local-master.yaml"


class _MasterConfigs(list[str]):
    def present(self, directory: Path | None = None) -> list[str]:
        """Return these paths, without the local master config where its file is missing.

        Upstream's projects and revisions, and the projects its tests build, have no local master
        config. With ``directory``, the files are looked up by name there and returned under it.
        """
        paths = [directory / Path(path).name if directory else Path(path) for path in self]
        local = Path(LOCAL_MASTER_CONFIG).name
        return [str(path) for path in paths if path.name != local or path.is_file()]


MASTER_CONFIGS = _MasterConfigs([
    "configs/amd-master.yaml",
    "configs/nvidia-master.yaml",
    LOCAL_MASTER_CONFIG,
])  # fmt: skip
RUNNER_CONFIG = "configs/runners.yaml"


def repository_root() -> Path:
    """Return the project root from ``INFERENCEX_REPOSITORY_ROOT``, the source tree, or the working directory."""
    if root := os.environ.get("INFERENCEX_REPOSITORY_ROOT"):
        return project_root(Path(root))
    source_root = Path(__file__).resolve().parent.parent
    if (source_root / "configs").is_dir():
        return source_root
    return project_root(Path.cwd())


def project_root(checkout: Path) -> Path:
    """Locate the end-to-end project in a current or historical checkout."""
    nested = checkout / "inferencex-e2e"
    return nested if (nested / RUNNER_CONFIG).is_file() else checkout


def git_repository_root(cwd: Path | None = None) -> Path:
    """Return the root of the working Git checkout, independently of installed code."""
    return Path(
        subprocess.check_output(["git", "rev-parse", "--show-toplevel"], cwd=cwd, text=True).strip()
    ).resolve()


def git_path_at_ref(ref: str, path: str, *, cwd: Path | None = None) -> str:
    """Resolve a project file across the repository-layout migration."""
    requested = Path(path)
    if requested.is_absolute() or ".." in requested.parts:
        requested = requested if requested.is_absolute() else (cwd or Path.cwd()) / requested
        path = requested.resolve().relative_to(git_repository_root(cwd)).as_posix()
    else:
        path = requested.as_posix()
    relative = path.removeprefix("inferencex-e2e/")
    for candidate in (f"inferencex-e2e/{relative}", relative):
        result = subprocess.run(
            ["git", "cat-file", "-e", f"{ref}:{candidate}"],
            cwd=cwd,
            capture_output=True,
            check=False,
        )
        if result.returncode == 0:
            return candidate
    raise ValueError(f"Could not find {path!r} at {ref!r}")
