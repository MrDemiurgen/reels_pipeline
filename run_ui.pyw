import os
import subprocess
import sys


def launch_from_venv() -> bool:
    base_dir = os.path.dirname(os.path.abspath(__file__))
    pythonw_path = os.path.join(base_dir, ".venv", "Scripts", "pythonw.exe")
    app_path = os.path.join(base_dir, "ui_app.py")
    if os.path.isfile(pythonw_path) and os.path.isfile(app_path):
        subprocess.Popen([pythonw_path, app_path], cwd=base_dir)
        return True
    return False


if __name__ == "__main__":
    if not launch_from_venv():
        sys.exit(1)
