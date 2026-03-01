(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const taskId = window.__TASK_ID || "";
  const canInspectionWrite = Boolean(window.__CAN_INSPECTION_WRITE);
  const canDefectWrite = Boolean(window.__CAN_DEFECT_WRITE);
  const observations = Array.isArray(window.__OBS) ? window.__OBS : [];
  const map = L.map("map");
  const center = observations.length ? [observations[0].position_lat, observations[0].position_lon] : [30.5928, 114.3055];
  map.setView(center, 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const exportBtn = document.getElementById("export-btn");
  const exportResult = document.getElementById("export-result");
  const resultNode = document.getElementById("inspection-task-result");

  const obsLat = document.getElementById("observation-lat");
  const obsLon = document.getElementById("observation-lon");
  const obsAlt = document.getElementById("observation-alt");
  const obsItemCode = document.getElementById("observation-item-code");
  const obsSeverity = document.getElementById("observation-severity");
  const obsNote = document.getElementById("observation-note");
  const obsCreateBtn = document.getElementById("observation-create-btn");

  const defectObservationId = document.getElementById("defect-observation-id");
  const defectCreateBtn = document.getElementById("defect-create-btn");

  function showResult(type, message) {
    if (!resultNode) {
      return;
    }
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
      throw new Error(body.detail || "request failed");
    }
    return body;
  }

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

  if (!exportBtn || !exportResult) {
    return;
  }

  map.on("click", (event) => {
    if (obsLat) {
      obsLat.value = event.latlng.lat.toFixed(6);
    }
    if (obsLon) {
      obsLon.value = event.latlng.lng.toFixed(6);
    }
  });

  exportBtn.addEventListener("click", async () => {
    const exportTaskId = exportBtn.getAttribute("data-task-id");
    if (!exportTaskId || !token) {
      exportResult.textContent = "Missing task id or token.";
      return;
    }
    const resp = await fetch(`/api/inspection/tasks/${exportTaskId}/export?format=html`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-CSRF-Token": csrfToken,
      },
    });
    try {
      const body = await resp.json();
      if (!resp.ok) {
        exportResult.textContent = body.detail || "Export failed";
        return;
      }
      const fileResp = await fetch(`/api/inspection/exports/${body.id}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-CSRF-Token": csrfToken,
        },
      });
      if (!fileResp.ok) {
        exportResult.textContent = "Export created but file fetch failed.";
        return;
      }
      const blob = await fileResp.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      exportResult.textContent = `Export ready: ${body.id}`;
    } catch (err) {
      exportResult.textContent = toMessage(err);
    }
  });

  if (canInspectionWrite && obsCreateBtn && taskId) {
    obsCreateBtn.addEventListener("click", async () => {
      const lat = Number(obsLat && obsLat.value ? obsLat.value : "");
      const lon = Number(obsLon && obsLon.value ? obsLon.value : "");
      const alt = Number(obsAlt && obsAlt.value ? obsAlt.value : "50");
      const itemCode = (obsItemCode && obsItemCode.value ? obsItemCode.value : "").trim();
      const severity = Number.parseInt(String(obsSeverity && obsSeverity.value ? obsSeverity.value : "1"), 10) || 1;
      const note = (obsNote && obsNote.value ? obsNote.value : "").trim();

      if (!Number.isFinite(lat) || !Number.isFinite(lon) || !itemCode) {
        showResult("warn", "Latitude, longitude and item code are required.");
        return;
      }

      await withBusyButton(obsCreateBtn, "Creating...", async () => {
        try {
          const row = await post(`/api/inspection/tasks/${taskId}/observations`, {
            position_lat: lat,
            position_lon: lon,
            alt_m: Number.isFinite(alt) ? alt : 50,
            item_code: itemCode,
            severity,
            note,
          });
          showResult("success", `Observation created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  async function createDefectFromObservation(observationId, triggerBtn) {
    const id = String(observationId || "").trim();
    if (!id) {
      showResult("warn", "Observation ID is required.");
      return;
    }
    await withBusyButton(triggerBtn, "Creating...", async () => {
      try {
        const row = await post(`/api/defects/from-observation/${id}`, {});
        showResult("success", `Defect created: ${row.id}`);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  }

  if (canDefectWrite && defectCreateBtn) {
    defectCreateBtn.addEventListener("click", async () => {
      await createDefectFromObservation(defectObservationId && defectObservationId.value, defectCreateBtn);
    });

    document.querySelectorAll(".js-create-defect-from-observation").forEach((button) => {
      button.addEventListener("click", async () => {
        const observationId = button.getAttribute("data-observation-id");
        if (defectObservationId && observationId) {
          defectObservationId.value = observationId;
        }
        await createDefectFromObservation(observationId, button);
      });
    });
  }
})();
