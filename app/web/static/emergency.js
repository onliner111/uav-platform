(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canIncidentWrite = Boolean(window.__CAN_INCIDENT_WRITE);
  const resultNode = document.getElementById("emergency-result");
  const titleInput = document.getElementById("incident-title");
  const levelSelect = document.getElementById("incident-level");
  const taskNameInput = document.getElementById("incident-task-name");
  const templateIdInput = document.getElementById("incident-template-id");
  const createIncidentBtn = document.getElementById("create-incident-btn");
  const createTaskBtn = document.getElementById("create-task-btn");

  if (!token) {
    if (resultNode) {
      resultNode.textContent = "Missing session token.";
    }
    return;
  }

  function showResult(type, message) {
    if (ui && typeof ui.setResult === "function") {
      ui.setResult(resultNode, type, message);
      return;
    }
    resultNode.textContent = message;
  }

  function toMessage(err) {
    if (ui && typeof ui.toMessage === "function") {
      return ui.toMessage(err);
    }
    return String((err && err.message) || err || "request failed");
  }

  async function withBusyButton(button, pendingLabel, action) {
    if (ui && typeof ui.withBusyButton === "function") {
      await ui.withBusyButton(button, pendingLabel, action);
      return;
    }
    await action();
  }

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
    showResult("success", `Location selected: ${selected.lat.toFixed(6)}, ${selected.lon.toFixed(6)}`);
  });

  async function post(path, payload) {
    const resp = await fetch(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
        "X-CSRF-Token": csrfToken,
      },
      body: JSON.stringify(payload),
    });
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "Request failed");
    }
    return body;
  }

  function buildCreateTaskPayload() {
    const payload = {};
    const templateId = (templateIdInput && templateIdInput.value ? templateIdInput.value : "").trim();
    const taskName = (taskNameInput && taskNameInput.value ? taskNameInput.value : "").trim();
    if (templateId) {
      payload.template_id = templateId;
    }
    if (taskName) {
      payload.task_name = taskName;
    }
    return payload;
  }

  async function createTaskForIncident(targetIncidentId, triggerBtn) {
    await withBusyButton(triggerBtn, "Creating...", async () => {
      try {
        const task = await post(`/api/incidents/${targetIncidentId}/create-task`, buildCreateTaskPayload());
        showResult("success", `Task created: ${task.task_id} (mission ${task.mission_id})`);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  }

  if (canIncidentWrite && createIncidentBtn) {
    createIncidentBtn.addEventListener("click", async () => {
      const title = titleInput.value.trim();
      const level = levelSelect.value;
      if (!title) {
        showResult("warn", "Title is required.");
        return;
      }
      const locationGeom = `POINT(${selected.lon.toFixed(6)} ${selected.lat.toFixed(6)})`;
      await withBusyButton(createIncidentBtn, "Creating...", async () => {
        try {
          const incident = await post("/api/incidents", {
            title,
            level,
            location_geom: locationGeom,
          });
          incidentId = incident.id;
          showResult("success", `Incident created: ${incident.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (canIncidentWrite && createTaskBtn) {
    createTaskBtn.addEventListener("click", async () => {
      if (!incidentId) {
        showResult("warn", "Create or select incident first.");
        return;
      }
      await createTaskForIncident(incidentId, createTaskBtn);
    });
  }

  document.querySelectorAll(".js-incident-create-task").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!canIncidentWrite || button.disabled) {
        return;
      }
      const rowIncidentId = button.getAttribute("data-incident-id") || "";
      if (!rowIncidentId) {
        showResult("warn", "Incident ID is missing.");
        return;
      }
      incidentId = rowIncidentId;
      await createTaskForIncident(rowIncidentId, button);
    });
  });

  if (!canIncidentWrite) {
    showResult("warn", "Read-only mode: incident write actions are disabled.");
  }
})();
