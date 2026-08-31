/*
  ShinVPN Cyberpunk Frontend Master Logic & Multi-Feature Hub
  Delusional Club Industries Application Control System
*/

document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const navButtons = document.querySelectorAll(".nav-btn");
  const tabContents = document.querySelectorAll(".tab-content");

  // Core Connection Elements
  const btnToggle = document.getElementById("btn-toggle-connect");
  const btnText = document.getElementById("btn-text");
  const pulseRing = document.getElementById("pulse-ring");
  const statusBadge = document.getElementById("status-badge");
  const transportBadge = document.getElementById("transport-badge");
  const statusDesc = document.getElementById("status-desc");
  const sessionTimer = document.getElementById("session-timer");

  // Metric Displays
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

  // Speedtest
  const btnSpeedtest = document.getElementById("btn-speedtest");
  const stText = document.getElementById("st-text");
  const stResults = document.getElementById("st-results");
  const resDl = document.getElementById("res-dl");
  const resUl = document.getElementById("res-ul");

  // CyberShield AdBlocker
  const badgeAdblock = document.getElementById("badge-adblock");
  const valAdsBlocked = document.getElementById("val-ads-blocked");
  const csStatBlocked = document.getElementById("cs-stat-blocked");
  const csStatRecent = document.getElementById("cs-stat-recent");
  const chkAdblockEnable = document.getElementById("chk-adblock-enable");

  // Double VPN / Multi-Hop
  const chkMultihopEnable = document.getElementById("chk-multihop-enable");
  const selHopEntry = document.getElementById("sel-hop-entry");
  const selHopExit = document.getElementById("sel-hop-exit");

  // Split Tunnel Process Matrix
  const procListContainer = document.getElementById("proc-list-container");
  const btnRefreshProcs = document.getElementById("btn-refresh-procs");
  const btnSaveSplitRules = document.getElementById("btn-save-split-rules");

  // Mobile QR Hub
  const profileGridContainer = document.getElementById("profile-grid-container");
  const btnAddProfile = document.getElementById("btn-add-profile");
  const qrDisplayBox = document.getElementById("qr-display-box");
  const qrDeviceTitle = document.getElementById("qr-device-title");
  const qrSvgWrapper = document.getElementById("qr-svg-wrapper");
  const btnCopyWireguardConf = document.getElementById("btn-copy-wireguard-conf");
  let currentActiveWireguardConf = "";

  // Nodes & Transport
  const nodeCards = document.querySelectorAll(".node-card");
  const btnCustomToggle = document.getElementById("btn-custom-toggle");
  const customNodeFields = document.getElementById("custom-node-fields");
  const inputCustomHost = document.getElementById("input-custom-host");
  const inputCustomPort = document.getElementById("input-custom-port");
  const transportSelect = document.getElementById("transport-select");

  // Toggles & Terminal
  const chkKillswitch = document.getElementById("chk-killswitch");
  const chkDns = document.getElementById("chk-dns");
  const chkSysproxy = document.getElementById("chk-sysproxy");
  const consoleBox = document.getElementById("console-box");
  const btnClearLogs = document.getElementById("btn-clear-logs");

  // Audio Toggle
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

  // 1. Initialize Holographic Radar Map
  let radarMap = null;
  if (window.CyberRadarMap) {
    radarMap = new window.CyberRadarMap("radar-canvas");
  }

  // 2. Tab Navigation
  navButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      playSynth("click");
      const targetTab = btn.dataset.tab;
      navButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");

      tabContents.forEach((content) => {
        if (content.id === `tab-${targetTab}`) {
          content.style.display = "block";
        } else {
          content.style.display = "none";
        }
      });

      if (targetTab === "splittunnel") loadProcesses();
      if (targetTab === "mobileqr") loadProfiles();
      if (targetTab === "cybershield") fetchAdblockStats();
    });
  });

  // 3. Web Audio Synthesizer
  let audioCtx = null;
  function getAudioContext() {
    if (!audioCtx) {
      const AudioContext = window.AudioContext || window.webkitAudioContext;
      audioCtx = new AudioContext();
    }
    if (audioCtx.state === "suspended") audioCtx.resume();
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
        osc.type = "sawtooth";
        osc.frequency.setValueAtTime(440, now);
        osc.frequency.exponentialRampToValueAtTime(880, now + 0.12);
        osc.frequency.exponentialRampToValueAtTime(1320, now + 0.25);
        gain.gain.setValueAtTime(0.12, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.5);
        osc.start(now);
        osc.stop(now + 0.5);
      } else if (type === "disconnect") {
        osc.type = "sine";
        osc.frequency.setValueAtTime(660, now);
        osc.frequency.exponentialRampToValueAtTime(180, now + 0.35);
        gain.gain.setValueAtTime(0.15, now);
        gain.gain.exponentialRampToValueAtTime(0.001, now + 0.4);
        osc.start(now);
        osc.stop(now + 0.4);
      } else if (type === "speedtest") {
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

  // 4. Background Canvas Particles
  const bgCanvas = document.getElementById("bg-canvas");
  const cctx = bgCanvas.getContext("2d");
  let particles = [];

  function resizeCanvas() {
    bgCanvas.width = window.innerWidth;
    bgCanvas.height = window.innerHeight;
  }
  window.addEventListener("resize", resizeCanvas);
  resizeCanvas();

  for (let i = 0; i < 35; i++) {
    particles.push({
      x: Math.random() * window.innerWidth,
      y: Math.random() * window.innerHeight,
      vx: (Math.random() - 0.5) * 0.3,
      vy: (Math.random() - 0.5) * 0.3,
      size: Math.random() * 2 + 1,
      color: Math.random() > 0.5 ? "rgba(157, 78, 221, " : "rgba(0, 245, 212, ",
      alpha: Math.random() * 0.4 + 0.2,
    });
  }

  function drawBackground() {
    cctx.clearRect(0, 0, bgCanvas.width, bgCanvas.height);
    for (let p of particles) {
      p.x += p.vx;
      p.y += p.vy;
      if (p.x < 0) p.x = bgCanvas.width;
      if (p.x > bgCanvas.width) p.x = 0;
      if (p.y < 0) p.y = bgCanvas.height;
      if (p.y > bgCanvas.height) p.y = 0;

      cctx.beginPath();
      cctx.arc(p.x, p.y, p.size, 0, Math.PI * 2);
      cctx.fillStyle = p.color + p.alpha + ")";
      cctx.fill();
    }
    requestAnimationFrame(drawBackground);
  }
  drawBackground();

  // 5. Chart.js Throughput Graph
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
          labels: { boxWidth: 10, color: "#94a3b8", font: { size: 9, family: "JetBrains Mono" } },
        },
      },
      scales: {
        x: { display: false },
        y: {
          beginAtZero: true,
          grid: { color: "rgba(255, 255, 255, 0.04)" },
          ticks: { color: "#94a3b8", font: { size: 9, family: "JetBrains Mono" } },
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

  // 6. WebSocket Telemetry
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
      setTimeout(connectWebSocket, 2000);
    };
  }

  async function fetchInitialState() {
    try {
      const res = await fetch("/api/status");
      const data = await res.json();
      if (data.client_key) dispClientKey.textContent = data.client_key;
      handleTelemetryUpdate(data);
      fetchAdblockStats();
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

      barDl.style.width = Math.min(100, (parseFloat(dlMbps) / 50) * 100) + "%";
      barUl.style.width = Math.min(100, (parseFloat(ulMbps) / 50) * 100) + "%";

      statDataIn.textContent = formatBytes(data.bytes_rx);
      statDataOut.textContent = formatBytes(data.bytes_tx);
      statPackets.textContent = `${data.packets_tx || 0} / ${data.packets_rx || 0}`;

      if (data.rekey_remaining_bytes) {
        dispRekey.textContent = Math.round(data.rekey_remaining_bytes / (1024 * 1024)) + " MB";
      }

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

  // 7. Node Selection & Radar Integration
  nodeCards.forEach((card) => {
    card.addEventListener("click", () => {
      playSynth("click");
      nodeCards.forEach((c) => c.classList.remove("active"));
      card.classList.add("active");
      selectedEndpoint = card.dataset.endpoint;
      const nodeId = card.dataset.id || "local";
      if (radarMap) radarMap.setActiveNode(nodeId);

      isCustomNode = false;
      customNodeFields.style.display = "none";
      logConsole(`Selected Node: ${card.querySelector(".node-name").textContent} (${selectedEndpoint})`, "info");
    });
  });

  btnCustomToggle.addEventListener("click", () => {
    playSynth("click");
    isCustomNode = !isCustomNode;
    customNodeFields.style.display = isCustomNode ? "block" : "none";
    if (isCustomNode) nodeCards.forEach((c) => c.classList.remove("active"));
  });

  transportSelect.addEventListener("change", () => {
    playSynth("click");
    transportBadge.textContent =
      transportSelect.value === "udp" ? "⚡ UDP HIGH-SPEED" : "🛡️ STEALTH WSS";
  });

  // 8. Connect / Disconnect Action
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

  const connectionHub = document.getElementById("conn-hub-trigger");
  if (connectionHub) connectionHub.addEventListener("click", handleConnectToggle);

  // 9. Speedtest Action
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
        logConsole(`✔ Benchmark: Down: ${data.download_mbps} Mbps | Up: ${data.upload_mbps} Mbps | RTT: ${data.latency_ms} ms`, "info");
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

  // 10. CyberShield AdBlocker Integration
  async function fetchAdblockStats() {
    try {
      const res = await fetch("/api/adblock/stats");
      const data = await res.json();
      valAdsBlocked.textContent = data.blocked_queries_count;
      csStatBlocked.textContent = data.blocked_queries_count;
      if (data.last_blocked_domain) csStatRecent.textContent = data.last_blocked_domain;
      chkAdblockEnable.checked = data.enabled;
    } catch (e) {}
  }

  chkAdblockEnable.addEventListener("change", async () => {
    playSynth("click");
    try {
      const res = await fetch("/api/adblock/toggle", { method: "POST" });
      const data = await res.json();
      logConsole(`CyberShield AdBlocker ${data.enabled ? "ACTIVATED" : "DISABLED"}`, "info");
      fetchAdblockStats();
    } catch (e) {}
  });

  // 11. Multi-Hop Double VPN
  chkMultihopEnable.addEventListener("change", async () => {
    playSynth("click");
    const payload = {
      enabled: chkMultihopEnable.checked,
      entry_node_id: selHopEntry.value,
      exit_node_id: selHopExit.value,
    };
    try {
      await fetch("/api/multihop/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      logConsole(`Double VPN Onion Routing: ${payload.enabled ? "ENABLED (" + payload.entry_node_id.toUpperCase() + " -> " + payload.exit_node_id.toUpperCase() + ")" : "DISABLED"}`, "system");
    } catch (e) {}
  });

  // 12. Split Tunnel Process Matrix
  async function loadProcesses() {
    try {
      procListContainer.innerHTML = "<div class='proc-item-loading'>Scanning running desktop applications...</div>";
      const res = await fetch("/api/processes");
      const data = await res.json();
      procListContainer.innerHTML = "";

      data.applications.forEach((app) => {
        const item = document.createElement("div");
        item.className = "proc-item";
        item.innerHTML = `
          <div class="proc-info">
            <span class="proc-icon">${app.icon}</span>
            <b>${app.display_name}</b>
            <span class="proc-cat">${app.category}</span>
          </div>
          <label class="switch">
            <input type="checkbox" class="chk-proc-route" data-proc="${app.process_name}" ${app.is_tunneled ? "checked" : ""}>
            <span class="slider"></span>
          </label>
        `;
        procListContainer.appendChild(item);
      });
    } catch (e) {
      procListContainer.innerHTML = "<div class='proc-item-loading'>Failed to scan processes.</div>";
    }
  }

  btnRefreshProcs.addEventListener("click", () => {
    playSynth("click");
    loadProcesses();
  });

  btnSaveSplitRules.addEventListener("click", async () => {
    playSynth("click");
    const checkedProcs = [];
    document.querySelectorAll(".chk-proc-route:checked").forEach((chk) => {
      checkedProcs.push(chk.dataset.proc);
    });
    const mode = document.querySelector('input[name="split-mode"]:checked').value;
    const payload = { enabled: true, mode: mode, selected_apps: checkedProcs };

    try {
      const res = await fetch("/api/processes/rules", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      });
      const data = await res.json();
      logConsole(`✔ Split Tunnel Rules saved (${data.selected_count} apps in ${data.mode} mode)`, "info");
    } catch (e) {}
  });

  // 13. Mobile QR Profiles Hub
  async function loadProfiles() {
    try {
      const res = await fetch("/api/profiles");
      const data = await res.json();
      profileGridContainer.innerHTML = "";

      data.profiles.forEach((prof) => {
        const card = document.createElement("div");
        card.className = "profile-card";
        const icon = prof.device_type === "phone" ? "📱" : prof.device_type === "laptop" ? "💻" : "🖥️";
        card.innerHTML = `
          <div>
            <span class="p-name">${icon} ${prof.name}</span>
            <span class="p-vip">VIP: ${prof.allocated_vip}</span>
          </div>
          <button class="btn-copy-key btn-view-qr" data-id="${prof.id}" data-name="${prof.name}">VIEW QR</button>
        `;
        profileGridContainer.appendChild(card);
      });

      document.querySelectorAll(".btn-view-qr").forEach((btn) => {
        btn.addEventListener("click", async () => {
          playSynth("click");
          const profId = btn.dataset.id;
          const profName = btn.dataset.name;
          const qrRes = await fetch(`/api/profiles/${profId}/qr`);
          const qrData = await qrRes.json();

          qrDeviceTitle.textContent = `${profName} — WireGuard QR Code`;
          qrSvgWrapper.innerHTML = qrData.svg;
          currentActiveWireguardConf = qrData.config;
          qrDisplayBox.style.display = "flex";
          logConsole(`Generated Mobile QR Import for ${profName}`, "info");
        });
      });
    } catch (e) {}
  }

  btnAddProfile.addEventListener("click", async () => {
    playSynth("click");
    const name = prompt("Enter new device profile name (e.g. iPhone-15):", "iPhone-15");
    if (!name) return;

    try {
      const res = await fetch("/api/profiles/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ name: name, device_type: "phone" }),
      });
      const data = await res.json();
      if (data.success) {
        logConsole(`Provisioned device profile '${name}' with VIP ${data.profile.allocated_vip}`, "system");
        loadProfiles();
      }
    } catch (e) {}
  });

  btnCopyWireguardConf.addEventListener("click", () => {
    playSynth("click");
    if (currentActiveWireguardConf) {
      navigator.clipboard.writeText(currentActiveWireguardConf).then(() => {
        const orig = btnCopyWireguardConf.textContent;
        btnCopyWireguardConf.textContent = "✔ COPIED TO CLIPBOARD!";
        setTimeout(() => { btnCopyWireguardConf.textContent = orig; }, 1500);
      });
    }
  });

  // 14. Copy Client Public Key
  btnCopyKey.addEventListener("click", () => {
    playSynth("click");
    const key = dispClientKey.textContent;
    if (key && key !== "Loading...") {
      navigator.clipboard.writeText(key).then(() => {
        const orig = btnCopyKey.textContent;
        btnCopyKey.textContent = "✔ COPIED!";
        setTimeout(() => { btnCopyKey.textContent = orig; }, 1500);
      });
    }
  });

  // 15. Quick Preset Bar Controls
  const presetButtons = document.querySelectorAll(".btn-preset");
  presetButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      playSynth("click");
      const presetKey = btn.dataset.preset;
      presetButtons.forEach((b) => b.classList.remove("active"));
      btn.classList.add("active");
      try {
        const res = await fetch(`/api/presets/${presetKey}`, { method: "POST" });
        const data = await res.json();
        if (data.success) {
          logConsole(`⚡ Activated Preset: ${presetKey} (${data.mode} mode - ${data.apps.length} apps)`, "system");
        }
      } catch (e) {}
    });
  });

  // 16. Double VPN Optimal Path Calculation
  const btnAutoHop = document.getElementById("btn-auto-hop");
  if (btnAutoHop) {
    btnAutoHop.addEventListener("click", async () => {
      playSynth("speedtest");
      logConsole("🔍 Running Dijkstra live latency pathfinding across global nodes...", "system");
      try {
        const res = await fetch("/api/multihop/optimal");
        const data = await res.json();
        if (data.success) {
          selHopEntry.value = data.entry.id;
          selHopExit.value = data.exit.id;
          chkMultihopEnable.checked = true;
          logConsole(`✔ Optimal Route Found: ${data.entry.id.toUpperCase()} (${data.entry.rtt}ms) ➔ ${data.exit.id.toUpperCase()} (${data.exit.rtt}ms) | Total RTT: ${data.combined_rtt}ms`, "info");
        }
      } catch (e) {}
    });
  }

  // 17. CyberShield Whitelist
  const btnAddWhitelist = document.getElementById("btn-add-whitelist");
  const inputWhitelist = document.getElementById("input-whitelist");
  if (btnAddWhitelist && inputWhitelist) {
    btnAddWhitelist.addEventListener("click", async () => {
      playSynth("click");
      const domain = inputWhitelist.value.trim();
      if (!domain) return;
      try {
        const res = await fetch("/api/adblock/whitelist/add", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ domain: domain }),
        });
        const data = await res.json();
        if (data.success) {
          logConsole(`✔ Whitelisted '${domain}' (Total whitelisted: ${data.whitelist_count})`, "info");
          inputWhitelist.value = "";
        }
      } catch (e) {}
    });
  }

  connectWebSocket();
  setInterval(fetchAdblockStats, 3000);
});
