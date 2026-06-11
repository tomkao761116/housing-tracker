import subprocess, sys, os

# Find all python and pip executables
for root in ["/opt/hermes", "/opt/data/home/housing-tracker"]:
    for dirpath, dirnames, filenames in os.walk(root):
        if ".venv" in dirpath or "venv" in dirpath:
            for f in filenames:
                if f in ("python", "python3", "pip", "pip3"):
                    print(os.path.join(dirpath, f))
        # Also check bin dirs
        if dirpath.endswith("bin"):
            for f in filenames:
                if f.startswith(("python", "pip")):
                    print(os.path.join(dirpath, f))

# Check site-packages
print("\n--- site-packages ---")
for sp in subprocess.check_output([sys.executable, "-c", "import site; print(site.getsitepackages())"]).decode().strip().split():
    print(sp)
    try:
        for f in os.listdir(sp):
            if "psycopg" in f.lower():
                print(f"  FOUND: {f}")
    except:
        pass
