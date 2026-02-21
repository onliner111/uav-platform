(function () {
  const token = window.__TOKEN;
  const resultNode = document.getElementById("emergency-result");
  const titleInput = document.getElementById("incident-title");
  const levelSelect = document.getElementById("incident-level");
  const createIncidentBtn = document.getElementById("create-incident-btn");
  const createTaskBtn = document.getElementById("create-task-btn");

  let selected = { lat: 30.5928, lon: 114.3055 };
  let incidentId = "";

  const map = L.map("map").setView([selected.lat, selected.lon], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  let marker = L.marker([selected.lat, selected.lon]).addTo(map);

  map.on("click", (event) => {
    selected = { lat: event.latlng.lat, lon: event.latlng.lng };
    marker.setLatLng([selected.lat, selected.lon]);
    resultNode.textContent = `Location selected: ${selected.lat.toFixed(6)}, ${selected.lon.toFixed(6)}`;
  });

  async function post(path, payload) {
    const resp = await fetch(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "Request failed");
    }
    return body;
  }

  createIncidentBtn.addEventListener("click", async () => {
    const title = titleInput.value.trim();
    const level = levelSelect.value;
    if (!title) {
      resultNode.textContent = "Title is required.";
      return;
    }
    const locationGeom = `POINT(${selected.lon.toFixed(6)} ${selected.lat.toFixed(6)})`;
    try {
      const incident = await post("/api/incidents", {
        title,
        level,
        location_geom: locationGeom,
      });
      incidentId = incident.id;
      resultNode.textContent = `Incident created: ${incident.id}`;
    } catch (err) {
      resultNode.textContent = err.message;
    }
  });

  createTaskBtn.addEventListener("click", async () => {
    if (!incidentId) {
      resultNode.textContent = "Create incident first.";
      return;
    }
    try {
      const task = await post(`/api/incidents/${incidentId}/create-task`, {});
      resultNode.textContent = `Task created in emergency mode: ${task.task_id} (mission ${task.mission_id})`;
    } catch (err) {
      resultNode.textContent = err.message;
    }
  });
})();
