(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const token = window.__TOKEN || auth.token;
  if (!token) {
    return;
  }

  const map = L.map("live-map").setView([30.5928, 114.3055], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const layerConfig = {
    resources: { id: "layer-resources", group: L.layerGroup().addTo(map) },
    tasks: { id: "layer-tasks", group: L.layerGroup().addTo(map) },
    alerts: { id: "layer-alerts", group: L.layerGroup().addTo(map) },
    events: { id: "layer-events", group: L.layerGroup() },
  };

  const replayState = {
    points: [],
    cursor: 0,
    timer: null,
    marker: null,
    line: null,
  };

  const replayDroneSelect = document.getElementById("replay-drone");
  const replayStepInput = document.getElementById("replay-step");
  const replayStatusNode = document.getElementById("replay-status");
  const alertListNode = document.getElementById("alert-list");
  const alertCardNode = document.getElementById("card-alert");
  const videoSlotsNode = document.getElementById("video-slots");

  const videoSlots = [
    { slot: "A1", protocol: "RTSP", endpoint: null },
    { slot: "A2", protocol: "WebRTC", endpoint: null },
    { slot: "B1", protocol: "RTSP", endpoint: null },
  ];

  function authHeaders() {
    return {
      Authorization: `Bearer ${token}`,
    };
  }

  function setStat(id, value) {
    const node = document.getElementById(id);
    if (node) {
      node.textContent = String(value);
    }
  }

  function setReplayStatus(text) {
    if (replayStatusNode) {
      replayStatusNode.textContent = text;
    }
  }

  function iconStyleFor(item) {
    if (item.category === "alert") {
      return { radius: 8, color: "#bc4749", fillColor: "#bc4749", fillOpacity: 0.95 };
    }
    if (item.category === "event") {
      return { radius: 5, color: "#495057", fillColor: "#495057", fillOpacity: 0.8 };
    }
    if (item.category === "mission" || item.category === "inspection_task" || item.category === "incident") {
      return { radius: 6, color: "#7f5539", fillColor: "#ddbea9", fillOpacity: 0.8 };
    }
    return { radius: 6, color: "#2d6a4f", fillColor: "#95d5b2", fillOpacity: 0.9 };
  }

  function popupHtml(item) {
    const detail = item.detail || {};
    const lines = [
      `<strong>${item.label || item.id}</strong>`,
      `Category: ${item.category}`,
      item.status ? `Status: ${item.status}` : null,
      detail.alert_type ? `AlertType: ${detail.alert_type}` : null,
      detail.severity ? `Severity: ${detail.severity}` : null,
      detail.drone_id ? `Drone: ${detail.drone_id}` : null,
      detail.mode ? `Mode: ${detail.mode}` : null,
    ].filter(Boolean);
    return lines.join("<br/>");
  }

  function applyLayerVisibility() {
    Object.keys(layerConfig).forEach((key) => {
      const cfg = layerConfig[key];
      const toggle = document.getElementById(cfg.id);
      if (!toggle) {
        return;
      }
      if (toggle.checked) {
        cfg.group.addTo(map);
      } else {
        map.removeLayer(cfg.group);
      }
    });
  }

  function clearReplay() {
    if (replayState.timer) {
      clearInterval(replayState.timer);
      replayState.timer = null;
    }
    if (replayState.marker) {
      map.removeLayer(replayState.marker);
      replayState.marker = null;
    }
    if (replayState.line) {
      map.removeLayer(replayState.line);
      replayState.line = null;
    }
    replayState.points = [];
    replayState.cursor = 0;
  }

  function renderLayerItems(layerName, items) {
    const cfg = layerConfig[layerName];
    if (!cfg) {
      return;
    }
    cfg.group.clearLayers();
    const bounds = [];
    items.forEach((item) => {
      if (!item.point || typeof item.point.lat !== "number" || typeof item.point.lon !== "number") {
        return;
      }
      const style = iconStyleFor(item);
      const marker = L.circleMarker([item.point.lat, item.point.lon], style);
      marker.bindPopup(popupHtml(item));
      marker.addTo(cfg.group);
      bounds.push([item.point.lat, item.point.lon]);
    });
    if (layerName === "alerts" && bounds.length > 0) {
      const ring = L.circle([bounds[0][0], bounds[0][1]], {
        radius: 40,
        color: "#bc4749",
        weight: 1,
        fillOpacity: 0.08,
      });
      ring.addTo(cfg.group);
    }
  }

  function updateReplayDroneOptions(resourceItems) {
    if (!replayDroneSelect) {
      return;
    }
    const current = replayDroneSelect.value;
    const drones = resourceItems.filter((item) => item.category === "drone");
    replayDroneSelect.innerHTML = '<option value="">Select drone</option>';
    drones.forEach((drone) => {
      const option = document.createElement("option");
      option.value = drone.id;
      option.textContent = drone.label || drone.id;
      replayDroneSelect.appendChild(option);
    });
    if (current && drones.some((item) => item.id === current)) {
      replayDroneSelect.value = current;
    }
  }

  function updateAlertList(alertItems) {
    if (!alertListNode) {
      return;
    }
    alertListNode.innerHTML = "";
    if (!Array.isArray(alertItems) || alertItems.length === 0) {
      alertListNode.innerHTML = '<li class="hint">No active alerts.</li>';
      if (alertCardNode) {
        alertCardNode.classList.remove("alert-hot");
      }
      return;
    }
    if (alertCardNode) {
      alertCardNode.classList.add("alert-hot");
    }
    alertItems.slice(0, 6).forEach((item) => {
      const detail = item.detail || {};
      const li = document.createElement("li");
      li.className = "alert-item";
      li.innerHTML = `${item.label || "Alert"}<small>${detail.alert_type || "-"} / ${detail.severity || "-"} / ${detail.drone_id || "-"}</small>`;
      alertListNode.appendChild(li);
    });
  }

  function renderVideoSlots() {
    if (!videoSlotsNode) {
      return;
    }
    videoSlotsNode.innerHTML = "";
    videoSlots.forEach((slot) => {
      const container = document.createElement("div");
      container.className = "video-slot";
      container.innerHTML = `
        <div class="title"><span>Slot ${slot.slot}</span><span class="status-pill">Placeholder</span></div>
        <div class="meta">${slot.protocol} gateway ready; endpoint pending integration.</div>
      `;
      videoSlotsNode.appendChild(container);
    });
  }

  function updateDashboardStats(payload) {
    const stats = payload.stats || {};
    setStat("stat-online", stats.online_devices || 0);
    setStat("stat-inspection", stats.today_inspections || 0);
    setStat("stat-defect", stats.defects_total || 0);
    setStat("stat-alert", stats.realtime_alerts || 0);
  }

  async function fetchMapOverview() {
    const response = await fetch("/api/map/overview?limit_per_layer=200", {
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`map overview failed: ${response.status}`);
    }
    return response.json();
  }

  async function refreshMapLayers() {
    try {
      const overview = await fetchMapOverview();
      const layers = Array.isArray(overview.layers) ? overview.layers : [];
      const layerByName = {};
      layers.forEach((layer) => {
        layerByName[layer.layer] = layer;
        renderLayerItems(layer.layer, Array.isArray(layer.items) ? layer.items : []);
      });
      updateReplayDroneOptions((layerByName.resources && layerByName.resources.items) || []);
      updateAlertList((layerByName.alerts && layerByName.alerts.items) || []);
      applyLayerVisibility();
    } catch (err) {
      setReplayStatus(`Map refresh failed: ${String(err)}`);
    }
  }

  function playReplay() {
    if (!replayState.points.length) {
      setReplayStatus("No replay points loaded.");
      return;
    }
    clearReplay();
    replayState.points = replayState.points.length ? replayState.points : [];
  }

  function startReplayAnimation(points) {
    clearReplay();
    replayState.points = points;
    replayState.cursor = 0;
    const latLngs = points.map((item) => [item.lat, item.lon]);
    replayState.line = L.polyline(latLngs, { color: "#1d3557", weight: 3, opacity: 0.85 }).addTo(map);
    replayState.marker = L.circleMarker(latLngs[0], {
      radius: 7,
      color: "#1d3557",
      fillColor: "#a8dadc",
      fillOpacity: 0.95,
    });
    replayState.marker.addTo(map);
    map.fitBounds(replayState.line.getBounds(), { padding: [18, 18] });

    replayState.timer = setInterval(() => {
      if (!replayState.marker || replayState.cursor >= replayState.points.length) {
        clearReplay();
        setReplayStatus("Replay completed.");
        return;
      }
      const point = replayState.points[replayState.cursor];
      replayState.marker.setLatLng([point.lat, point.lon]);
      replayState.cursor += 1;
      setReplayStatus(`Replay running: ${replayState.cursor}/${replayState.points.length}`);
    }, 500);
  }

  async function loadReplayAndPlay() {
    if (!replayDroneSelect || !replayDroneSelect.value) {
      setReplayStatus("Select a drone first.");
      return;
    }
    const step = Number(replayStepInput && replayStepInput.value ? replayStepInput.value : 1);
    const droneId = encodeURIComponent(replayDroneSelect.value);
    const response = await fetch(`/api/map/tracks/replay?drone_id=${droneId}&sample_step=${step}`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      setReplayStatus(`Replay load failed: ${response.status}`);
      return;
    }
    const payload = await response.json();
    const points = Array.isArray(payload.points) ? payload.points : [];
    if (!points.length) {
      setReplayStatus("Replay data empty.");
      return;
    }
    startReplayAnimation(points);
  }

  Object.keys(layerConfig).forEach((key) => {
    const cfg = layerConfig[key];
    const toggle = document.getElementById(cfg.id);
    if (toggle) {
      toggle.addEventListener("change", applyLayerVisibility);
    }
  });

  const replayPlayBtn = document.getElementById("replay-play");
  const replayStopBtn = document.getElementById("replay-stop");
  const replayRefreshBtn = document.getElementById("replay-refresh");
  if (replayPlayBtn) {
    replayPlayBtn.addEventListener("click", () => {
      loadReplayAndPlay().catch((err) => setReplayStatus(`Replay error: ${String(err)}`));
    });
  }
  if (replayRefreshBtn) {
    replayRefreshBtn.addEventListener("click", () => {
      refreshMapLayers();
      setReplayStatus("Layer data refreshed.");
    });
  }
  if (replayStopBtn) {
    replayStopBtn.addEventListener("click", () => {
      clearReplay();
      setReplayStatus("Replay stopped.");
    });
  }

  renderVideoSlots();
  refreshMapLayers();
  setInterval(refreshMapLayers, 15000);

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${scheme}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`);
  ws.onmessage = (event) => {
    try {
      updateDashboardStats(JSON.parse(event.data));
    } catch (_err) {
      // Ignore invalid payload.
    }
  };
})();
