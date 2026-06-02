import os

print("Searching D:\\ for SwayCanvas, HeroSection, hero-bg.jpg...")
found = []
for root, dirs, files in os.walk(r"d:\\"):
    # Prune directory tree to speed up and avoid loops/system folders
    dirs[:] = [d for d in dirs if d.lower() not in [
        "windows", "program files", "program files (x86)", "programdata",
        "node_modules", ".git", ".venv", ".pytest_cache", "appdata", "local settings",
        "system32", "microsoft", "package cache", "$recycle.bin", "$sysreset",
        "documents and settings", "recovery", "system volume information"
    ]]
    
    for file in files:
        if "swaycanvas" in file.lower() or "herosection" in file.lower() or "hero-bg" in file.lower():
            path = os.path.join(root, file)
            print("FOUND:", path)
            found.append(path)
            
    if len(found) > 100:
        break

print(f"Done. Found {len(found)} files.")
