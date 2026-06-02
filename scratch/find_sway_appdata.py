import os

print("Searching for SwayCanvas inside AppData and hidden folders...")
found = []
for root, dirs, files in os.walk(r"c:\Users\Nikhil C"):
    # Target AppData, Local, Temp explicitly
    for file in files:
        if "SwayCanvas" in file or "HeroSection" in file:
            path = os.path.join(root, file)
            print(path)
            found.append(path)

print(f"Done. Found {len(found)} files.")
