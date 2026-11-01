"""
Path utilities for py-wiki-crawler.
Handles path sanitization, Windows-safe filename normalization,
and relative path calculation between markdown files and assets.
"""

import os
import re
from pathlib import Path
from urllib.parse import unquote

# Reserved names in Windows (e.g. CON, PRN, AUX, NUL, COM1..9, LPT1..9)
WINDOWS_RESERVED_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}


def sanitize_path_segment(segment: str) -> str:
    """
    Sanitizes a single path segment for Windows, macOS, and Linux compatibility.
    Replaces illegal characters, avoids trailing spaces/dots, and handles reserved names.
    """
    segment = unquote(segment).strip()
    # Replace illegal filesystem characters: \ / : * ? " < > |
    clean = re.sub(r'[\\/*?:"<>|]', "_", segment)
    # Strip trailing periods and spaces (prohibited on Windows)
    clean = clean.rstrip(". ")

    if not clean:
        clean = "unbenannt"

    # Handle reserved names in Windows
    upper_base = clean.split(".")[0].upper()
    if upper_base in WINDOWS_RESERVED_NAMES:
        clean = f"_{clean}"

    # Truncate length if excessively long for filesystem
    if len(clean) > 150:
        clean = clean[:150].rstrip(". ")

    return clean


def title_to_relative_path(title: str) -> Path:
    """
    Converts a wiki article title (which may contain slashes like 'Weapons/Swords/Excalibur')
    into a relative Path object with '.md' extension.
    Example: 'Weapons/Swords/Excalibur' -> Path('Weapons/Swords/Excalibur.md')
    """
    segments = [s for s in title.split("/") if s.strip()]
    if not segments:
        segments = ["index"]

    sanitized_segments = [sanitize_path_segment(s) for s in segments]
    folder = Path(*sanitized_segments[:-1]) if len(sanitized_segments) > 1 else Path()
    filename = f"{sanitized_segments[-1]}.md"

    return folder / filename


def get_relative_link(from_file_path: Path, to_file_path: Path) -> str:
    """
    Calculates a relative POSIX link from one file to another.
    Both paths should be relative to the same root (e.g. export directory) or absolute.
    Example:
      from_file_path: output/Items/Weapons/Sword.md
      to_file_path:   output/assets/images/sword.png
      Returns:        ../../assets/images/sword.png
    """
    from_dir = from_file_path.parent
    try:
        rel_path = os.path.relpath(to_file_path, from_dir)
        return Path(rel_path).as_posix()
    except ValueError:
        # Fallback if different drives on Windows
        return to_file_path.as_posix()
