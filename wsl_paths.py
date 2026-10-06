"""Path translation between WSL and the Windows binaries these tools drive.

ffmpeg, ffprobe and Live are Windows programs: they must receive `E:\\x`, never
`/mnt/e/x`, and never a `\\\\wsl.localhost\\...` path, which they fail to read or
read wrong.
"""
import os


def to_windows_path(path):
    """Translate /mnt/e/x into E:\\x. Any other path is returned absolute, unchanged."""
    real = os.path.abspath(path)
    if real.startswith("/mnt/") and len(real) > 6 and real[6] == "/":
        return real[5].upper() + ":" + real[6:].replace("/", "\\")
    return real


def is_on_windows_drive(path):
    """True when a Windows program can read this path."""
    windows = to_windows_path(path)
    return len(windows) >= 2 and windows[1] == ":"
