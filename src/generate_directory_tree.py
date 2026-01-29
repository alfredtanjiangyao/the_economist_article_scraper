import os
from typing import TextIO

EXCLUDE_NAMES = {"__pycache__"}

def _should_exclude(name: str) -> bool:
    """
    Check whether a name should be excluded from the directory tree.

    This excludes:
      - Hidden files or folders (names starting with ".")
      - Specific unwanted folders/files listed in EXCLUDE_NAMES

    Args:
        name (str): File or directory name.

    Returns:
        bool: True if the name should be excluded, False otherwise.
    """
    return name.startswith(".") or name in EXCLUDE_NAMES

def generate_tree(start_path: str, output_file: TextIO, prefix: str = "") -> None:
    """
    Recursively generate a directory tree structure and write it to a file.

    Hidden files/folders (names starting with ".") and unwanted folders/files are excluded.
    The "data" folder is displayed using a mocked structure instead of its real contents.

    Args:
        start_path (str): Root directory path to start generating the tree from.
        output_file (TextIO): Open file object where the tree structure will be written.
        prefix (str, optional): Prefix used for indentation and tree formatting.
            Defaults to "".

    Returns:
        None
    """
    items = sorted([i for i in os.listdir(start_path) if not _should_exclude(i)])
    items_count = len(items)

    for index, name in enumerate(items):
        path = os.path.join(start_path, name)
        connector = "└─ " if index == items_count - 1 else "├─ "

        # Mock the "data" folder structure
        if name == "data" and os.path.isdir(path):
            output_file.write(f"{prefix}{connector}data/\n")
            extension = "   " if index == items_count - 1 else "│  "
            output_file.write(f"{prefix}{extension}└─ {{article_title}}/\n")
            output_file.write(f"{prefix}{extension}   └─ {{article_title}}.json\n")
            continue

        output_file.write(f"{prefix}{connector}{name}\n")

        if os.path.isdir(path):
            extension = "   " if index == items_count - 1 else "│  "
            generate_tree(path, output_file, prefix + extension)

if __name__ == "__main__":
    project_root = "."
    output_path = "directory_tree.txt"

    with open(output_path, "w", encoding="utf-8") as f:
        f.write(f"{os.path.basename(os.path.abspath(project_root))}/\n")
        generate_tree(project_root, f)

    print(f"[SUCCESS] Directory tree saved to {output_path}")
