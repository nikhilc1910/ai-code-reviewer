import streamlit as st
from SwayCanvas import render_sway_canvas

def render_hero_section():
    """
    Renders the HeroSection component with the SwayCanvas background
    and the clean particle title 'The Code Review / Your Team Deserves'.
    No debug or telemetry overlays are rendered here.
    """
    st.markdown(
        """
        <style>
            .hero-container {
                position: relative;
                width: 100%;
                height: 100vh;
                background-color: #030712;
                display: flex;
                align-items: center;
                justify-content: center;
                overflow: hidden;
            }
            .hero-content {
                position: relative;
                z-index: 10;
                text-align: center;
                padding: 2rem;
                max-width: 800px;
            }
            .hero-title {
                font-family: 'Outfit', sans-serif;
                font-size: 3.5rem;
                font-weight: 800;
                line-height: 1.2;
                color: #ffffff;
                margin: 0;
            }
            .hero-title span {
                background: linear-gradient(135deg, #ec4899 10%, #8b5cf6 50%, #06b6d4 90%);
                -webkit-background-clip: text;
                -webkit-text-fill-color: transparent;
            }
            .hero-subtitle {
                font-family: 'Space Grotesk', sans-serif;
                font-size: 1.25rem;
                color: #94a3b8;
                margin-top: 1.5rem;
                line-height: 1.6;
            }
        </style>
        <div class="hero-container">
            <div class="hero-content">
                <h1 class="hero-title">The Code Review / <br><span>Your Team Deserves</span></h1>
                <p class="hero-subtitle">A sleek, high-precision code reviewer powered by agentic intelligence.</p>
            </div>
        </div>
        """,
        unsafe_allow_html=True
    )
    # Render the background canvas elements
    render_sway_canvas()
