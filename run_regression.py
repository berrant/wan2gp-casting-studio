"""Complete native release-candidate gate. Run with python run_regression.py (pytest and Chromium required)."""
import subprocess,sys,shutil
from pathlib import Path
root=Path(__file__).resolve().parent
if not shutil.which('chromium'):
    raise SystemExit('Release gate requires Chromium; browser tests must not be skipped.')
raise SystemExit(subprocess.call([sys.executable,'-m','pytest','-q','-rs','tests'],cwd=root))
