# Dynamic injection to satisfy imports without modifying existing codebase files
import sys
import ingestion
import parser
import utils.chunker as chunker
import reviewer
import pipeline

pipeline._import_ingestion = lambda: ingestion.clone_repo
pipeline._import_parser = lambda: parser.parse_file
pipeline._import_chunker = lambda: chunker.make_chunks
pipeline._import_reviewer = lambda: reviewer.review_code

import agent.reviewer
agent.reviewer._call_anthropic = getattr(reviewer, "_call_anthropic", None)
agent.reviewer._call_openai = getattr(reviewer, "_call_openai", None)
agent.reviewer.SYSTEM_PROMPT = getattr(reviewer, "SYSTEM_PROMPT", "")

import os, json, shutil
from dotenv import load_dotenv
load_dotenv()

print("="*50)
print("DIAGNOSTIC: Why is reviewer returning 0 comments?")
print("="*50)

# CHECK 1: API key present
key = os.environ.get("ANTHROPIC_API_KEY", "") or os.environ.get("OPENAI_API_KEY", "") or os.environ.get("GROQ_API_KEY", "")
print(f"\n[1] API KEY: {'[OK] Found (' + key[:8] + '...)' if key else '[MISSING] - this is why'}")

# CHECK 2: Clone works
print("\n[2] CLONE TEST")
from ingestion import clone_repo
files, tmp = clone_repo("https://github.com/pypa/sampleproject")

print(f"    Files found: {len(files)}")
for f in files:
    print(f"    - {f['path']} ({len(f['content'])} chars)")

# CHECK 3: Parse works
print("\n[3] PARSE TEST")
from parser import parse_file
for f in files:
    ast = parse_file(f["content"])
    print(f"    {f['path']}: {len(ast.get('functions',[]))} functions, {len(ast.get('classes',[]))} classes")
    print(f"    parse_error: {ast.get('parse_error', 'None')}")

# CHECK 4: Chunk works
print("\n[4] CHUNK TEST")
from utils.chunker import make_chunks
all_chunks = []
for f in files:
    ast = parse_file(f["content"])
    chunks = make_chunks(ast, f["content"])
    print(f"    {f['path']}: {len(chunks)} chunks")
    for i, ch in enumerate(chunks):
        print(f"      chunk[{i}] ({len(ch)} chars): {ch[:60].strip()!r}")
    all_chunks.extend([(ch, f['path']) for ch in chunks])

# CHECK 5: Reviewer called directly — print raw response
print("\n[5] REVIEWER TEST (raw)")
from agent.reviewer import review_code, _call_anthropic, _call_openai, SYSTEM_PROMPT
import os
provider = os.environ.get("LLM_PROVIDER", "openai").lower()
print(f"    Provider: {provider}")

if all_chunks:
    chunk, fpath = all_chunks[0]
    user_msg = f"File: {fpath}\n\n```python\n{chunk}\n```"
    
    print(f"    Sending {len(chunk)} chars to LLM...")
    try:
        if provider == "anthropic":
            raw = _call_anthropic(user_msg, os.environ.get("LLM_MODEL", "claude-sonnet-4-20250514"))
        elif provider == "groq":
            from agent.reviewer import _call_groq
            raw = _call_groq(user_msg, os.environ.get("LLM_MODEL", "llama-3.1-8b-instant"))
        else:
            raw = _call_openai(user_msg, os.environ.get("LLM_MODEL", "gpt-4o-mini"))
        print(f"    RAW RESPONSE ({len(raw)} chars):")
        print(f"    {raw[:500]}")
    except Exception as e:
        print(f"    [FAIL] API CALL FAILED: {e}")
        raw = ""
    
    # Now test full review_code
    print("\n    Calling review_code()...")
    try:
        comments = review_code(chunk, file_path=fpath)
        print(f"    Comments returned: {len(comments)}")
        print(f"    Raw: {json.dumps(comments, indent=2)[:300]}")
    except Exception as e:
        print(f"    [FAIL] review_code FAILED: {e}")

# CHECK 6: Pipeline _import_ingestion returns what?
print("\n[6] PIPELINE WIRING TEST")
from pipeline import _import_ingestion, _import_parser, _import_reviewer, _import_chunker
clone_fn  = _import_ingestion()
parse_fn  = _import_parser()
chunk_fn  = _import_chunker()
review_fn = _import_reviewer()
print(f"    clone_fn:  {clone_fn.__name__}")
print(f"    parse_fn:  {parse_fn.__name__}")
print(f"    chunk_fn:  {chunk_fn.__name__}")
print(f"    review_fn: {review_fn.__name__}")

# Simulate exactly what pipeline does with 1 file
f = files[0]
ast = parse_fn(f["content"])
chunks = chunk_fn(ast, f["content"])
print(f"    pipeline parse -> {len(ast.get('functions',[]))} functions")
print(f"    pipeline chunk -> {len(chunks)} chunks")
if chunks:
    comments = review_fn(chunks[0], file_path=f["path"])
    print(f"    pipeline review -> {len(comments)} comments")
    if comments:
        print(f"    First comment: {json.dumps(comments[0], indent=2)}")

shutil.rmtree(tmp, ignore_errors=True)
print("\n" + "="*50)
print("DIAGNOSTIC COMPLETE")
print("="*50)
