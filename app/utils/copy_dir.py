import shutil
from pathlib import Path


def copy_dir(src: Path, dst: Path) -> None:
    if not src.exists():
        raise FileNotFoundError(f"Active model path not found: {src}")
    
    dst.mkdir(parents=True, exist_ok=True)

    if any(dst.iterdir()):
        for item in dst.iterdir():
            if item.is_dir():
                shutil.rmtree(item) 
            else:
                item.unlink()

    shutil.copytree(src, dst, dirs_exist_ok=True)
