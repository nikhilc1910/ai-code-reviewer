import json
import os

log_path = r"C:\Users\Nikhil C\.gemini\antigravity-ide\brain\47ac476f-db91-4f5d-88c8-64077a327cec\.system_generated\logs\transcript.jsonl"
if os.path.exists(log_path):
    user_inputs = []
    with open(log_path, "r", encoding="utf-8") as f:
        for line in f:
            try:
                data = json.loads(line)
                if data.get("type") == "USER_INPUT":
                    user_inputs.append(data)
            except Exception:
                pass
    
    print(f"Total user inputs: {len(user_inputs)}")
    for item in user_inputs[-15:]:
        print(f"\n--- STEP {item.get('step_index')} ({item.get('created_at')}) ---")
        print(item.get("content"))
else:
    print(f"Log path does not exist: {log_path}")
