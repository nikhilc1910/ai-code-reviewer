from dotenv import load_dotenv
load_dotenv()

import streamlit as st
import os
import json
import threading
import time
from pipeline import run_pipeline
from utils.formatter import comments_to_markdown, comments_to_json

# Set page config
st.set_page_config(layout="wide", page_icon="🤖", page_title="AI Code Review Agent")

# CSS Styling for Premium Aesthetics
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
    
    :root {
        --bg: #0a0e1a;
        --surface: #111827;
        --glass: rgba(255, 255, 255, 0.04);
        --border: rgba(99, 179, 237, 0.15);
        --accent: #3b82f6;
        --accent2: #06b6d4;
        --text: #e2e8f0;
        --muted: #64748b;
        --critical: #ef4444;
        --major: #f97316;
        --minor: #eab308;
        --success: #22c55e;
    }
    
    /* Base backgrounds & fonts */
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Sidebar */
    [data-testid="stSidebar"] {
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] > div {
        background-color: var(--surface) !important;
    }
    
    /* Headings styling */
    h1, h2, h3, h4, h5, h6, [data-testid="stWidgetLabel"] {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--text) !important;
    }
    
    /* Animations */
    @keyframes fadeSlideUp {
        from {
            opacity: 0;
            transform: translateY(20px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(59, 130, 246, 0.4);
        }
        70% {
            box-shadow: 0 0 0 8px rgba(59, 130, 246, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(59, 130, 246, 0);
        }
    }
    
    @keyframes scanline {
        0% {
            background-position: 0% center;
        }
        50% {
            background-position: 100% center;
        }
        100% {
            background-position: 200% center;
        }
    }
    
    .main-header, .caption-style {
        animation: fadeSlideUp 0.5s ease-out forwards;
    }
    
    /* Primary Run Review Button animation */
    div[data-testid="stButton"] > button[kind="primary"] {
        animation: pulse 2s infinite !important;
        background-color: var(--accent) !important;
        color: white !important;
        border: none !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
    }
    div[data-testid="stButton"] > button[kind="primary"]:hover {
        background-color: #2563eb !important;
    }
    
    /* Header Scanline gradient sweep */
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        background: linear-gradient(90deg, var(--text), var(--accent2), var(--accent), var(--text));
        background-size: 200% auto;
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        animation: fadeSlideUp 0.5s ease-out forwards, scanline 3s ease-in-out infinite;
        margin-bottom: 0.1rem;
    }
    
    .header-tag {
        font-family: 'JetBrains Mono', monospace !important;
        color: var(--accent2) !important;
        -webkit-text-fill-color: var(--accent2) !important;
        font-size: 1.2rem !important;
        margin-right: 0.5rem !important;
        opacity: 0.8 !important;
        display: inline-block !important;
    }
    
    .caption-style {
        color: var(--muted) !important;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    
    /* Expanders styled with glassmorphism */
    div[data-testid="stExpander"] {
        background: var(--glass) !important;
        border: 1px solid var(--border) !important;
        backdrop-filter: blur(10px) !important;
        -webkit-backdrop-filter: blur(10px) !important;
        border-radius: 10px !important;
        margin-bottom: 0.6rem;
        transition: transform 0.2s ease, border-color 0.2s ease !important;
    }
    div[data-testid="stExpander"]:hover {
        transform: translateY(-2px) !important;
        border-color: var(--accent) !important;
    }
    div[data-testid="stExpander"] details {
        border: none !important;
        background: transparent !important;
    }
    div[data-testid="stExpander"] summary {
        border: none !important;
        background: transparent !important;
        color: var(--text) !important;
    }
    
    /* Metric Cards */
    [data-testid="stMetric"] {
        background: var(--glass) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        padding: 1rem !important;
        transition: border-color 0.2s ease, transform 0.2s ease !important;
    }
    [data-testid="stMetric"]:hover {
        border-color: var(--accent) !important;
        transform: translateY(-2px) !important;
    }
    [data-testid="stMetricLabel"] {
        color: var(--muted) !important;
        font-family: 'JetBrains Mono', monospace !important;
    }
    [data-testid="stMetricValue"] {
        color: var(--text) !important;
        font-family: 'Space Grotesk', sans-serif !important;
    }
    
    /* Alerts (st.info, st.warning, st.error, st.success) */
    div[data-testid="stAlert"] {
        border: none !important;
        box-shadow: none !important;
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentInfo"]) {
        border-left: 3px solid var(--accent2) !important;
        background: rgba(6, 182, 212, 0.08) !important;
        border-radius: 0 8px 8px 0 !important;
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentWarning"]) {
        border-left: 3px solid var(--major) !important;
        background: rgba(249, 115, 22, 0.08) !important;
        border-radius: 0 8px 8px 0 !important;
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentError"]) {
        border-left: 3px solid var(--critical) !important;
        background: rgba(239, 68, 68, 0.08) !important;
        border-radius: 0 8px 8px 0 !important;
    }
    div[data-testid="stAlert"]:has([data-testid="stAlertContentSuccess"]) {
        border-left: 3px solid var(--success) !important;
        background: rgba(34, 197, 94, 0.08) !important;
        border-radius: 0 8px 8px 0 !important;
    }
    
    /* Multiselect tags */
    [data-baseweb="tag"] {
        background-color: rgba(59, 130, 246, 0.2) !important;
        color: var(--accent) !important;
        border: 1px solid rgba(59, 130, 246, 0.4) !important;
        border-radius: 4px !important;
    }
    [data-baseweb="tag"] span {
        color: var(--accent) !important;
    }
    [data-baseweb="tag"] svg {
        fill: var(--accent) !important;
    }
    
    /* Slider thumb and track */
    div[role="slider"], [data-testid="stSlider"] [role="slider"] {
        background-color: var(--accent) !important;
        box-shadow: 0 0 8px var(--accent) !important;
    }
    div[data-testid="stSlider"] [data-baseweb="slider"] > div > div > div {
        background-color: var(--accent) !important;
    }
    
    /* Progress bar */
    [data-testid="stProgress"] div[role="progressbar"] > div,
    [data-testid="stProgress"] div > div > div > div {
        background: linear-gradient(90deg, var(--accent), var(--accent2)) !important;
    }
    
    /* Download buttons */
    div[data-testid="stDownloadButton"] > button,
    button[data-testid="stDownloadButton"] {
        background-color: transparent !important;
        border: 1px solid var(--accent) !important;
        color: var(--accent) !important;
        font-family: 'JetBrains Mono', monospace !important;
        transition: background-color 0.2s ease, color 0.2s ease !important;
    }
    div[data-testid="stDownloadButton"] > button:hover,
    button[data-testid="stDownloadButton"]:hover {
        background-color: var(--accent) !important;
        color: white !important;
    }
    
    /* Scrollbar override */
    ::-webkit-scrollbar {
        width: 4px !important;
        height: 4px !important;
    }
    ::-webkit-scrollbar-track {
        background: transparent !important;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(59, 130, 246, 0.4) !important;
        border-radius: 2px !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--accent) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# --- Helper functions for confidence rating ---
def _get_conf_val(c: dict) -> int:
    confidence = c.get("confidence", 0)
    try:
        return int(confidence)
    except (ValueError, TypeError):
        return 0

def _get_conf_emoji(conf_val: int) -> str:
    if conf_val >= 70:
        return "🟢"
    elif conf_val >= 40:
        return "🟡"
    else:
        return "🔴"

# --- helper render function ---
def render_comment(c: dict, show_verify: bool = False) -> None:
    severity = str(c.get("severity", "info")).lower()
    file = c.get("file") or c.get("file_path") or "<unknown_file>"
    line = c.get("line") or c.get("line_start") or "N/A"
    
    severity_emojis = {
        "critical": "🔴",
        "major": "🟠",
        "minor": "🟡",
        "info": "🔵"
    }
    sev_emoji = severity_emojis.get(severity, "⚪")
    
    label = f"{sev_emoji} `{file}` · line {line} · **{severity.upper()}**"
    
    with st.expander(label):
        category = c.get("category", "info")
        conf_val = _get_conf_val(c)
        conf_emoji = _get_conf_emoji(conf_val)
            
        message = c.get("message") or c.get("issue") or "No description provided."
        suggestion = c.get("suggestion")
        
        cols = st.columns([1, 1, 1])
        cols[0].markdown(f"**Category:** {category}")
        cols[1].markdown(f"**Confidence:** {conf_emoji} {conf_val}%")
        if show_verify:
            cols[2].warning("⚠️ verify this")
            
        st.markdown(f"**Issue:** {message}")
        if suggestion:
            st.info(f"💡 **Suggestion:**\n{suggestion}")


# --- SIDEBAR ---
st.sidebar.title("⚙️ Settings")
repo_url = st.sidebar.text_input("GitHub Repository URL", placeholder="https://github.com/user/repo")
run_btn = st.sidebar.button("🚀 Run Review", type="primary", use_container_width=True)

st.sidebar.divider()
st.sidebar.subheader("🔍 Filters")

selected_cats = st.sidebar.multiselect(
    "Category",
    options=["bug", "security", "performance", "style", "maintainability"],
    default=["bug", "security", "performance", "style", "maintainability"]
)

min_confidence = st.sidebar.slider("Minimum Confidence", min_value=0, max_value=100, value=0)

st.sidebar.divider()
st.sidebar.subheader("📥 Export")

# Show export download buttons only if we have comments in session state
if "comments" in st.session_state and isinstance(st.session_state["comments"], list) and len(st.session_state["comments"]) > 0:
    comments_list = st.session_state["comments"]
    json_str = comments_to_json(comments_list)
    md_str = comments_to_markdown(comments_list)
    
    st.sidebar.download_button(
        label="Download JSON",
        data=json_str,
        file_name="review.json",
        mime="application/json",
        use_container_width=True
    )
    st.sidebar.download_button(
        label="Download Markdown",
        data=md_str,
        file_name="review.md",
        mime="text/markdown",
        use_container_width=True
    )


# --- MAIN AREA ---
st.markdown('<div class="main-header"><span class="header-tag">// AI</span> Code Review Agent</div>', unsafe_allow_html=True)
st.markdown('<div class="caption-style"><span style="color:var(--accent2)">●</span> Powered by Claude &nbsp;·&nbsp; <span style="color:var(--accent2)">●</span> AST-aware &nbsp;·&nbsp; <span style="color:var(--accent2)">●</span> Confidence-rated</div>', unsafe_allow_html=True)

if run_btn:
    # Clear previous run results and errors
    if "comments" in st.session_state:
        del st.session_state["comments"]
    if "error" in st.session_state:
        del st.session_state["error"]

    if not repo_url.strip():
        st.error("Please enter a GitHub URL")
    else:
        with st.status("Reviewing repository...", expanded=True) as status:
            progress_bar = st.progress(0.0)
            
            # Shared structures to hold results or errors from background thread
            results = []
            errors = []
            
            def thread_target():
                try:
                    comments = run_pipeline(repo_url.strip())
                    results.append(comments)
                except Exception as e:
                    errors.append(e)

            # Spawn pipeline run in background thread
            t = threading.Thread(target=thread_target, daemon=True)
            t.start()

            # 5 animated progress steps
            steps = [
                ("Cloning repository...", 0.2),
                ("Parsing files and constructing AST...", 0.4),
                ("Chunking source code nodes...", 0.6),
                ("Analyzing code with LLM reviewer...", 0.8),
                ("Finalizing review comments...", 0.9),
            ]

            start_time = time.time()
            while t.is_alive():
                elapsed = time.time() - start_time
                # Advance step every 2.0 seconds, up to the last step (0.9 progress)
                step_idx = min(int(elapsed / 2.0), len(steps) - 1)
                step_msg, step_pct = steps[step_idx]
                
                status.update(label=step_msg)
                progress_bar.progress(step_pct)
                time.sleep(0.1)

            t.join()

            if errors:
                status.update(label="Review failed!", state="error", expanded=True)
                st.session_state["error"] = str(errors[0])
                st.rerun()
            else:
                progress_bar.progress(1.0)
                st.session_state["comments"] = results[0]
                status.update(label="Review complete!", state="complete", expanded=False)
                st.rerun()

# Display error if one occurred
if "error" in st.session_state:
    st.error(f"Error: {st.session_state['error']}")
    st.info("💡 Check that the repo URL is public and your API key is set in .env")

# Display review results if comments exist
if "comments" in st.session_state:
    comments = st.session_state["comments"]
    
    # Filter comments
    cats_lower = {sc.lower() for sc in selected_cats}
    filtered_comments = []
    for c in comments:
        cat = str(c.get("category", "")).lower()
        conf_val = _get_conf_val(c)
        if cat in cats_lower and conf_val >= min_confidence:
            filtered_comments.append(c)
            
    # Calculate metrics
    total_issues = len(filtered_comments)
    critical_count = sum(1 for c in filtered_comments if str(c.get("severity", "")).lower() == "critical")
    security_count = sum(1 for c in filtered_comments if str(c.get("category", "")).lower() == "security")
    
    confidences = [_get_conf_val(c) for c in filtered_comments]
    avg_confidence = int(sum(confidences) / len(confidences)) if confidences else 0
    
    # Render metrics in columns
    m1, m2, m3, m4 = st.columns(4)
    m1.metric("Total Issues", total_issues)
    m2.metric("Critical Issues", critical_count)
    m3.metric("Security Issues", security_count)
    m4.metric("Avg Confidence", f"{avg_confidence}%")
    
    st.divider()
    
    # Split into high and low confidence groups
    high_conf = []
    low_conf = []
    for c in filtered_comments:
        conf_val = _get_conf_val(c)
        if conf_val >= 50:
            high_conf.append(c)
        else:
            low_conf.append(c)
            
    # Render high confidence findings
    st.subheader(f"✅ Review Comments ({len(high_conf)})")
    for c in high_conf:
        render_comment(c, show_verify=False)
        
    # Render low confidence findings
    with st.expander(f"⚠️ Needs Verification — {len(low_conf)} items", expanded=False):
        st.caption("confidence < 50% — review manually before acting")
        for c in low_conf:
            render_comment(c, show_verify=True)
    
    # Render file breakdown expander
    with st.expander("📁 File breakdown"):
        st.caption("Summary of findings per file")
        # Build breakdown data
        file_stats = {}
        for c in filtered_comments:
            file_path = c.get("file") or c.get("file_path") or "<unknown_file>"
            sev = str(c.get("severity", "info")).lower()
            
            if file_path not in file_stats:
                file_stats[file_path] = {
                    "File Path": file_path,
                    "Critical 🔴": 0,
                    "Major 🟠": 0,
                    "Minor 🟡": 0,
                    "Info 🔵": 0,
                    "Total Issues": 0
                }
            
            file_stats[file_path]["Total Issues"] += 1
            if sev == "critical":
                file_stats[file_path]["Critical 🔴"] += 1
            elif sev == "major":
                file_stats[file_path]["Major 🟠"] += 1
            elif sev == "minor":
                file_stats[file_path]["Minor 🟡"] += 1
            else:
                file_stats[file_path]["Info 🔵"] += 1
        
        if file_stats:
            breakdown_list = list(file_stats.values())
            # Sort by total issues descending
            breakdown_list.sort(key=lambda x: x["Total Issues"], reverse=True)
            st.dataframe(breakdown_list, use_container_width=True, hide_index=True)
        else:
            st.info("No files processed.")
            
    # Render success message if no findings match filters
    if not filtered_comments:
        st.success("No issues match your filters 🎉")
