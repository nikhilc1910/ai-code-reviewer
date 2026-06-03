"""Thread-safe pipeline progress tracking and timing metrics."""

import threading
import time
from typing import Any, Dict, List

class PipelineProgress:
    def __init__(self):
        self.lock = threading.Lock()
        
        self.stages = [
            "cloning",
            "discovery",
            "parsing",
            "dependencies",
            "chunking",
            "static_analysis",
            "review",
            "aggregation",
            "assembly"
        ]
        
        self.stage_status: Dict[str, str] = {s: "pending" for s in self.stages}
        self.stage_messages: Dict[str, str] = {s: "" for s in self.stages}
        self.stage_durations: Dict[str, float] = {s: 0.0 for s in self.stages}
        self.stage_start_times: Dict[str, float] = {}
        
        self.total_files = 0
        self.discovered_files = 0
        self.parsed_files = 0
        self.total_chunks = 0
        self.reviewed_chunks = 0
        
        self.errors: List[str] = []
        self.logs: List[str] = []
        
        self.start_time = time.time()
        self.total_time = 0.0

    def log(self, msg: str):
        with self.lock:
            self.logs.append(msg)

    def start_stage(self, stage: str, message: str = ""):
        with self.lock:
            if stage in self.stage_status:
                self.stage_status[stage] = "running"
                self.stage_messages[stage] = message or f"Running {stage}..."
                self.stage_start_times[stage] = time.time()
                self.logs.append(f"[{stage.upper()}] Started - {self.stage_messages[stage]}")

    def complete_stage(self, stage: str, message: str = ""):
        with self.lock:
            if stage in self.stage_status:
                self.stage_status[stage] = "completed"
                if message:
                    self.stage_messages[stage] = message
                start = self.stage_start_times.get(stage)
                if start:
                    duration = time.time() - start
                    self.stage_durations[stage] = duration
                    self.logs.append(f"[{stage.upper()}] Completed in {duration:.2f}s")

    def fail_stage(self, stage: str, error_msg: str):
        with self.lock:
            if stage in self.stage_status:
                self.stage_status[stage] = "failed"
                self.stage_messages[stage] = error_msg
                self.errors.append(f"{stage.upper()} Error: {error_msg}")
                start = self.stage_start_times.get(stage)
                if start:
                    duration = time.time() - start
                    self.stage_durations[stage] = duration
                    self.logs.append(f"[{stage.upper()}] Failed in {duration:.2f}s: {error_msg}")

    def update_counts(self, total_files: int = 0, discovered_files: int = 0, parsed_files: int = 0, total_chunks: int = 0):
        with self.lock:
            if total_files:
                self.total_files = total_files
            if discovered_files:
                self.discovered_files = discovered_files
            if parsed_files:
                self.parsed_files = parsed_files
            if total_chunks:
                self.total_chunks = total_chunks

    def increment_reviewed(self):
        with self.lock:
            self.reviewed_chunks += 1

    def add_error(self, error_msg: str):
        with self.lock:
            self.errors.append(error_msg)
            self.logs.append(f"[ERROR] {error_msg}")

    def finalize(self):
        with self.lock:
            self.total_time = time.time() - self.start_time
            self.logs.append(f"[TOTAL] Completed in {self.total_time:.2f}s")
