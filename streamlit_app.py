import sys
from pathlib import Path

# Add project root to sys.path to ensure correct module resolution
root_path = Path(__file__).resolve().parent
if str(root_path) not in sys.path:
    sys.path.insert(0, str(root_path))

# Read and execute app.py in the global namespace on every rerun
app_path = root_path / "app.py"
with open(app_path, "r", encoding="utf-8") as f:
    code = f.read()

exec(code, globals())
