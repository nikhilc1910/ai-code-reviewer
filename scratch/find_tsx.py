import os

search_paths = [
    r"c:\Users\Nikhil C\OneDrive",
    r"c:\Users\Nikhil C\Desktop"
]

print("Searching for files...")
for base_path in search_paths:
    print(f"Searching in {base_path}...")
    if not os.path.exists(base_path):
        print(f"Path does not exist: {base_path}")
        continue
    
    count = 0
    for root, dirs, files in os.walk(base_path):
        if any(ignored in root for ignored in [".venv", "node_modules", ".git", ".pytest_cache", "AppData", "Local"]):
            continue
        
        for file in files:
            if "SwayCanvas" in file or "HeroSection" in file or file.endswith(".tsx"):
                print(os.path.join(root, file))
                count += 1
                if count > 100:
                    break
        if count > 100:
            break
    print(f"Finished searching {base_path}.")
