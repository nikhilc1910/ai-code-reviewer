import sys
import os
import shutil

# Ensure workspace root is in sys.path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from ingestion import clone_repo
from parser import parse_file
from utils.chunker import make_chunks

def test_smoke():
    repo_url = "https://github.com/pypa/sampleproject"
    print(f"Cloning {repo_url}...")
    try:
        # Ingestion returns a plain list of files because clone_repo is aliased to ingest_repository,
        # but in the pipeline it handles both a list and a tuple. Let's handle it here too.
        res = clone_repo(repo_url)
        if isinstance(res, tuple):
            files, tmp_dir = res
        else:
            files = res
            tmp_dir = None
        
        print(f"Successfully ingested {len(files)} python/javascript files.")
        for f in files[:5]: # Print first 5 files
            ast = parse_file(f['content'])
            chunks = make_chunks(ast, f['content'])
            print(f"- {f['path']} ({f['language']}) -> {len(chunks)} chunks")
            
        if tmp_dir and os.path.exists(tmp_dir):
            shutil.rmtree(tmp_dir)
            print("Cleaned up temp directory.")
    except Exception as e:
        print(f"Error during smoke test: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_smoke()
