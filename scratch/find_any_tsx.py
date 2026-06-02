import os

print("Searching C:\\Users\\Nikhil C for any .tsx files...")
found = []
for root, dirs, files in os.walk(r"c:\Users\Nikhil C"):
    # Prune directory tree to speed up and avoid loops/system folders
    dirs[:] = [d for d in dirs if d.lower() not in [
        "node_modules", ".git", ".venv", ".pytest_cache", "appdata", "local settings",
        "system32", "microsoft", "package cache", "$recycle.bin", "$sysreset",
        "documents and settings", "recovery", "system volume information", "onedrive"
    ]]
    
    for file in files:
        if file.endswith(".tsx") or file.endswith(".ts") or "sway" in file.lower():
            path = os.path.join(root, file)
            print("FOUND:", path)
            found.append(path)
            
    if len(found) > 100:
        break

print(f"Done. Found {len(found)} files.")
