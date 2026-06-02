import os

search_paths = [
    r"c:\Users\Nikhil C\ai project",
    r"c:\Users\Nikhil C\ai project - Copy",
    r"c:\Users\Nikhil C\Documents",
    r"c:\Users\Nikhil C\Downloads",
    r"c:\Users\Nikhil C\Desktop",
    r"c:\Users\Nikhil C\source",
    r"c:\Users\Nikhil C"
]

print("Searching for SwayCanvas / HeroSection / hero-bg.jpg...")
found = []
for base_path in search_paths:
    print(f"Scanning {base_path}...")
    if not os.path.exists(base_path):
        continue
    
    # We walk and only search depth up to a reasonable level, or just walk normal folders
    for root, dirs, files in os.walk(base_path):
        # Prune dirs
        dirs[:] = [d for d in dirs if d not in [
            "node_modules", ".git", ".venv", ".pytest_cache", "AppData", "Local Settings", 
            "Windows", "Program Files", "Program Files (x86)", "ProgramData", "System32",
            "Atlassian", "Microsoft", "Package Cache"
        ]]
        
        for file in files:
            if "SwayCanvas" in file or "HeroSection" in file or "hero-bg" in file:
                path = os.path.join(root, file)
                print("FOUND:", path)
                found.append(path)
                
        # Limit to prevent runaway
        if len(found) > 100:
            break
    if len(found) > 100:
        break

print(f"Done. Found {len(found)} files.")
