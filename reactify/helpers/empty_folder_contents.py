import shutil
from pathlib import Path
from typing import List

def empty_folder_contents(folder_path: Path, exclude: List[str] = None):
    """
    Deletes all contents inside the given folder (files and subfolders),
    but keeps the folder itself. Allows excluding specific files or folders.

    :param folder_path: The folder to empty.
    :param exclude: List of file/folder names (not full paths) to exclude.
    """
    folder_path = Path(folder_path)
    exclude = set(exclude or [])

    if not folder_path.exists() or not folder_path.is_dir():
        return

    for item in folder_path.iterdir():
        if item.name in exclude:
            continue

        try:
            if item.is_file() or item.is_symlink():
                item.unlink()
            elif item.is_dir():
                shutil.rmtree(item)
        except Exception as e:
            print(f"Error removing {item}: {e}")
