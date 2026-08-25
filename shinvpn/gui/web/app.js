/*
  ShinVPN Cyberpunk Frontend Logic & Holographic Audio-Visual Engine
  Delusional Club Industries Telemetry & State Control
*/

document.addEventListener("DOMContentLoaded", () => {
  // Elements
  const btnToggle = document.getElementById("btn-toggle-connect");
  const btnText = document.getElementById("btn-text");
  const pulseRing = document.getElementById("pulse-ring");
  const statusBadge = document.getElementById("status-badge");
  const transportBadge = document.getElementById("transport-badge");
  const statusDesc = document.getElementById("status-desc");
  const sessionTimer = document.getElementById("session-timer");

  const valDl = document.getElementById("val-dl");
  const valUl = document.getElementById("val-ul");
  const valPing = document.getElementById("val-ping");
  const barDl = document.getElementById("bar-dl");
  const barUl = document.getElementById("bar-ul");
  const dotPing = document.getElementById("dot-ping");

  const dispVip = document.getElementById("disp-vip");
  const dispRekey = document.getElementById("disp-rekey");
  const dispClientKey = document.getElementById("disp-client-key");
  const btnCopyKey = document.getElementById("btn-copy-key");

  const statDataIn = document.getElementById("stat-data-in");
  const statDataOut = document.getElementById("stat-data-out");
  const statPackets = document.getElementById("stat-packets");

  const btnSpeedtest = document.getElementById("btn-speedtest");
  const stText = document.getElementById("st-text");
  const stResults = document.getElementById("st-results");
  const resDl = document.getElementById("res-dl");
  const resUl = document.getElementById("res-ul");

  const nodeCards = document.querySelectorAll(".node-card");
  const btnCustomToggle = document.getElementById("btn-custom-toggle");
  const customNodeFields = document.getElementById("custom-node-fields");
  const inputCustomHost = document.getElementById("input-custom-host");
  const inputCustomPort = document.getElementById("input-custom-port");
  const transportSelect = document.getElementById("transport-select");

  const chkKillswitch = document.getElementById("chk-killswitch");
  const chkDns = document.getElementById("chk-dns");
  const chkSysproxy = document.getElementById("chk-sysproxy");
  const consoleBox = document.getElementById("console-box");
  const btnClearLogs = document.getElementById("btn-clear-logs");

  const btnAudioToggle = document.getElementById("btn-audio-toggle");
  const audioIcon = document.getElementById("audio-icon");
  const audioStatus = document.getElementById("audio-status");

  let isConnected = false;
  let isSpeedtesting = false;
  let audioEnabled = true;
  let timerInterval = null;
  let connectionStartTime = null;
  let selectedEndpoint = "127.0.0.1:51820";
  let isCustomNode = false;

  // 1. Web Audio Synth Effects
  let audioCtx = null;
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioContext();
    }
    if (audioCtx.state === "suspended") {
      audioCtx.resume();
    }
    return audioCtx;
  }

  function playSynth(type) {
    if (!audioEnabled) return;
    try {
      const ctx = getAudioContext();
      const now = ctx.currentTime;
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === "connect") {
        // Upbeat cyberpunk chime (Arpeggio: 440 -> 660 -> 880 -> 1320 Hz)
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
        osc.frequency.exponentialRampToValueAtTime(1320, now + 0.25);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc.start(now);
        osc.stop(now + 0.5);
      } else if (type === "disconnect") {
        // Descending low-pass filter sweep (880 -> 220 Hz)
        osc.type = "sine";
        osc.frequency.setValueAtTime(660, now);
        osc.frequency.exponentialRampToValueAtTime(180, now + 0.35);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      } else if (type === "speedtest") {
        // Sonar Ping
        osc.type = "sine";
        osc.frequency.setValueAtTime(1200, now);
        osc.frequency.exponentialRampToValueAtTime(1800, now + 0.08);
        gain.gain.setValueAtTime(0.1, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.3);
        osc.start(now);
        osc.stop(now + 0.3);
      } else if (type === "click") {
        osc.type = "triangle";
        osc.frequency.setValueAtTime(900, now);
        gain.gain.setValueAtTime(0.04, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.05);
        osc.start(now);
        osc.stop(now + 0.05);
      }
    } catch (e) {}
  }

  btnAudioToggle.addEventListener("click", () => {
    audioEnabled = !audioEnabled;
    audioIcon.textContent = audioEnabled ? "🔊" : "🔇";
    audioStatus.textContent = audioEnabled ? "ON" : "OFF";
    btnAudioToggle.style.opacity = audioEnabled ? "1" : "0.5";
    playSynth("click");
  });

  // 2. Holographic Background Canvas Animation
  const canvas = document.getElementById("bg-canvas");
  const cctx = canvas.getContext("2d");
  let particles = [];

  function resizeCanvas() {
    canvas.width = window.innerWidth;
    canvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  for (let i = 0; i < 40; i++) {
    particles.push({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - 0.5) * 0.4,
      vy: (Math.random() - 0.5) * 0.4,
      size: Math.random() * 2 + 1,
      color: Math.random() > 0.5 ? "rgba(157, 78, 221, " : "rgba(0, 245, 212, ",
      alpha: Math.random() * 0.5 + 0.2,
    });
  }

  function drawBackground() {
    cctx.clearRect(0, 0, canvas.width, canvas.height);
    for (let p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = canvas.width;
      if (p.x > canvas.width) p.x = 0;
      if (p.y < 0) p.y = canvas.height;
      if (p.y > canvas.height) p.y = 0;

      cctx.beginPath();
      cctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      cctx.fillStyle = p.color + p.alpha + ")";
      cctx.fill();
    }
    requestAnimationFrame(drawBackground);
  }
  drawBackground();

  // 3. Initialize Chart.js Live Graph
  const chartCanvas = document.getElementById("traffic-chart").getContext("2d");
  const chartLabels = Array(20).fill("");
  const dlData = Array(20).fill(0);
  const ulData = Array(20).fill(0);

  const trafficChart = new Chart(chartCanvas, {
    type: "line",
    data: {
      labels: chartLabels,
      datasets: [
        {
          label: "DL (Mbps)",
          data: dlData,
          borderColor: "#00f5d4",
          backgroundColor: "rgba(0, 245, 212, 0.12)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.35,
          fill: true,
        },
        {
          label: "UL (Mbps)",
          data: ulData,
          borderColor: "#9d4edd",
          backgroundColor: "rgba(157, 78, 221, 0.12)",
          borderWidth: 2,
          pointRadius: 0,
          tension: 0.35,
          fill: true,
        },
      ],
    },
    options: {
      responsive: true,
      maintainAspectRatio: false,
      animation: false,
      plugins: {
        legend: {
          display: true,
          position: "top",
          labels: {
            boxWidth: 10,
            color: "#94a3b8",
            font: { size: 9, family: "JetBrains Mono" },
          },
        },
      },
      scales: {
        x: { display: false },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: {
            color: "#94a3b8",
            font: { size: 9, family: "JetBrains Mono" },
          },
        },
      },
    },
  });

  function logConsole(msg, level = "info") {
    const entry = document.createElement("div");
    entry.className = `log-entry ${level}`;
    const time = new Date().toTimeString().split(" ")[0];
    entry.textContent = `[${time}] ${msg}`;
    consoleBox.appendChild(entry);
    consoleBox.scrollTop = consoleBox.scrollHeight;
  }

  btnClearLogs.addEventListener("click", () => {
    consoleBox.innerHTML = "";
    logConsole("Console cleared.", "system");
  });

  // 4. WebSocket Telemetry Connection
  let ws = null;
  function connectWebSocket() {
    const loc = window.location;
    const wsUri = (loc.protocol === "https:" ? "wss://" : "ws://") + loc.host + "/ws/telemetry";

    ws = new WebSocket(wsUri);

    ws.onopen = () => {
      logConsole("Connected to ShinVPN Daemon Engine", "system");
      fetchInitialState();
    };

    ws.onmessage = (event) => {
      try {
        const msg = JSON.parse(event.data);
        handleTelemetryUpdate(msg);
      } catch (err) {}
    };

    ws.onclose = () => {
      logConsole("Lost connection to daemon. Retrying...", "warn");
      setTimeout(connectWebSocket, 2000);
    };
  }

  async function fetchInitialState() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (data.client_key) {
        dispClientKey.textContent = data.client_key;
      }
      handleTelemetryUpdate(data);
    } catch (e) {}
  }

  function formatBytes(bytes) {
    if (!bytes || bytes === 0) return "0.0 KB";
    const k = 1024;
    const sizes = ["B", "KB", "MB", "GB", "TB"];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(2)) + " " + sizes[i];
  }

  function handleTelemetryUpdate(data) {
    if (!data) return;

    if (data.state === "CONNECTED") {
      if (!isConnected) {
        setConnectedState(true);
        playSynth("connect");
      }
      dispVip.textContent = data.allocated_vip || "10.8.0.2";
      valPing.textContent = (data.rtt_ms || 0.0).toFixed(1);

      if (data.rtt_ms < 30) {
        dotPing.style.background = "#10b981";
        dotPing.style.boxShadow = "0 0 6px #10b981";
      } else if (data.rtt_ms < 80) {
        dotPing.style.background = "#f59e0b";
        dotPing.style.boxShadow = "0 0 6px #f59e0b";
      } else {
        dotPing.style.background = "#ff0055";
        dotPing.style.boxShadow = "0 0 6px #ff0055";
      }

      const dlMbps = ((data.speed_rx_bps || 0) / 1000000).toFixed(2);
      const ulMbps = ((data.speed_tx_bps || 0) / 1000000).toFixed(2);
      valDl.textContent = dlMbps;
      valUl.textContent = ulMbps;

      // Update Mini Progress Bars (capped at 50 Mbps max visual width)
      barDl.style.width = Math.min(100, (parseFloat(dlMbps) / 50) * 100) + "%";
      barUl.style.width = Math.min(100, (parseFloat(ulMbps) / 50) * 100) + "%";

      // Session stats
      statDataIn.textContent = formatBytes(data.bytes_rx);
      statDataOut.textContent = formatBytes(data.bytes_tx);
      statPackets.textContent = `${data.packets_tx || 0} / ${data.packets_rx || 0}`;

      if (data.rekey_remaining_bytes) {
        dispRekey.textContent = Math.round(data.rekey_remaining_bytes / (1024 * 1024)) + " MB";
      }

      // Update Chart
      dlData.shift();
      dlData.push(parseFloat(dlMbps));
      ulData.shift();
      ulData.push(parseFloat(ulMbps));
      trafficChart.update();

      if (data.connected_time && !connectionStartTime) {
        connectionStartTime = data.connected_time;
        startTimer();
      }
    } else if (data.state === "CONNECTING" || data.state === "AUTHENTICATING") {
      statusBadge.textContent = data.state;
      statusBadge.className = "badge status-badge";
      statusDesc.textContent = "NEGOTIATING X25519 TUNNEL...";
      btnText.textContent = "WAIT...";
    } else {
      if (isConnected) {
        setConnectedState(false);
        playSynth("disconnect");
      }
      if (data.last_error) {
        statusDesc.textContent = "ERROR: " + data.last_error;
        logConsole("Tunnel Error: " + data.last_error, "error");
      } else {
        statusDesc.textContent = "SYSTEM IDLE & READY";
      }
    }
  }

  function setConnectedState(connected) {
    isConnected = connected;
    if (connected) {
      pulseRing.classList.add("connected");
      btnToggle.classList.add("connected");
      statusBadge.textContent = "CONNECTED";
      statusBadge.classList.add("connected");
      statusDesc.textContent = "SECURE & ENCRYPTED TUNNEL ACTIVE";
      btnText.textContent = "DISCONNECT";
    } else {
      pulseRing.classList.remove("connected");
      btnToggle.classList.remove("connected");
      statusBadge.textContent = "DISCONNECTED";
      statusBadge.classList.remove("connected");
      btnText.textContent = "CONNECT";
      valDl.textContent = "0.00";
      valUl.textContent = "0.00";
      valPing.textContent = "0.0";
      barDl.style.width = "0%";
      barUl.style.width = "0%";
      dispVip.textContent = "0.0.0.0";
      stopTimer();
    }
  }

  function startTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = setInterval(() => {
      if (!connectionStartTime) return;
      const elapsed = Math.floor(Date.now() / 1000 - connectionStartTime);
      const hrs = String(Math.floor(elapsed / 3600)).padStart(2, "0");
      const mins = String(Math.floor((elapsed % 3600) / 60)).padStart(2, "0");
      const secs = String(elapsed % 60).padStart(2, "0");
      sessionTimer.textContent = `${hrs}:${mins}:${secs}`;
    }, 1000);
  }

  function stopTimer() {
    if (timerInterval) clearInterval(timerInterval);
    timerInterval = null;
    connectionStartTime = null;
    sessionTimer.textContent = "00:00:00";
  }

  // 5. Node Selection
  nodeCards.forEach((card) => {
    card.addEventListener("click", () => {
      playSynth("click");
      nodeCards.forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      selectedEndpoint = card.dataset.endpoint;
      isCustomNode = false;
      customNodeFields.style.display = "none";
      logConsole(`Selected Node: ${card.querySelector(".node-name").textContent} (${selectedEndpoint})`, "info");
    });
  });

  btnCustomToggle.addEventListener("click", () => {
    playSynth("click");
    isCustomNode = !isCustomNode;
    customNodeFields.style.display = isCustomNode ? "block" : "none";
    if (isCustomNode) {
      nodeCards.forEach((c) => c.classList.remove("active"));
    }
  });

  transportSelect.addEventListener("change", () => {
    playSynth("click");
    transportBadge.textContent =
      transportSelect.value === "udp" ? "⚡ UDP HIGH-SPEED" : "🛡️ STEALTH WSS";
  });

  // 6. Connect / Disconnect Action
  async function handleConnectToggle() {
    playSynth("click");
    if (isConnected) {
      logConsole("Requesting graceful tunnel disconnect...", "info");
      btnText.textContent = "CLOSING...";
      try {
        await fetch("/api/disconnect", { method: "POST" });
      } catch (err) {
        logConsole("Disconnect request failed: " + err.message, "error");
      }
    } else {
      let host = "127.0.0.1";
      let port = 51820;

      if (isCustomNode) {
        host = inputCustomHost.value.trim() || "127.0.0.1";
        port = parseInt(inputCustomPort.value) || 51820;
      } else {
        const parts = selectedEndpoint.split(":");
        host = parts[0];
        port = parseInt(parts[1]);
      }

      statusBadge.textContent = "CONNECTING...";
      statusBadge.className = "badge status-badge";
      statusDesc.textContent = "CONNECTING TO " + host.toUpperCase() + "...";
      btnText.textContent = "WAIT...";

      const payload = {
        server_host: host,
        server_port: port,
        transport_type: transportSelect.value,
        enable_killswitch: chkKillswitch.checked,
        enable_dns_shield: chkDns.checked,
        enable_system_proxy: chkSysproxy.checked,
      };

      logConsole(`Initiating ShinVPN tunnel to ${host}:${port} (${payload.transport_type.toUpperCase()})...`, "info");
      if (host !== "127.0.0.1" && host !== "localhost") {
        logConsole(`Note: Connecting to remote VPS node. For instant zero-setup local testing, select 'Local Core Node' (⚡).`, "system");
      }

      try {
        const res = await fetch("/api/connect", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(payload),
        });
        const result = await res.json();
        if (!result.success) {
          logConsole("Connect failure: " + result.error, "error");
          btnText.textContent = "CONNECT";
          statusDesc.textContent = "ERROR: " + result.error;
        }
      } catch (err) {
        logConsole("Connect request error: " + err.message, "error");
        btnText.textContent = "CONNECT";
        statusDesc.textContent = "CONNECTION ERROR";
      }
    }
  }

  btnToggle.addEventListener("click", (e) => {
    e.stopPropagation();
    handleConnectToggle();
  });

  const connectionHub = document.querySelector(".connection-hub");
  if (connectionHub) {
    connectionHub.addEventListener("click", handleConnectToggle);
  }

  // 7. Speedtest Action
  btnSpeedtest.addEventListener("click", async () => {
    if (!isConnected) {
      logConsole("Connect to ShinVPN first before running speedtest.", "warn");
      return;
    }
    if (isSpeedtesting) return;

    isSpeedtesting = true;
    btnSpeedtest.classList.add("running");
    stText.textContent = "TESTING ENCRYPTED TUNNEL...";
    stResults.style.display = "none";
    playSynth("speedtest");
    logConsole("🚀 Starting encrypted throughput benchmark probe...", "system");

    try {
      const res = await fetch("/api/speedtest", { method: "POST" });
      const data = await res.json();
      if (data.success) {
        resDl.textContent = data.download_mbps;
        resUl.textContent = data.upload_mbps;
        stResults.style.display = "flex";
        logConsole(`✔ Benchmark Complete! Down: ${data.download_mbps} Mbps | Up: ${data.upload_mbps} Mbps | Latency: ${data.latency_ms} ms`, "info");
      } else {
        logConsole("Speedtest error: " + data.error, "error");
      }
    } catch (e) {
      logConsole("Speedtest request failed: " + e.message, "error");
    } finally {
      isSpeedtesting = false;
      btnSpeedtest.classList.remove("running");
      stText.textContent = "RUN TUNNEL SPEEDTEST";
    }
  });

  // 8. Copy Public Key Action
  btnCopyKey.addEventListener("click", () => {
    playSynth("click");
    const key = dispClientKey.textContent;
    if (key && key !== "Loading...") {
      navigator.clipboard.writeText(key).then(() => {
        const orig = btnCopyKey.textContent;
        btnCopyKey.textContent = "✔ COPIED!";
        logConsole("Client public key copied to clipboard.", "info");
        setTimeout(() => { btnCopyKey.textContent = orig; }, 1500);
      });
    }
  });

  connectWebSocket();
});
