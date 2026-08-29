/*
  ShinVPN Interactive Cyberpunk Holographic Radar Map & Node Topology
  Delusional Club Industries Frontend Visualizer
*/

class CyberRadarMap {
  constructor(canvasId) {
    this.canvas = document.getElementById(canvasId);
    if (!this.canvas) return;
    this.ctx = this.canvas.getContext("2d");
    this.nodes = [
      { id: "local", name: "Local Core", flag: "⚡", x: 0.28, y: 0.42, ping: "1.2 ms", active: true },
      { id: "tokyo", name: "Tokyo Alpha-1", flag: "🇯🇵", x: 0.82, y: 0.44, ping: "18 ms", active: false },
      { id: "frankfurt", name: "Frankfurt Vault-7", flag: "🇩🇪", x: 0.52, y: 0.36, ping: "42 ms", active: false },
      { id: "singapore", name: "Singapore Nexus-9", flag: "🇸🇬", x: 0.76, y: 0.62, ping: "28 ms", active: false },
    ];
    this.activeNodeId = "local";
    this.animTime = 0;
    this.arcs = [];
    this.particles = [];

    this.init();
  }

  init() {
    this.resize();
    window.addEventListener("resize", () => this.resize());
    this.animate();
  }

  resize() {
    const rect = this.canvas.parentElement.getBoundingClientRect();
    this.canvas.width = rect.width || 400;
    this.canvas.height = rect.height || 180;
  }

  setActiveNode(nodeId) {
    this.activeNodeId = nodeId;
    this.nodes.forEach((n) => {
      n.active = n.id === nodeId;
    });
  }

  drawGrid() {
    const { width, height } = this.canvas;
    this.ctx.strokeStyle = "rgba(157, 78, 221, 0.08)";
    this.ctx.lineWidth = 1;

    // Latitudes & Longitudes
    for (let x = 0; x < width; x += 40) {
      this.ctx.beginPath();
      this.ctx.moveTo(x, 0);
      this.ctx.lineTo(x, height);
      this.ctx.stroke();
    }
    for (let y = 0; y < height; y += 30) {
      this.ctx.beginPath();
      this.ctx.moveTo(0, y);
      this.ctx.lineTo(width, y);
      this.ctx.stroke();
    }
  }

  drawNodes() {
    const { width, height } = this.canvas;
    const t = this.animTime;

    this.nodes.forEach((node) => {
      const nx = node.x * width;
      const ny = node.y * height;

      // Sonar Pulse Ring for Active Node
      if (node.active) {
        const pulseR = (t * 25) % 35;
        const alpha = Math.max(0, 1 - pulseR / 35);
        this.ctx.beginPath();
        this.ctx.arc(nx, ny, pulseR + 6, 0, Math.PI * 2);
        this.ctx.strokeStyle = `rgba(0, 245, 212, ${alpha})`;
        this.ctx.lineWidth = 1.5;
        this.ctx.stroke();
      }

      // Outer glow
      this.ctx.beginPath();
      this.ctx.arc(nx, ny, node.active ? 8 : 5, 0, Math.PI * 2);
      this.ctx.fillStyle = node.active ? "#00f5d4" : "rgba(157, 78, 221, 0.7)";
      this.ctx.shadowColor = node.active ? "#00f5d4" : "#9d4edd";
      this.ctx.shadowBlur = node.active ? 15 : 6;
      this.ctx.fill();
      this.ctx.shadowBlur = 0;

      // Label & Flag
      this.ctx.fillStyle = node.active ? "#ffffff" : "#94a3b8";
      this.ctx.font = "bold 9px 'JetBrains Mono', monospace";
      this.ctx.textAlign = "center";
      this.ctx.fillText(`${node.flag} ${node.name}`, nx, ny - 12);

      // Ping Badge
      this.ctx.fillStyle = node.active ? "#00f5d4" : "rgba(157, 78, 221, 0.9)";
      this.ctx.font = "8px 'JetBrains Mono', monospace";
      this.ctx.fillText(node.ping, nx, ny + 16);
    });
  }

  drawArcs() {
    const { width, height } = this.canvas;
    const localNode = this.nodes.find((n) => n.id === "local");
    const activeNode = this.nodes.find((n) => n.active && n.id !== "local");

    if (localNode && activeNode) {
      const x1 = localNode.x * width;
      const y1 = localNode.y * height;
      const x2 = activeNode.x * width;
      const y2 = activeNode.y * height;
      const cx = (x1 + x2) / 2;
      const cy = Math.min(y1, y2) - 30;

      // Draw Curved Hop Arc
      this.ctx.beginPath();
      this.ctx.moveTo(x1, y1);
      this.ctx.quadraticCurveTo(cx, cy, x2, y2);
      this.ctx.strokeStyle = "rgba(0, 245, 212, 0.4)";
      this.ctx.lineWidth = 2;
      this.ctx.setLineDash([4, 4]);
      this.ctx.lineDashOffset = -this.animTime * 15;
      this.ctx.stroke();
      this.ctx.setLineDash([]);
    }
  }

  animate() {
    this.animTime += 0.03;
    this.ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

    this.drawGrid();
    this.drawArcs();
    this.drawNodes();

    requestAnimationFrame(() => this.animate());
  }
}

window.CyberRadarMap = CyberRadarMap;
