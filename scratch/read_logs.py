import json
import os

log_path = r"C:\Users\Nikhil C\.gemini\antigravity-ide\brain\47ac476f-db91-4f5d-88c8-64077a327cec\.system_generated\logs\transcript.jsonl"
if os.path.exists(log_path):
    print("Reading log...")
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                step = data.get("step_index")
                src = data.get("source")
                t = data.get("type")
                content = data.get("content")
                if t in ["USER_INPUT", "PLANNER_RESPONSE"]:
                    print(f"\n--- STEP {step} ({src} - {t}) ---")
                    print(content)
            except Exception as e:
                pass
else:
    print(f"Log path does not exist: {log_path}")
