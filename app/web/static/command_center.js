(function () {
  const token = window.__TOKEN;
  const map = L.map("live-map").setView([30.5928, 114.3055], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  let markerLayer = L.layerGroup().addTo(map);

  function setStat(id, value) {
    const node = document.getElementById(id);
    if (node) {
      node.textContent = String(value);
    }
  }

  function update(payload) {
    const stats = payload.stats || {};
    setStat("stat-online", stats.online_devices || 0);
    setStat("stat-inspection", stats.today_inspections || 0);
    setStat("stat-defect", stats.defects_total || 0);
    setStat("stat-alert", stats.realtime_alerts || 0);

    markerLayer.clearLayers();
    const markers = Array.isArray(payload.markers) ? payload.markers : [];
    markers.forEach((item) => {
      const marker = L.circleMarker([item.lat, item.lon], {
        radius: 6,
        color: item.severity >= 3 ? "#bc4749" : "#2d6a4f",
        fillOpacity: 0.8,
      });
      marker.bindPopup(`Severity: ${item.severity}<br/>${item.note || ""}`);
      marker.addTo(markerLayer);
    });
  }

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${scheme}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`);
  ws.onmessage = (event) => {
    try {
      update(JSON.parse(event.data));
    } catch (_err) {
      // Ignore invalid payload.
    }
  };
})();
