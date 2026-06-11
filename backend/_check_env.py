import subprocess, os, sys

# Check python3 location
r = subprocess.run(["which", "python3"], capture_output=True, text=True)
print(f"python3: {r.stdout.strip()}")

# Check psycopg2
try:
    import psycopg2
    print("psycopg2: OK")
except ImportError as e:
    print(f"psycopg2: MISSING ({e})")

# Find venvs
for d in ["/opt/data/home/housing-tracker/backend/venv", "/opt/data/home/housing-tracker/.venv"]:
    p = os.path.join(d, "bin", "python")
    if os.path.exists(p):
        print(f"Found venv: {p}")

# Check pip
for cmd in ["pip", "pip3"]:
    r = subprocess.run(["which", cmd], capture_output=True, text=True)
    if r.returncode == 0:
        print(f"{cmd}: {r.stdout.strip()}")
