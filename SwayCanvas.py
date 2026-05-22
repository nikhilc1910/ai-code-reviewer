import streamlit.components.v1 as components

def render_sway_canvas():
    """
    Renders the SwayCanvas component in Streamlit.
    Defines explicit inline styles and background fallback logic.
    """
    html_code = """
    <style>
        #sway-canvas {
            position: absolute;
            top: 0;
            left: 0;
            width: 100%;
            height: 100%;
            z-index: 1;
            pointer-events: none;
        }
    </style>
    <canvas id="sway-canvas"></canvas>
    <script>
        const canvas = document.getElementById('sway-canvas');
        const ctx = canvas.getContext('2d');
        
        function resize() {
            canvas.width = window.innerWidth;
            canvas.height = window.innerHeight;
            draw();
        }

        function draw() {
            const img = new Image();
            img.crossOrigin = 'anonymous';
            img.onload = () => {
                const canvasAspect = canvas.width / canvas.height;
                const imgAspect = img.width / img.height;
                let drawWidth = canvas.width;
                let drawHeight = canvas.height;
                let drawX = 0;
                let drawY = 0;

                if (canvasAspect > imgAspect) {
                    drawHeight = canvas.width / imgAspect;
                    drawY = (canvas.height - drawHeight) / 2;
                } else {
                    drawWidth = canvas.height * imgAspect;
                    drawX = (canvas.width - drawWidth) / 2;
                }
                ctx.drawImage(img, drawX, drawY, drawWidth, drawHeight);
            };
            img.onerror = () => {
                const grad = ctx.createLinearGradient(0, 0, 0, canvas.height);
                grad.addColorStop(0, '#0a0e1a');
                grad.addColorStop(0.5, '#111827');
                grad.addColorStop(1, '#0a0e1a');
                ctx.fillStyle = grad;
                ctx.fillRect(0, 0, canvas.width, canvas.height);
            };
            img.src = '/hero-bg.jpg';
        }

        window.addEventListener('resize', resize);
        resize();
    </script>
    """
    components.html(html_code, height=0)
