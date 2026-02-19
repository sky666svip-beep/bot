/**
 * Handwriting Recognition Logic
 * Handles Canvas drawing and API communication
 */

const HandwritingManager = {
    canvas: null,
    ctx: null,
    isDrawing: false,
    lastX: 0,
    lastY: 0,

    init: function(canvasId) {
        this.canvas = document.getElementById(canvasId);
        if (!this.canvas) return;
        
        this.ctx = this.canvas.getContext('2d');
        
        this.ctx = this.canvas.getContext('2d');
        
        // Dynamic Resize to match container
        this.resizeCanvas();
        
        // Events
        this.canvas.addEventListener('mousedown', (e) => this.startDrawing(e));
        this.canvas.addEventListener('mousemove', (e) => this.draw(e));
        this.canvas.addEventListener('mouseup', () => this.stopDrawing());
        this.canvas.addEventListener('mouseout', () => this.stopDrawing());
        
        // Touch support
        this.canvas.addEventListener('touchstart', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousedown', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        });
        
        this.canvas.addEventListener('touchmove', (e) => {
            e.preventDefault();
            const touch = e.touches[0];
            const mouseEvent = new MouseEvent('mousemove', {
                clientX: touch.clientX,
                clientY: touch.clientY
            });
            this.canvas.dispatchEvent(mouseEvent);
        });
        
        this.canvas.addEventListener('touchend', () => {
             const mouseEvent = new MouseEvent('mouseup', {});
             this.canvas.dispatchEvent(mouseEvent);
        });
    },

    startDrawing: function(e) {
        this.isDrawing = true;
        [this.lastX, this.lastY] = this.getCoordinates(e);
    },

    draw: function(e) {
        if (!this.isDrawing) return;
        
        const [x, y] = this.getCoordinates(e);
        
        // Styles are set in clearCanvas() / resizeCanvas() globally
        // But we ensure them here just in case
        this.ctx.lineWidth = 6; 
        this.ctx.strokeStyle = '#000000';
        
        this.ctx.beginPath();
        this.ctx.moveTo(this.lastX, this.lastY);
        this.ctx.lineTo(x, y);
        this.ctx.stroke();
        
        [this.lastX, this.lastY] = [x, y];
    },

    stopDrawing: function() {
        this.isDrawing = false;
    },

    getCoordinates: function(e) {
        const rect = this.canvas.getBoundingClientRect();
        return [
            e.clientX - rect.left,
            e.clientY - rect.top
        ];
    },

    resizeCanvas: function() {
        if (!this.canvas) return;
        // Match internal resolution to display size
        this.canvas.width = this.canvas.offsetWidth;
        this.canvas.height = this.canvas.offsetHeight;
        this.clearCanvas();
    },

    clearCanvas: function() {
        if (!this.ctx) return;
        this.ctx.fillStyle = "#ffffff";
        this.ctx.fillRect(0, 0, this.canvas.width, this.canvas.height);
        
        // Reset context styles after resize/clear
        this.ctx.lineCap = 'round';
        this.ctx.lineJoin = 'round';
        this.ctx.strokeStyle = '#000000';
        this.ctx.lineWidth = 6; // Thinner line for large canvas (was 15)
    },

    recognize: async function() {
        const imageData = this.canvas.toDataURL('image/png');
        const resultArea = document.getElementById('recognitionResult');
        
        if(resultArea) {
             resultArea.innerHTML = '<span class="spinner-border spinner-border-sm text-primary" role="status"></span> 识别中...';
        }

        try {
            const response = await fetch('/api/handwriting/recognize', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ image: imageData })
            });
            
            const result = await response.json();
            
            if (result.success) {
                this.displayResults(result.data);
            } else {
                if(resultArea) resultArea.innerHTML = `<span class="text-danger">Error: ${result.message}</span>`;
            }
        } catch (error) {
            console.error('Error:', error);
            if(resultArea) resultArea.innerHTML = `<span class="text-danger">网络错误</span>`;
        }
    },

    displayResults: function(data) {
        const resultArea = document.getElementById('recognitionResult');
        if (!resultArea) return;
        
        if (data.length === 0) {
            resultArea.innerHTML = "未识别到字符";
            return;
        }

        // Top 1
        const top = data[0];
        let html = `<div class="d-flex align-items-center justify-content-center gap-3">`;
        
        // Large detailed display for top 1
        html += `
            <div class="text-center">
                <div class="display-4 fw-bold text-primary">${top.char}</div>
                <div class="small text-muted">${(top.confidence * 100).toFixed(1)}%</div>
            </div>
        `;
        
        // Others
        if (data.length > 1) {
             html += `<div class="border-start ps-3"><div class="small text-muted mb-1">候选:</div>`;
             for(let i=1; i<data.length; i++) {
                 html += `<span class="badge bg-light text-dark border me-1">${data[i].char} <span class="text-muted" style="font-size:0.7em">${(data[i].confidence * 100).toFixed(0)}%</span></span>`;
             }
             html += `</div>`;
        }
        
        html += `</div>`;
        resultArea.innerHTML = html;
        
        // If high confidence, auto-fill search, but maybe user just wants to play
        // document.getElementById('searchInput').value = top.char; 
    }
};

// Auto init when modal opens
document.addEventListener('DOMContentLoaded', () => {
    const handwritingModal = document.getElementById('handwritingModal');
    if(handwritingModal) {
        handwritingModal.addEventListener('shown.bs.modal', function () {
            HandwritingManager.init('handwritingCanvas');
        });
    }
});
