from pathlib import Path
import shutil

def copy_dir(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Active model path not found: {src}")
    dst.mkdir(parents=True, exist_ok=True)
    if any(dst.iterdir()):
        return
    shutil.copytree(src, dst, dirs_exist_ok=True)
