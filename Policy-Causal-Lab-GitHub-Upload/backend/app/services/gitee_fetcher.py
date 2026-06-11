from pathlib import Path
import subprocess

SUPPORTED = {".md", ".txt", ".pdf", ".docx", ".pptx"}


def sync_repo(repo_url: str, branch: str, target_dir: Path) -> list[Path]:
    target_dir.parent.mkdir(parents=True, exist_ok=True)
    if (target_dir / ".git").exists():
        subprocess.run(["git", "-C", str(target_dir), "pull", "--ff-only"], check=True, capture_output=True, text=True)
    else:
        subprocess.run(["git", "clone", "--depth", "1", "--branch", branch, repo_url, str(target_dir)], check=True, capture_output=True, text=True)
    return [path for path in target_dir.rglob("*") if path.is_file() and path.suffix.lower() in SUPPORTED]
