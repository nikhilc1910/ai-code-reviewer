import sys
import os
import shutil
import json
from dotenv import load_dotenv

# Reconfigure stdout and stderr to UTF-8 for Windows console unicode support
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

# Load API keys and settings from .env file
load_dotenv()

def print_header(step_num, step_name):
    print("  ─────────────────────────────────")
    print(f"  STEP {step_num}: {step_name}")
    print("  ─────────────────────────────────")

def assert_equal(actual, expected, msg=""):
    if actual != expected:
        raise AssertionError(f"Expected {expected}, but got {actual}. {msg}")

def run_all_steps():
    # Outer state shared across steps
    files = []
    tmp = None
    parsed_asts = {}
    all_chunks = []
    all_comments = []
    
    step_results = {
        1: ("URL Validation", False),
        2: ("Clone", False),
        3: ("Parse", False),
        4: ("Chunk", False),
        5: ("Review", False),
        6: ("Full Pipeline", False),
        7: ("Formatter", False),
    }

    try:
        # STEP 1 — URL VALIDATION
        try:
            print_header(1, "URL VALIDATION")
            from ingestion import validate_github_url
            
            r1 = validate_github_url("https://github.com/pypa/sampleproject")
            print(f'validate_github_url("https://github.com/pypa/sampleproject") -> {r1}')
            assert_equal(r1, True, "Valid HTTPS URL should be True")

            r2 = validate_github_url("https://github.com/pypa/sampleproject/")
            print(f'validate_github_url("https://github.com/pypa/sampleproject/") -> {r2}')
            assert_equal(r2, True, "Valid HTTPS URL with trailing slash should be True")

            r3 = validate_github_url("not-a-url")
            print(f'validate_github_url("not-a-url") -> {r3}')
            assert_equal(r3, False, "Invalid URL string should be False")

            r4 = validate_github_url("")
            print(f'validate_github_url("") -> {r4}')
            assert_equal(r4, False, "Empty URL string should be False")
            
            print("  ✅ PASS")
            step_results[1] = ("URL Validation", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[1] = ("URL Validation", False)

        # STEP 2 — CLONE
        try:
            print_header(2, "CLONE")
            from ingestion import clone_repo
            
            print("Attempting to clone target repo: https://github.com/pypa/sampleproject")
            files, tmp = clone_repo("https://github.com/pypa/sampleproject")

            print(f"Number of files found: {len(files)}")
            for f in files:
                print(f"  - Path: {f.get('path')}, Language: {f.get('language')}")

            # Assert: len(files) >= 1
            if len(files) < 1:
                raise AssertionError(f"Expected len(files) >= 1, but got {len(files)}")

            # Assert: all files have keys: path, language, content
            # Assert: no file has empty content
            for f in files:
                for key in ["path", "language", "content"]:
                    if key not in f:
                        raise AssertionError(f"File dictionary missing key '{key}': {f}")
                if not f.get("content") or not f.get("content").strip():
                    raise AssertionError(f"File content is empty for path: {f.get('path')}")

            print("  ✅ PASS")
            step_results[2] = ("Clone", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[2] = ("Clone", False)

        # STEP 3 — PARSE
        try:
            print_header(3, "PARSE")
            from parser import parse_file
            
            if not files:
                raise AssertionError("No files available from Step 2 to parse.")

            for file in files:
                ast_data = parse_file(file["content"])
                parsed_asts[file["path"]] = ast_data
                
                fun_cnt = len(ast_data.get("functions", []))
                cls_cnt = len(ast_data.get("classes", []))
                imp_cnt = len(ast_data.get("imports", []))
                print(f"File: {file['path']} -> functions: {fun_cnt}, classes: {cls_cnt}, imports: {imp_cnt}")
                
                # Assert: ast_data has keys: functions, classes, imports
                for key in ["functions", "classes", "imports"]:
                    if key not in ast_data:
                        raise AssertionError(f"AST data missing key '{key}' in file '{file['path']}': {ast_data}")
                
                # Assert: parse_error is None or not present (no crash)
                if ast_data.get("parse_error") is not None:
                    raise AssertionError(f"Parse error found in AST for file '{file['path']}': {ast_data['parse_error']}")

            print("  ✅ PASS")
            step_results[3] = ("Parse", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[3] = ("Parse", False)

        # STEP 4 — CHUNK
        try:
            print_header(4, "CHUNK")
            from utils.chunker import make_chunks
            
            if not files:
                raise AssertionError("No files available from Step 2 to chunk.")

            for file in files:
                ast_data = parsed_asts.get(file["path"])
                if ast_data is None:
                    raise AssertionError(f"AST data missing for file '{file['path']}'")
                
                chunks = make_chunks(ast_data, file["content"])
                for chunk in chunks:
                    all_chunks.append((file["path"], chunk))
                    
                if chunks:
                    preview = chunks[0][:80].replace("\n", " ")
                    print(f"File: {file['path']} -> {len(chunks)} chunks. First chunk preview: '{preview}'")
                else:
                    print(f"File: {file['path']} -> 0 chunks")

                # Assert: len(chunks) >= 1
                if len(chunks) < 1:
                    raise AssertionError(f"Expected len(chunks) >= 1 for '{file['path']}', but got {len(chunks)}")
                    
                # Assert: all chunks are non-empty strings
                # Assert: each chunk contains "===" (proper header format)
                for chunk in chunks:
                    if not isinstance(chunk, str) or not chunk.strip():
                        raise AssertionError(f"Found empty or non-string chunk in file '{file['path']}': {chunk}")
                    if "===" not in chunk:
                        raise AssertionError(f"Chunk does not contain '===': {chunk[:100]}")

            print("  ✅ PASS")
            step_results[4] = ("Chunk", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[4] = ("Chunk", False)

        # STEP 5 — REVIEW
        try:
            print_header(5, "REVIEW")
            from reviewer import review_code
            
            if not all_chunks:
                raise AssertionError("No chunks available from Step 4 to review.")
                
            first_path, first_chunk = all_chunks[0]
            print(f"Submitting first chunk from {first_path} for LLM review...")
            comments = review_code(first_chunk, file_path="sample_test.py")
            
            print(f"Raw comments returned: {comments}")
            
            # Assert: isinstance(comments, list)
            if not isinstance(comments, list):
                raise AssertionError(f"Expected comments to be a list, but got {type(comments)}")
                
            # Assert: if comments not empty, each has keys: file, category, severity, message, suggestion, confidence
            # Assert: all confidence values are integers 0-100
            for c in comments:
                required_keys = ["file", "category", "severity", "message", "suggestion", "confidence"]
                for key in required_keys:
                    if key not in c:
                        raise AssertionError(f"Comment missing key '{key}': {c}")
                
                confidence = c["confidence"]
                if not isinstance(confidence, int) or not (0 <= confidence <= 100):
                    raise AssertionError(f"Confidence value must be an integer between 0 and 100, got: {confidence} ({type(confidence)})")

            print("  ✅ PASS")
            step_results[5] = ("Review", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[5] = ("Review", False)

        # STEP 6 — FULL PIPELINE
        try:
            print_header(6, "FULL PIPELINE")
            from pipeline import run_pipeline
            
            print("Attempting run_pipeline on target repository: https://github.com/pypa/sampleproject")
            all_comments = run_pipeline("https://github.com/pypa/sampleproject")
                
            print(f"Total comments returned: {len(all_comments)}")
            severity_breakdown = {}
            for c in all_comments:
                sev = c.get("severity", "unknown")
                severity_breakdown[sev] = severity_breakdown.get(sev, 0) + 1
            print(f"Breakdown by severity: {severity_breakdown}")
            
            # Assert: isinstance(all_comments, list)
            if not isinstance(all_comments, list):
                raise AssertionError(f"Expected all_comments to be a list, but got {type(all_comments)}")
                
            # If comments exist, assert sorted correctly
            if all_comments:
                severities = [c["severity"] for c in all_comments]
                order = {"critical": 0, "major": 1, "minor": 2, "info": 3}
                for i in range(len(severities) - 1):
                    s1 = severities[i]
                    s2 = severities[i + 1]
                    o1 = order.get(s1, 3)
                    o2 = order.get(s2, 3)
                    if o1 > o2:
                        raise AssertionError(f"Comments are not sorted correctly by severity. '{s1}' (index {i}) came before '{s2}' (index {i+1})")

            print("  ✅ PASS")
            step_results[6] = ("Full Pipeline", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[6] = ("Full Pipeline", False)

        # STEP 7 — FORMATTER
        try:
            print_header(7, "FORMATTER")
            from utils.formatter import comments_to_json, comments_to_markdown
            
            json_out = comments_to_json(all_comments)
            md_out = comments_to_markdown(all_comments)
            
            # Assert: json.loads(json_out) works without error
            try:
                json.loads(json_out)
            except Exception as je:
                raise AssertionError(f"JSON formatting is invalid: {je}")
                
            # Assert: "# Code Review Report" in md_out
            if "# Code Review Report" not in md_out:
                raise AssertionError("Expected '# Code Review Report' in markdown output")
                
            print(f"Markdown preview (first 200 chars):\n{md_out[:200]}")
            print("  ✅ PASS")
            step_results[7] = ("Formatter", True)
        except Exception as e:
            print(f"  ❌ FAIL: {e}")
            step_results[7] = ("Formatter", False)

    finally:
        # CLEANUP: Always call shutil.rmtree(tmp, ignore_errors=True) at the end.
        if tmp:
            try:
                from ingestion import remove_readonly
                shutil.rmtree(tmp, onerror=remove_readonly)
            except Exception:
                shutil.rmtree(tmp, ignore_errors=True)
            print(f"\nCleanup: Removed temporary directory {tmp}")

    # Print summary table
    print("\n  ─────────────────────────────────")
    print("  SMOKE TEST SUMMARY")
    print("  ─────────────────────────────────")
    passed_count = 0
    for step_num in sorted(step_results.keys()):
        name, passed = step_results[step_num]
        status_emoji = "✅" if passed else "❌"
        print(f"  STEP {step_num} {name:<15}  {status_emoji}")
        if passed:
            passed_count += 1
            
    print(f"\n  TOTAL: {passed_count}/7 passed")

if __name__ == "__main__":
    run_all_steps()
