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
st.set_page_config(layout="wide", page_icon="🤖", page_title="CodeLens AI - Review Agent")

# Define mock comments for initial "Wow" landing state
MOCK_COMMENTS = [
    {
        "category": "security",
        "severity": "critical",
        "file": "api.js",
        "file_path": "api.js",
        "line": 112,
        "confidence": 95,
        "message": "Unsafe User Input Sanitization: User-controlled input from query parameters is passed directly to the execution context without sanitization, leading to Remote Code Execution (RCE).",
        "suggestion": "Use subprocess.run with an arguments array, or validate and sanitize input using a strict whitelist regex."
    },
    {
        "category": "security",
        "severity": "critical",
        "file": "userProfile.tsx",
        "file_path": "userProfile.tsx",
        "line": 245,
        "confidence": 91,
        "message": "Potential XSS Vulnerability: Inserting raw unsanitized API response attributes into HTML using dangerouslySetInnerHTML can execute malicious third-party scripts.",
        "suggestion": "Sanitize output using a library like DOMPurify, or use safe React binding text elements instead of dangerouslySetInnerHTML."
    },
    {
        "category": "performance",
        "severity": "major",
        "file": "common.utils.js",
        "file_path": "common.utils.js",
        "line": 88,
        "confidence": 78,
        "message": "Code Duplication and High Complexity: Multiple nested loops are used to search for item indices, resulting in O(N^2) complexity instead of caching in a map for O(N).",
        "suggestion": "Create a lookup Map object beforehand to reduce iterations and optimize the algorithm to linear time complexity O(N)."
    },
    {
        "category": "maintainability",
        "severity": "minor",
        "file": "dataService.js",
        "file_path": "dataService.js",
        "line": 156,
        "confidence": 65,
        "message": "Missing Documentation and Typed Annotations: The database query exporter function has complex parameter destructuring but lacks docstrings explaining types, parameters, or exceptions.",
        "suggestion": "Add complete JSDoc annotations describing parameters, types, and return models for enhanced IDE autocomplete and lint checks."
    }
]

MOCK_FILES = [
    {
        "path": "api.js",
        "language": "javascript",
        "content": """// CodeLens AI - API Entrypoint
const express = require('express');
const { exec } = require('child_process');
const app = express();

app.get('/run', (req, res) => {
    let cmd = req.query.cmd;
    // CRITICAL: Unsafe input sanitization
    exec(cmd, (err, stdout, stderr) => {
        if (err) return res.status(500).send(err.message);
        res.send(stdout);
    });
});

app.listen(3000, () => console.log('Listening on port 3000'));
"""
    },
    {
        "path": "userProfile.tsx",
        "language": "typescript",
        "content": """import React from 'react';

interface ProfileProps {
  bioHtml: string;
  name: string;
}

export const UserProfile: React.FC<ProfileProps> = ({ bioHtml, name }) => {
  return (
    <div className="profile-container">
      <h2>{name}</h2>
      {/* WARNING: Potential XSS */}
      <div dangerouslySetInnerHTML={{ __html: bioHtml }} />
    </div>
  );
};
"""
    },
    {
        "path": "common.utils.js",
        "language": "javascript",
        "content": """// Utility helper routines
export function searchItems(array, targets) {
    let matches = [];
    // O(N^2) duplication complexity
    for (let i = 0; i < array.length; i++) {
        for (let j = 0; j < targets.length; j++) {
            if (array[i].id === targets[j].id) {
                matches.push(array[i]);
            }
        }
    }
    return matches;
}
"""
    },
    {
        "path": "dataService.js",
        "language": "javascript",
        "content": """// Data fetcher and DB interface
export async function queryExporter({ filter, limit, offset, format }) {
    const rawData = await db.query(filter, limit, offset);
    if (format === 'json') {
        return JSON.stringify(rawData);
    }
    return rawData;
}
"""
    }
]

# Initialize Session State values
if "comments" not in st.session_state:
    st.session_state["comments"] = MOCK_COMMENTS
if "files" not in st.session_state:
    st.session_state["files"] = MOCK_FILES
if "llm_provider" not in st.session_state:
    st.session_state["llm_provider"] = "Groq"
if "llm_model" not in st.session_state:
    st.session_state["llm_model"] = "llama-3.1-8b-instant"
if "groq_api_key" not in st.session_state:
    st.session_state["groq_api_key"] = os.environ.get("GROQ_API_KEY", "")
if "openai_api_key" not in st.session_state:
    st.session_state["openai_api_key"] = os.environ.get("OPENAI_API_KEY", "")
if "anthropic_api_key" not in st.session_state:
    st.session_state["anthropic_api_key"] = os.environ.get("ANTHROPIC_API_KEY", "")

# CSS Styling for Premium Aesthetics (CodeLens AI styling based on visual mockups)
# CSS Styling for Premium Aesthetics (CodeLens AI styling based on visual mockups)
st.markdown(
    """
    <style>
    @import url('https://fonts.googleapis.com/css2?family=JetBrains+Mono:wght@300;400;500;600;700&family=Space+Grotesk:wght@300;400;500;600;700&display=swap');
    
    :root {
        --bg: #05070f;
        --surface: #0b0f19;
        --glass: rgba(255, 255, 255, 0.03);
        --border: rgba(99, 179, 237, 0.12);
        --accent: #3b82f6;
        --accent2: #06b6d4;
        --text: #f1f5f9;
        --muted: #94a3b8;
        --critical: #f87171;
        --major: #fb923c;
        --minor: #facc15;
        --success: #4ade80;
    }
    
    /* Base backgrounds & fonts with tech fade slide-in animation */
    @keyframes techSlideIn {
        from {
            opacity: 0;
            transform: translateY(15px);
            filter: blur(4px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
            filter: blur(0);
        }
    }
    
    html, body, [data-testid="stAppViewContainer"], [data-testid="stHeader"] {
        background-color: var(--bg) !important;
        color: var(--text) !important;
        font-family: 'Space Grotesk', sans-serif !important;
        position: relative;
    }
    
    /* Subtle tech grid background and scanline overlay all over the deployed project */
    [data-testid="stAppViewContainer"]::before {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background-image: 
            linear-gradient(rgba(6, 182, 212, 0.02) 1px, transparent 1px),
            linear-gradient(90deg, rgba(6, 182, 212, 0.02) 1px, transparent 1px);
        background-size: 40px 40px;
        background-position: center;
        pointer-events: none;
        z-index: 0;
    }
    
    [data-testid="stAppViewContainer"]::after {
        content: "";
        position: fixed;
        top: 0;
        left: 0;
        width: 100vw;
        height: 100vh;
        background: linear-gradient(
            to bottom,
            rgba(6, 182, 212, 0) 0%,
            rgba(6, 182, 212, 0.03) 10%,
            rgba(6, 182, 212, 0) 20%
        );
        background-size: 100% 200%;
        animation: techScanline 12s linear infinite;
        pointer-events: none;
        z-index: 1;
    }
    
    @keyframes techScanline {
        0% { background-position: 0% 0%; }
        100% { background-position: 0% 200%; }
    }
    
    [data-testid="stAppViewContainer"] {
        animation: techSlideIn 0.7s cubic-bezier(0.16, 1, 0.3, 1) forwards;
    }
    
    /* Global visibility overrides for captions, titles, sidebar items, and controls to eliminate dark-on-dark text */
    [data-testid="stSidebar"] p, 
    [data-testid="stSidebar"] span, 
    [data-testid="stSidebar"] label, 
    [data-testid="stSidebar"] div,
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"],
    [data-testid="stSidebar"] [data-testid="stCaptionContainer"] *,
    [data-testid="stSidebar"] [class*="stCaption"],
    [data-testid="stSidebar"] [class*="stCaption"] *,
    [data-testid="stSidebar"] caption {
        color: #cbd5e1 !important;
    }
    
    [data-testid="stSidebar"] h2,
    [data-testid="stSidebar"] h3,
    [data-testid="stSidebar"] h4,
    [data-testid="stSidebar"] h5,
    [data-testid="stSidebar"] strong {
        color: #ffffff !important;
        font-weight: 700 !important;
    }
    
    [data-testid="stSidebar"] div[data-testid="stCaptionContainer"] p,
    [data-testid="stSidebar"] [class*="stCaption"] p {
        color: #94a3b8 !important;
        font-size: 0.85rem !important;
        font-weight: 500 !important;
    }
    
    /* Header top-bar button and icon visibility fixes (e.g. Share, Star, Edit, Github icons) */
    header[data-testid="stHeader"] button,
    header[data-testid="stHeader"] a,
    header[data-testid="stHeader"] svg,
    header[data-testid="stHeader"] svg *,
    header[data-testid="stHeader"] button *,
    header[data-testid="stHeader"] a *,
    header[data-testid="stHeader"] span,
    header[data-testid="stHeader"] div {
        color: #cbd5e1 !important;
        fill: #cbd5e1 !important;
        stroke: #cbd5e1 !important;
        transition: color 0.2s ease, fill 0.2s ease, stroke 0.2s ease !important;
    }
    header[data-testid="stHeader"] button:hover *,
    header[data-testid="stHeader"] a:hover *,
    header[data-testid="stHeader"] button:hover,
    header[data-testid="stHeader"] a:hover {
        color: #ffffff !important;
        fill: #ffffff !important;
        stroke: #ffffff !important;
    }
    
    /* Code and details use JetBrains Mono */
    code, pre, .finding-index, .finding-progress-bar, .finding-confidence-text, .finding-tag, .stat-card-change {
        font-family: 'JetBrains Mono', monospace !important;
    }
    
    /* Sidebar styling */
    [data-testid="stSidebar"] {
        background-color: var(--surface) !important;
        border-right: 1px solid var(--border) !important;
    }
    [data-testid="stSidebar"] > div {
        background-color: var(--surface) !important;
    }
    
    /* Headings */
    h1, h2, h3, h4, h5, h6, [data-testid="stWidgetLabel"] {
        font-family: 'Space Grotesk', sans-serif !important;
        color: var(--text) !important;
    }
    
    /* Hide the radio button circle indicators in the sidebar navigation completely (robust sibling filters) */
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label > *:not([data-testid="stMarkdownContainer"]) {
        display: none !important;
        width: 0 !important;
        height: 0 !important;
        opacity: 0 !important;
        visibility: hidden !important;
    }
    
    /* Sidebar radio button styling transformed into custom navigation tabs */
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] {
        gap: 0.5rem;
    }
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label {
        background: transparent !important;
        border: 1px solid transparent !important;
        padding: 0.7rem 1rem !important;
        border-radius: 8px !important;
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), background-color 0.25s ease, border-color 0.25s ease !important;
        cursor: pointer !important;
        display: flex !important;
        align-items: center !important;
        transform-origin: left center;
    }
    
    /* Fix text contrast & hover-zoom in left column navigation tabs */
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label [data-testid="stMarkdownContainer"] {
        color: #94a3b8 !important; /* light grey unselected */
        font-weight: 500 !important;
        font-size: 1.05rem !important;
        transition: color 0.25s ease-in-out, transform 0.25s ease-in-out !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover {
        background: rgba(255, 255, 255, 0.03) !important;
        border-color: rgba(99, 179, 237, 0.1) !important;
        transform: scale(1.05) !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:hover [data-testid="stMarkdownContainer"] {
        color: #ffffff !important; /* white on hover */
    }
    
    /* Modern bulletproof selected tab selector using :has() */
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) {
        background: rgba(59, 130, 246, 0.1) !important;
        border: 1px solid rgba(59, 130, 246, 0.25) !important;
        box-shadow: 0 0 15px rgba(6, 182, 212, 0.15) !important;
    }
    
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) [data-testid="stMarkdownContainer"] *,
    [data-testid="stSidebar"] [data-testid="stRadio"] [role="radiogroup"] label:has(input:checked) [data-testid="stMarkdownContainer"] {
        color: var(--accent2) !important; /* bright cyan when selected */
        font-weight: 700 !important;
    }
    
    /* Style all Streamlit input controls (text inputs, selects, multiselects) to remove "white boxes" and match the dark theme */
    div[data-testid="stTextInput"] input,
    div[data-testid="stTextArea"] textarea,
    div[data-testid="stSelectbox"] select,
    div[data-testid="stSelectbox"] div[data-baseweb="select"],
    div[data-testid="stMultiSelect"] div[data-baseweb="select"],
    div[data-baseweb="select"] > div {
        background-color: #0e1220 !important;
        color: var(--text) !important;
        border: 1px solid var(--border) !important;
        border-radius: 8px !important;
        transition: border-color 0.25s ease, box-shadow 0.25s ease !important;
    }
    
    /* Input field focus glow tech animations */
    div[data-testid="stTextInput"] input:focus,
    div[data-testid="stSelectbox"] div[data-baseweb="select"]:focus,
    div[data-testid="stMultiSelect"] div[data-baseweb="select"]:focus {
        border-color: var(--accent2) !important;
        box-shadow: 0 0 12px rgba(6, 182, 212, 0.25) !important;
    }
    
    /* Input placeholder styling */
    div[data-testid="stTextInput"] input::placeholder {
        color: #64748b !important;
    }
    
    /* Multiselect tags styling */
    div[data-testid="stMultiSelect"] span[data-baseweb="tag"] {
        background-color: rgba(6, 182, 212, 0.12) !important;
        border: 1px solid rgba(6, 182, 212, 0.25) !important;
        color: var(--accent2) !important;
        border-radius: 4px !important;
    }
    div[data-testid="stMultiSelect"] span[data-baseweb="tag"] span {
        color: var(--accent2) !important;
    }
    div[data-testid="stMultiSelect"] span[data-baseweb="tag"] svg {
        fill: var(--accent2) !important;
    }
    div[data-testid="stMultiSelect"] input {
        background-color: transparent !important;
        color: var(--text) !important;
    }
    
    /* Dropdown/Listbox popover menus styling for selects and multiselects */
    div[data-baseweb="popover"] ul,
    div[data-baseweb="menu"] {
        background-color: #0e1220 !important;
        border: 1px solid var(--border) !important;
    }
    div[data-baseweb="popover"] li,
    div[data-baseweb="menu"] li {
        color: var(--text) !important;
        background-color: transparent !important;
        transition: background-color 0.2s ease !important;
    }
    div[data-baseweb="popover"] li:hover,
    div[data-baseweb="menu"] li:hover {
        background-color: rgba(6, 182, 212, 0.1) !important;
        color: var(--accent2) !important;
    }
    
    /* Animations */
    @keyframes fadeSlideUp {
        from {
            opacity: 0;
            transform: translateY(12px);
        }
        to {
            opacity: 1;
            transform: translateY(0);
        }
    }
    
    @keyframes pulse {
        0% {
            box-shadow: 0 0 0 0 rgba(6, 182, 212, 0.4);
        }
        70% {
            box-shadow: 0 0 0 8px rgba(6, 182, 212, 0);
        }
        100% {
            box-shadow: 0 0 0 0 rgba(6, 182, 212, 0);
        }
    }
    
    /* Primary RUN NEW REVIEW button styling */
    div[data-testid="stSidebar"] button[kind="primary"] {
        animation: pulse 2.5s infinite !important;
        background: linear-gradient(135deg, var(--accent) 0%, var(--accent2) 100%) !important;
        color: white !important;
        border: none !important;
        font-family: 'Space Grotesk', sans-serif !important;
        font-weight: 600 !important;
        border-radius: 8px !important;
        padding: 0.75rem 1.2rem !important;
        box-shadow: 0 0 15px rgba(59, 130, 246, 0.3) !important;
        transition: all 0.3s ease !important;
    }
    div[data-testid="stSidebar"] button[kind="primary"]:hover {
        box-shadow: 0 0 25px rgba(6, 182, 212, 0.5) !important;
        transform: translateY(-2px) !important;
    }
    
    /* Outlined buttons */
    div[data-testid="stDownloadButton"] > button,
    button[data-testid="stDownloadButton"] {
        background-color: transparent !important;
        border: 1px solid var(--border) !important;
        color: var(--accent2) !important;
        border-radius: 6px !important;
        transition: all 0.2s ease !important;
    }
    div[data-testid="stDownloadButton"] > button:hover,
    button[data-testid="stDownloadButton"]:hover {
        background-color: rgba(6, 182, 212, 0.08) !important;
        border-color: var(--accent2) !important;
    }
    
    /* Custom Stat Cards styling with hover-zoom & tech scanline sweep transitions */
    .stat-card {
        background: var(--glass);
        border: 1px solid var(--border);
        border-radius: 12px;
        padding: 1.2rem;
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease, box-shadow 0.25s ease !important;
        position: relative;
        overflow: hidden;
    }
    .stat-card::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 50%;
        height: 100%;
        background: linear-gradient(
            to right,
            rgba(255, 255, 255, 0) 0%,
            rgba(6, 182, 212, 0.08) 50%,
            rgba(255, 255, 255, 0) 100%
        );
        transform: skewX(-25deg);
        transition: 0.75s;
    }
    .stat-card:hover::after {
        left: 120%;
    }
    .stat-card:hover {
        border-color: var(--accent) !important;
        transform: scale(1.04) !important;
        box-shadow: 0 12px 40px rgba(59, 130, 246, 0.2) !important;
        z-index: 2;
    }
    @keyframes neonBorderGlow {
        0% {
            border-color: rgba(6, 182, 212, 0.2);
            box-shadow: 0 0 10px rgba(6, 182, 212, 0.05);
        }
        50% {
            border-color: rgba(6, 182, 212, 0.6);
            box-shadow: 0 0 25px rgba(6, 182, 212, 0.25);
        }
        100% {
            border-color: rgba(6, 182, 212, 0.2);
            box-shadow: 0 0 10px rgba(6, 182, 212, 0.05);
        }
    }
    .stat-glow {
        animation: neonBorderGlow 3s infinite ease-in-out !important;
    }
    .stat-card-title {
        color: var(--muted);
        font-family: 'JetBrains Mono', monospace;
        font-size: 0.75rem;
        letter-spacing: 0.05em;
        text-transform: uppercase;
        margin-bottom: 0.5rem;
    }
    .stat-card-value-row {
        display: flex;
        justify-content: space-between;
        align-items: center;
        margin-bottom: 0.3rem;
    }
    .stat-card-value {
        color: var(--text);
        font-family: 'Space Grotesk', sans-serif;
        font-size: 1.9rem;
        font-weight: 700;
        transition: transform 0.2s ease, color 0.2s ease !important;
    }
    .stat-card:hover .stat-card-value {
        color: var(--accent2) !important;
        transform: scale(1.05) !important;
        display: inline-block;
    }
    .stat-card-emoji {
        font-size: 1.4rem;
    }
    .stat-card-change {
        font-size: 0.85rem;
        font-weight: 500;
    }
    
    /* Interactive HTML findings accordion panel with hover-zoom and scanline sweep */
    details.finding-detail-box {
        background: var(--glass);
        border: 1px solid var(--border);
        border-radius: 10px;
        margin-bottom: 0.8rem;
        padding: 0.85rem 1.1rem;
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), border-color 0.25s ease, box-shadow 0.25s ease !important;
        position: relative;
        overflow: hidden;
    }
    details.finding-detail-box::after {
        content: '';
        position: absolute;
        top: 0;
        left: -100%;
        width: 30%;
        height: 100%;
        background: linear-gradient(
            to right,
            rgba(255, 255, 255, 0) 0%,
            rgba(59, 130, 246, 0.05) 50%,
            rgba(255, 255, 255, 0) 100%
        );
        transform: skewX(-25deg);
        transition: 0.6s;
    }
    details.finding-detail-box:hover::after {
        left: 120%;
    }
    details.finding-detail-box:hover {
        border-color: rgba(6, 182, 212, 0.4) !important;
        transform: scale(1.015) !important;
        box-shadow: 0 6px 24px rgba(6, 182, 212, 0.12) !important;
    }
    details.finding-detail-box[open] {
        border-color: var(--accent);
        background: rgba(11, 15, 25, 0.6);
    }
    summary.finding-summary {
        display: flex;
        justify-content: space-between;
        align-items: center;
        cursor: pointer;
        list-style: none;
        user-select: none;
    }
    summary.finding-summary::-webkit-details-marker {
        display: none;
    }
    .finding-summary-left {
        display: flex;
        align-items: center;
        gap: 12px;
        flex-grow: 1;
        overflow: hidden;
        margin-right: 20px;
    }
    .finding-index {
        color: var(--muted);
        font-weight: 700;
        font-size: 0.9rem;
    }
    
    /* Severity badge pulse animations */
    @keyframes badgePulse {
        0% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0.4); }
        70% { box-shadow: 0 0 0 6px rgba(248, 113, 113, 0); }
        100% { box-shadow: 0 0 0 0 rgba(248, 113, 113, 0); }
    }
    
    .finding-severity-badge {
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.72rem;
        font-weight: 600;
        text-transform: uppercase;
        display: inline-flex;
        align-items: center;
        gap: 4px;
        min-width: 95px;
        justify-content: center;
    }
    .sev-critical {
        background: rgba(248, 113, 113, 0.12);
        color: var(--critical);
        border: 1px solid rgba(248, 113, 113, 0.25);
        animation: badgePulse 2s infinite !important;
    }
    .sev-major {
        background: rgba(251, 146, 60, 0.12);
        color: var(--major);
        border: 1px solid rgba(251, 146, 60, 0.25);
    }
    .sev-minor {
        background: rgba(250, 204, 21, 0.12);
        color: var(--minor);
        border: 1px solid rgba(250, 204, 21, 0.25);
    }
    .sev-info {
        background: rgba(74, 222, 128, 0.12);
        color: var(--success);
        border: 1px solid rgba(74, 222, 128, 0.25);
    }
    
    /* Hover effects for important findings text */
    .finding-title {
        color: var(--text);
        font-size: 0.95rem;
        font-weight: 500;
        white-space: nowrap;
        overflow: hidden;
        text-overflow: ellipsis;
        transition: transform 0.25s ease, color 0.25s ease, padding-left 0.25s ease !important;
        position: relative;
    }
    .finding-title::before {
        content: ">";
        color: var(--accent2);
        opacity: 0;
        position: absolute;
        left: -15px;
        transition: opacity 0.25s ease, left 0.25s ease !important;
    }
    .finding-title:hover {
        color: var(--accent2) !important;
        padding-left: 15px !important;
    }
    .finding-title:hover::before {
        opacity: 1;
        left: 0;
    }
    
    .finding-line {
        color: var(--muted);
        font-size: 0.8rem;
        margin-left: 5px;
        transition: color 0.2s ease !important;
    }
    .finding-line:hover {
        color: #ffffff !important;
    }
    .finding-summary-right {
        display: flex;
        align-items: center;
        gap: 15px;
    }
    .finding-progress-bar {
        color: var(--accent2);
        letter-spacing: -2px;
        font-size: 0.95rem;
        font-weight: bold;
    }
    .finding-confidence-text {
        color: var(--text);
        font-weight: 600;
        font-size: 0.9rem;
        min-width: 35px;
        text-align: right;
    }
    .finding-content {
        margin-top: 1rem;
        padding-top: 1rem;
        border-top: 1px solid var(--border);
        animation: fadeSlideUp 0.3s ease-out forwards;
    }
    .finding-tags {
        display: flex;
        gap: 8px;
        margin-bottom: 0.8rem;
    }
    .finding-tag {
        background: rgba(59, 130, 246, 0.08);
        border: 1px solid rgba(59, 130, 246, 0.2);
        color: #93c5fd;
        padding: 2px 8px;
        border-radius: 4px;
        font-size: 0.75rem;
    }
    .finding-description {
        background: rgba(255, 255, 255, 0.015);
        border: 1px solid var(--border);
        border-radius: 6px;
        padding: 0.8rem;
        color: var(--text);
        font-size: 0.9rem;
        margin-bottom: 0.8rem;
        line-height: 1.5;
    }
    .finding-suggestion-box {
        background: rgba(6, 182, 212, 0.03);
        border-left: 3px solid var(--accent2);
        border-radius: 0 6px 6px 0;
        padding: 0.8rem;
        color: var(--text);
        font-size: 0.9rem;
        line-height: 1.5;
    }
    
    /* Main title and logo transition styles for hover-zoom */
    .main-title-container {
        font-size: 2.2rem;
        font-weight: 700;
        font-family: 'Space Grotesk', sans-serif;
        letter-spacing: -0.5px;
        margin-bottom: 5px;
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1), color 0.25s ease !important;
        display: inline-block;
        transform-origin: left center;
    }
    .main-title-container:hover {
        transform: scale(1.03) !important;
        color: var(--accent2) !important;
    }
    
    .sidebar-logo-container {
        transition: transform 0.25s cubic-bezier(0.4, 0, 0.2, 1) !important;
        display: inline-block;
        transform-origin: left center;
    }
    .sidebar-logo-container:hover {
        transform: scale(1.05) !important;
    }
    
    /* Scrollbar overrides */
    ::-webkit-scrollbar {
        width: 5px !important;
        height: 5px !important;
    }
    ::-webkit-scrollbar-track {
        background: transparent !important;
    }
    ::-webkit-scrollbar-thumb {
        background: rgba(59, 130, 246, 0.3) !important;
        border-radius: 3px !important;
    }
    ::-webkit-scrollbar-thumb:hover {
        background: var(--accent2) !important;
    }
    </style>
    """,
    unsafe_allow_html=True
)

# Helper function for confidence rating conversions
def _get_conf_val(c: dict) -> int:
    confidence = c.get("confidence", 0)
    try:
        return int(confidence)
    except (ValueError, TypeError):
        return 0

# --- SIDEBAR NAV ---
st.sidebar.markdown(
    """
    <div style="padding: 10px 0px; margin-bottom: 15px;">
        <h2 class="sidebar-logo-container" style="font-family:'Space Grotesk', sans-serif; font-size:1.6rem; font-weight:700; color:var(--text); margin:0; display:inline-block;">
            <span style="color:var(--accent2)">🤖</span> CodeLens AI
        </h2>
    </div>
    """,
    unsafe_allow_html=True
)

selected_tab = st.sidebar.radio(
    "Navigation",
    ["Overview", "Codebase", "Settings", "API Docs"],
    index=0,
    label_visibility="collapsed"
)

# --- SIDEBAR RUN FORM ---
st.sidebar.divider()
st.sidebar.subheader("🚀 Run Review")
repo_url = st.sidebar.text_input("GitHub Repository URL", placeholder="https://github.com/user/repo", label_visibility="collapsed")
run_btn = st.sidebar.button("RUN NEW REVIEW ↗", type="primary", use_container_width=True)

# --- SIDEBAR FILTERS ---
st.sidebar.divider()
st.sidebar.subheader("🔍 Filters")
selected_cats = st.sidebar.multiselect(
    "Category Filter",
    options=["bug", "security", "performance", "style", "maintainability"],
    default=["bug", "security", "performance", "style", "maintainability"]
)

min_confidence = st.sidebar.slider("Min Confidence Rating", min_value=0, max_value=100, value=0)

# Mocked Filter parameters matching mockup design
st.sidebar.selectbox("Date Range", options=["Last 7 Days", "Last 30 Days", "All Time"], disabled=True)
st.sidebar.selectbox("Branch Context", options=["main", "develop", "staging"], disabled=True)

# --- SIDEBAR EXPORTS ---
st.sidebar.divider()
st.sidebar.subheader("📥 Export")
comments_list = st.session_state["comments"]
if comments_list and len(comments_list) > 0 and comments_list != MOCK_COMMENTS:
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
else:
    st.sidebar.caption("Run a real review to export reports.")


# --- TRIGGER RUN PIPELINE ---
if run_btn:
    # Clear previous results
    st.session_state["comments"] = []
    st.session_state["files"] = []
    if "error" in st.session_state:
        del st.session_state["error"]

    if not repo_url.strip():
        st.error("Please enter a GitHub URL")
    else:
        # Dynamically inject settings configurations into environment variables
        os.environ["LLM_PROVIDER"] = st.session_state["llm_provider"].lower()
        os.environ["LLM_MODEL"] = st.session_state["llm_model"]
        if st.session_state["groq_api_key"]:
            os.environ["GROQ_API_KEY"] = st.session_state["groq_api_key"]
        if st.session_state["openai_api_key"]:
            os.environ["OPENAI_API_KEY"] = st.session_state["openai_api_key"]
        if st.session_state["anthropic_api_key"]:
            os.environ["ANTHROPIC_API_KEY"] = st.session_state["anthropic_api_key"]

        with st.status("Analyzing codebase repository...", expanded=True) as status:
            progress_bar = st.progress(0.0)
            
            results = []
            errors = []
            
            def thread_target():
                try:
                    # Execute pipeline
                    comments = run_pipeline(repo_url.strip())
                    results.append(comments)
                except Exception as e:
                    errors.append(e)

            # Start pipeline thread
            t = threading.Thread(target=thread_target, daemon=True)
            t.start()

            steps = [
                ("Cloning codebase files...", 0.2),
                ("Constructing abstract syntax trees...", 0.4),
                ("Extracting AST nodes and chunking modules...", 0.6),
                ("Submitting code blocks to LLM Reviewer...", 0.8),
                ("Assembling findings report...", 0.9),
            ]

            start_time = time.time()
            while t.is_alive():
                elapsed = time.time() - start_time
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
                comments = results[0]
                st.session_state["comments"] = comments
                st.session_state["files"] = getattr(comments, "files", [])
                status.update(label="Review completed!", state="complete", expanded=False)
                st.rerun()

# Display error alerts if occurred
if "error" in st.session_state:
    st.error(f"Execution Error: {st.session_state['error']}")
    st.info("💡 Ensure the target repository is public and appropriate API keys are configured in Settings.")


# --- MAIN CONTENT SWITCHER ---

if selected_tab == "Overview":
    # 1. TOP HEADER PANEL (Mockup layout search + notifications + avatar)
    st.markdown('<div style="margin-top: 10px;"></div>', unsafe_allow_html=True)
    top_col1, top_col2, top_col3 = st.columns([5, 1, 2])
    with top_col1:
        search_query = st.text_input(
            "Search",
            placeholder="🔍 Search issues, files, or severities...",
            label_visibility="collapsed"
        )
    with top_col2:
        st.markdown(
            """
            <div style="display:flex; justify-content:center; align-items:center; height:38px;">
                <span style="font-size:1.4rem; cursor:pointer; position:relative; color:#94a3b8;">
                    🔔<span style="position:absolute; top:2px; right:2px; background:#f87171; width:7px; height:7px; border-radius:50%;"></span>
                </span>
            </div>
            """,
            unsafe_allow_html=True
        )
    with top_col3:
        st.markdown(
            """
            <div style="display:flex; align-items:center; gap:10px; justify-content:flex-end; height:38px;">
                <img src="https://images.unsplash.com/photo-1494790108377-be9c29b29330?auto=format&fit=crop&q=80&w=100" style="width:30px; height:30px; border-radius:50%; object-fit:cover; border: 1px solid var(--border);" />
                <span style="font-family:'Space Grotesk', sans-serif; font-size:0.9rem; color:var(--text); font-weight:500;">Sarah Jenkins ∨</span>
            </div>
            """,
            unsafe_allow_html=True
        )
    
    st.markdown('<div style="margin-top: 25px;"></div>', unsafe_allow_html=True)
    st.markdown('<div class="main-title-container">// AI Code Review Agent</div>', unsafe_allow_html=True)
    
    # Render active configuration subtitle
    active_prov = st.session_state["llm_provider"]
    active_mod = st.session_state["llm_model"]
    st.markdown(f'<div style="color:var(--muted); font-size:0.95rem; margin-bottom:25px; font-family:\'JetBrains Mono\', monospace;"><span style="color:var(--accent2)">●</span> Active Engine: {active_prov} ({active_mod}) &nbsp;·&nbsp; <span style="color:var(--accent2)">●</span> AST-Aware &nbsp;·&nbsp; <span style="color:var(--accent2)">●</span> Confidence-Rated</div>', unsafe_allow_html=True)

    # 2. FILTER & CALCULATE METRICS
    comments = st.session_state["comments"]
    cats_lower = {sc.lower() for sc in selected_cats}
    
    filtered_comments = []
    for c in comments:
        # Match filters
        cat = str(c.get("category", "")).lower()
        conf_val = _get_conf_val(c)
        if cat not in cats_lower or conf_val < min_confidence:
            continue
            
        # Match search text query
        msg = str(c.get("message", "")).lower()
        suggestion = str(c.get("suggestion", "")).lower()
        file_path = str(c.get("file", "")).lower()
        severity = str(c.get("severity", "")).lower()
        
        if search_query:
            query = search_query.lower()
            if query not in msg and query not in suggestion and query not in file_path and query not in severity:
                continue
                
        filtered_comments.append(c)

    # Calculate metrics
    total_issues = len(filtered_comments)
    critical_count = sum(1 for c in filtered_comments if str(c.get("severity", "")).lower() == "critical")
    security_count = sum(1 for c in filtered_comments if str(c.get("category", "")).lower() == "security")
    
    confidences = [_get_conf_val(c) for c in filtered_comments]
    avg_confidence = int(sum(confidences) / len(confidences)) if confidences else 0

    # 3. STAT CARDS LAYOUT
    s1, s2, s3, s4 = st.columns(4)
    
    def render_card(col, title, value, change, color, emoji, glow=False):
        glow_cls = "stat-glow" if glow else ""
        card_html = f"""
        <div class="stat-card {glow_cls}">
            <div class="stat-card-title">{title}</div>
            <div class="stat-card-value-row">
                <span class="stat-card-value">{value}</span>
                <span class="stat-card-emoji">{emoji}</span>
            </div>
            <div class="stat-card-change" style="color: {color};">{change}</div>
        </div>
        """
        col.markdown(card_html, unsafe_allow_html=True)

    render_card(s1, "Total Issues", total_issues, "+12% vs last scan", "var(--success)", "📊", glow=True)
    render_card(s2, "Critical Issues", critical_count, "+3% need verification", "var(--major)", "🔥")
    render_card(s3, "Security Issues", security_count, "-5% resolved", "var(--accent2)", "🛡️")
    render_card(s4, "Avg Confidence", f"{avg_confidence}%", "+0.8% accuracy rate", "var(--success)", "🧠")

    st.markdown('<div style="margin-top: 35px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.4rem; font-weight: 700; font-family:\'Space Grotesk\', sans-serif; margin-bottom:15px;">Code Review Findings</div>', unsafe_allow_html=True)

    # Group into high and low confidence reviews
    high_conf = [c for c in filtered_comments if _get_conf_val(c) >= 50]
    low_conf = [c for c in filtered_comments if _get_conf_val(c) < 50]

    # Render finding helper renderer
    def build_finding_html(comment_list, start_idx=1, force_verify_badge=False):
        html_cards = []
        for idx, c in enumerate(comment_list, start_idx):
            severity = str(c.get("severity", "info")).lower()
            file_path = c.get("file") or c.get("file_path") or "<unknown>"
            line = c.get("line") or c.get("line_start") or "N/A"
            category = c.get("category", "info")
            conf_val = _get_conf_val(c)
            
            severity_emojis = {
                "critical": "🔴",
                "major": "🟠",
                "minor": "🟡",
                "info": "🔵"
            }
            sev_emoji = severity_emojis.get(severity, "🔵")
            
            sev_text = severity.upper()
            if sev_text == "MAJOR":
                sev_text = "MODERATE"
            
            sev_class = f"sev-{severity}"
            
            # Confidence meter blocks
            total_blocks = 12
            filled = int((conf_val / 100) * total_blocks)
            filled_str = "|" * filled
            empty_str = "|" * (total_blocks - filled)
            progress_blocks = f'<span style="color:var(--accent2)">{filled_str}</span><span style="color:rgba(255,255,255,0.12)">{empty_str}</span>'
            
            msg_text = c.get("message") or "No description provided."
            suggestion = c.get("suggestion", "")
            
            verify_badge_html = ""
            if force_verify_badge or conf_val < 50:
                verify_badge_html = '<span class="finding-tag" style="background:rgba(239,68,68,0.1); border-color:rgba(239,68,68,0.3); color:#f87171;">⚠️ Verify This</span>'

            suggestion_block = ""
            if suggestion:
                suggestion_block = f"""
                <div class="finding-suggestion-box">
                    <strong>💡 Suggestion:</strong><br/>
                    {suggestion.replace('\\n', '<br/>').replace('\n', '<br/>')}
                </div>
                """
                
            card_html = f"""
            <details class="finding-detail-box">
                <summary class="finding-summary">
                    <div class="finding-summary-left">
                        <span class="finding-index">[{idx}]</span>
                        <span class="finding-severity-badge {sev_class}">{sev_emoji} {sev_text}</span>
                        <span class="finding-title">{msg_text} <span class="finding-line">({file_path}:{line})</span></span>
                    </div>
                    <div class="finding-summary-right">
                        <span class="finding-progress-bar">[{progress_blocks}]</span>
                        <span class="finding-confidence-text">{conf_val}%</span>
                    </div>
                </summary>
                <div class="finding-content">
                    <div class="finding-tags">
                        <span class="finding-tag">Category: {category}</span>
                        <span class="finding-tag">Confidence: {conf_val}%</span>
                        {verify_badge_html}
                        <span class="finding-tag">By: AI Agent</span>
                    </div>
                    <div class="finding-description">
                        <strong>Detailed Issue:</strong> {msg_text}
                    </div>
                    {suggestion_block}
                </div>
            </details>
            """
            html_cards.append(card_html)
        return "\n".join(html_cards)

    # Render findings
    if high_conf:
        st.markdown(build_finding_html(high_conf, start_idx=1), unsafe_allow_html=True)
    else:
        st.caption("No high confidence findings match filters.")

    # Needs verification section
    if low_conf:
        st.markdown('<div style="margin-top: 25px;"></div>', unsafe_allow_html=True)
        with st.expander(f"⚠️ Needs Verification — {len(low_conf)} items", expanded=False):
            st.caption("Confidence score < 50% — these findings should be reviewed manually before taking action.")
            st.markdown(build_finding_html(low_conf, start_idx=len(high_conf) + 1, force_verify_badge=True), unsafe_allow_html=True)

    # Render File breakdown table
    st.markdown('<div style="margin-top: 25px;"></div>', unsafe_allow_html=True)
    with st.expander("📁 File breakdown", expanded=False):
        st.caption("Summary of findings and severity levels mapped per file path")
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
            breakdown_list.sort(key=lambda x: x["Total Issues"], reverse=True)
            st.dataframe(breakdown_list, use_container_width=True, hide_index=True)
        else:
            st.info("No file statistics available.")

elif selected_tab == "Codebase":
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.8rem; font-weight: 700; font-family:\'Space Grotesk\', sans-serif;">📁 Codebase File Explorer</div>', unsafe_allow_html=True)
    st.caption("Browse repository files, inspect source code, and view review comments associated with specific lines.")
    
    files = st.session_state["files"]
    comments = st.session_state["comments"]
    
    if not files:
        st.info("No codebase files scanned yet. Enter a repository URL and click 'Run Review' in the sidebar.")
    else:
        file_paths = [f["path"] for f in files]
        
        col_list, col_viewer = st.columns([1, 2])
        
        with col_list:
            st.markdown("#### Repository Files")
            selected_file = st.radio(
                "Select a file to view:",
                options=file_paths,
                label_visibility="collapsed"
            )
            
        with col_viewer:
            file_obj = next(f for f in files if f["path"] == selected_file)
            st.markdown(f"#### Viewing: `{selected_file}`")
            
            st.code(
                file_obj["content"],
                language=file_obj.get("language", "python")
            )
            
            # Show review comments associated with this specific file
            file_comments = [c for c in comments if (c.get("file") or c.get("file_path")) == selected_file]
            
            st.divider()
            st.markdown(f"##### Line-level Review Comments ({len(file_comments)})")
            
            if not file_comments:
                st.success("No issues detected in this file! 🎉")
            else:
                for idx, c in enumerate(file_comments, 1):
                    line = c.get("line") or "N/A"
                    sev = str(c.get("severity", "info")).upper()
                    if sev == "MAJOR":
                        sev = "MODERATE"
                        
                    cat = c.get("category", "style")
                    msg = c.get("message", "")
                    sug = c.get("suggestion", "")
                    
                    st.markdown(
                        f"""
                        <div style="background:var(--glass); border:1px solid var(--border); padding:10px 15px; border-radius:6px; margin-bottom:8px;">
                            <div style="display:flex; justify-content:space-between; margin-bottom:5px;">
                                <span style="font-family:'JetBrains Mono', monospace; font-size:0.85rem; font-weight:bold; color:var(--accent2)">Line {line} · {sev}</span>
                                <span style="font-family:'JetBrains Mono', monospace; font-size:0.75rem; background:rgba(255,255,255,0.05); padding:2px 6px; border-radius:3px; color:var(--muted);">{cat}</span>
                            </div>
                            <div style="font-size:0.9rem; color:var(--text); margin-bottom:5px;">{msg}</div>
                            {f'<div style="font-size:0.85rem; color:var(--accent2); background:rgba(6,182,212,0.03); border-left:2px solid var(--accent2); padding:5px 8px; margin-top:5px;">💡 {sug}</div>' if sug else ''}
                        </div>
                        """,
                        unsafe_allow_html=True
                    )

elif selected_tab == "Settings":
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.8rem; font-weight: 700; font-family:\'Space Grotesk\', sans-serif;">⚙️ Engine Settings & Credentials</div>', unsafe_allow_html=True)
    st.caption("Configure global pipeline variables, adjust LLM provider settings, and manage API keys.")

    st.divider()
    
    # LLM Settings Columns
    c1, c2 = st.columns(2)
    
    with c1:
        st.markdown("#### LLM Engine Integration")
        st.session_state["llm_provider"] = st.selectbox(
            "Select LLM Provider",
            options=["Groq", "Anthropic", "OpenAI"],
            index=["Groq", "Anthropic", "OpenAI"].index(st.session_state["llm_provider"])
        )
        
        st.session_state["llm_model"] = st.text_input(
            "LLM Model Identifier",
            value=st.session_state["llm_model"]
        )
        
        st.caption("Common Models: `llama-3.1-8b-instant` (Groq), `claude-3-5-sonnet-latest` (Anthropic), `gpt-4o-mini` (OpenAI)")
        
    with c2:
        st.markdown("#### API Keys Manager")
        
        st.session_state["groq_api_key"] = st.text_input(
            "Groq API Key",
            value=st.session_state["groq_api_key"],
            type="password"
        )
        
        st.session_state["openai_api_key"] = st.text_input(
            "OpenAI API Key",
            value=st.session_state["openai_api_key"],
            type="password"
        )
        
        st.session_state["anthropic_api_key"] = st.text_input(
            "Anthropic API Key",
            value=st.session_state["anthropic_api_key"],
            type="password"
        )
        
        st.caption("Provide the API key corresponding to your selected LLM Provider.")

    st.divider()
    st.markdown("#### Active API Verification Status")
    
    # Check credentials load status
    import os
    groq_valid = bool(st.session_state["groq_api_key"] or os.environ.get("GROQ_API_KEY"))
    openai_valid = bool(st.session_state["openai_api_key"] or os.environ.get("OPENAI_API_KEY"))
    anthropic_valid = bool(st.session_state["anthropic_api_key"] or os.environ.get("ANTHROPIC_API_KEY"))
    
    stat_col1, stat_col2, stat_col3 = st.columns(3)
    stat_col1.metric("Groq Connection", "Connected ✅" if groq_valid else "Missing ❌")
    stat_col2.metric("OpenAI Connection", "Connected ✅" if openai_valid else "Missing ❌")
    stat_col3.metric("Anthropic Connection", "Connected ✅" if anthropic_valid else "Missing ❌")

    st.divider()
    st.info("💡 API Keys provided in this Settings tab are loaded dynamically into runtime memory and will override credentials configured in files.")

elif selected_tab == "API Docs":
    st.markdown('<div style="margin-top: 20px;"></div>', unsafe_allow_html=True)
    st.markdown('<div style="font-size: 1.8rem; font-weight: 700; font-family:\'Space Grotesk\', sans-serif; margin-bottom:5px;">📖 API & System Documentation</div>', unsafe_allow_html=True)
    st.caption("Learn how CodeLens AI operates, explore backend pipelines, and integrate features programmatically.")
    
    st.divider()
    
    # Architecture markdown
    st.markdown(
        """
        ### System Architecture & Pipeline Stages
        
        CodeLens AI operates as a unified repository code analysis system. Code execution flows sequentially:
        
        ```
        +------------+     +---------------+     +-------------+     +--------------+     +-------------+
        | GitHub URL | --> | ingestion.py  | --> |  parser.py  | --> |  chunker.py  | --> | reviewer.py |
        +------------+     +---------------+     +-------------+     +--------------+     +-------------+
                                 |                      |                   |                    |
                           Clones repo &          Parses code to       Slices AST to        Calls LLMs &
                           applies limits         abstract tree        logical chunks       validates schema
        ```
        
        1. **Ingestion (`ingestion.py`)**: Clones public GitHub repositories, filters python/javascript source files, and caps total files to performance limits.
        2. **AST Parser (`parser.py`)**: Traverses source file codes into abstract syntax tree nodes using Python's core compiler modules.
        3. **Chunker (`utils/chunker.py`)**: Groups class and function nodes into cohesive code chunks fitting inside LLM tokens context window limits.
        4. **Reviewer (`reviewer.py`)**: Invokes selected LLM APIs using systematic prompt instruction schemas, returning validated code review comments.
        
        ---
        
        ### Programmatic Integration
        
        Developers can import and execute the full code review pipeline in custom python scripts:
        
        ```python
        from pipeline import run_pipeline
        
        # Invoke repository analysis
        findings = run_pipeline("https://github.com/pypa/sampleproject")
        
        for item in findings:
            print(f"[{item['severity'].upper()}] File: {item['file']} · Line: {item['line']}")
            print(f"Issue: {item['message']}")
            print(f"Confidence: {item['confidence']}%\\n")
        ```
        
        ---
        
        ### Comment JSON Schema
        
        Review findings returned by the model conform to a strict schema validated before presentation:
        
        ```json
        {
          "comments": [
            {
              "line": 42,
              "category": "security",
              "severity": "critical",
              "message": "Detailed description of the issue.",
              "suggestion": "Concrete code improvement recommendation.",
              "confidence": 95
            }
          ]
        }
        ```
        """,
        unsafe_allow_html=True
    )
