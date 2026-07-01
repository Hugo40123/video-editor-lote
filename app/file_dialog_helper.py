"""Helper to open native OS file/folder dialogs.

This script is meant to be run as a subprocess to avoid conflicts
between tkinter's GUI event loop and FastAPI's async event loop.
"""

from __future__ import annotations

import sys


def select_folder() -> str:
    """Open native folder picker and return the selected path."""
    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.focus_force()
        folder = filedialog.askdirectory(title="Selecione uma pasta")
        root.destroy()
        return folder or ""
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return ""


def select_file(file_types: str = "*.jpg *.jpeg *.png *.bmp") -> str:
    """Open native file picker and return the selected path."""
    try:
        import tkinter
        from tkinter import filedialog

        root = tkinter.Tk()
        root.withdraw()
        root.attributes("-topmost", True)
        root.focus_force()
        file_path = filedialog.askopenfilename(
            title="Selecione um arquivo",
            filetypes=[("Arquivos", file_types), ("Todos", "*.*")],
        )
        root.destroy()
        return file_path or ""
    except Exception as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return ""


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Uso: python file_dialog_helper.py folder|file [file_types]", file=sys.stderr)
        sys.exit(1)

    mode = sys.argv[1]

    if mode == "folder":
        result = select_folder()
    elif mode == "file":
        file_types = sys.argv[2] if len(sys.argv) > 2 else "*.jpg *.jpeg *.png *.bmp"
        result = select_file(file_types)
    else:
        print(f"Modo desconhecido: {mode}", file=sys.stderr)
        sys.exit(1)

    # Print result as single line for the parent process to read
    print(result)
