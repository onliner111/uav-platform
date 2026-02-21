(function () {
  const observations = Array.isArray(window.__OBS) ? window.__OBS : [];
  const map = L.map("map");
  const center = observations.length
    ? [observations[0].position_lat, observations[0].position_lon]
    : [30.5928, 114.3055];
  map.setView(center, 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  observations.forEach((item) => {
    const marker = L.circleMarker([item.position_lat, item.position_lon], {
      radius: 7,
      color: item.severity >= 3 ? "#bc4749" : "#2d6a4f",
      weight: 2,
      fillOpacity: 0.9,
    }).addTo(map);
    marker.bindPopup(
      "<strong>" + item.item_code + "</strong><br/>" +
      "Severity: " + item.severity + "<br/>" +
      "Note: " + (item.note || "")
    );
  });

  const exportBtn = document.getElementById("export-btn");
  const exportResult = document.getElementById("export-result");
  if (!exportBtn || !exportResult) {
    return;
  }

  exportBtn.addEventListener("click", async () => {
    const taskId = exportBtn.getAttribute("data-task-id");
    const token = exportBtn.getAttribute("data-token");
    if (!taskId || !token) {
      exportResult.textContent = "Missing task id or token.";
      return;
    }
    const resp = await fetch(`/api/inspection/tasks/${taskId}/export?format=html`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
    });
    const body = await resp.json();
    if (!resp.ok) {
      exportResult.textContent = body.detail || "Export failed";
      return;
    }
    const fileResp = await fetch(`/api/inspection/exports/${body.id}`, {
      headers: { Authorization: `Bearer ${token}` },
    });
    if (!fileResp.ok) {
      exportResult.textContent = "Export created but file fetch failed.";
      return;
    }
    const blob = await fileResp.blob();
    const url = URL.createObjectURL(blob);
    window.open(url, "_blank", "noopener,noreferrer");
    exportResult.textContent = `Export ready: ${body.id}`;
  });
})();
