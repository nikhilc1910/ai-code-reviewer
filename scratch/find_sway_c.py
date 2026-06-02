import os

print("Searching for SwayCanvas on C:\\ drive...")
found = []
for root, dirs, files in os.walk(r"c:\\"):
    # Exclude system and large directories to make search fast and safe
    dirs[:] = [d for d in dirs if d not in [
        "Windows", "Program Files", "Program Files (x86)", "ProgramData",
        "node_modules", ".git", ".venv", "AppData", "Local", "Temp", "System32"
    ]]
    for file in files:
        if "SwayCanvas" in file or "HeroSection" in file:
            path = os.path.join(root, file)
            print(path)
            found.append(path)

print(f"Done. Found {len(found)} files.")
