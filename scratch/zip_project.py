import os
import zipfile

def zip_project(output_filename, source_dir):
    exclude_dirs = {'.venv', '.git', '.pytest_cache', '__pycache__', '.antigravitycli'}
    exclude_files = {output_filename}
    
    count = 0
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        for root, dirs, files in os.walk(source_dir):
            # Modify dirs in-place to avoid traversing excluded directories
            dirs[:] = [d for d in dirs if d not in exclude_dirs]
            
            for file in files:
                if file in exclude_files:
                    continue
                # Skip temp/scratch python files if they are in the scratch folder
                file_path = os.path.join(root, file)
                rel_path = os.path.relpath(file_path, source_dir)
                
                # We can skip scratch folder completely or keep it. Let's skip scratch/ to make the submission clean
                if rel_path.startswith('scratch'):
                    continue
                    
                zipf.write(file_path, rel_path)
                count += 1
    print(f"Created {output_filename} containing {count} files.")

if __name__ == '__main__':
    workspace = r"c:\Users\Nikhil C\ai project"
    output_zip = os.path.join(workspace, "ai_code_reviewer_submission.zip")
    zip_project(output_zip, workspace)
