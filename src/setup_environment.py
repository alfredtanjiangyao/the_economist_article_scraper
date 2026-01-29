import subprocess
import sys
import os

# Step 1: Create virtual environment
venv_path = ".venv1"
if not os.path.exists(venv_path):
    subprocess.run([sys.executable, "-m", "venv", venv_path])
    print(f"Virtual environment created at {venv_path}")
else:
    print(f"Virtual environment already exists at {venv_path}")

# Step 2: Install dependencies
# Construct path to pip inside the venv
if sys.platform == "darwin":  # macOS
    pip_executable = os.path.join(venv_path, "bin", "pip")
else:  # Windows
    pip_executable = os.path.join(venv_path, "Scripts", "pip.exe")

subprocess.run([pip_executable, "install", "-r", "requirements.txt"])
print("Dependencies installed.")

# activate the venv1 manually in your terminal
# source .venv1/bin/activate