(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const defectIdInput = document.getElementById("defect-id");
  const assignedToInput = document.getElementById("assigned-to");
  const assignNoteInput = document.getElementById("assign-note");
  const statusSelect = document.getElementById("next-status");
  const statusNoteInput = document.getElementById("status-note");
  const detailIdInput = document.getElementById("defect-detail-id");
  const observationIdInput = document.getElementById("defect-observation-id");
  const detailBtn = document.getElementById("defect-detail-btn");
  const detailBox = document.getElementById("defect-detail-box");
  const resultNode = document.getElementById("defect-result");
  const assignBtn = document.getElementById("assign-btn");
  const statusBtn = document.getElementById("status-btn");

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

  async function callApi(path, payload) {
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

  async function getApi(path) {
    const resp = await fetch(path, {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-CSRF-Token": csrfToken,
      },
    });
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "Request failed");
    }
    return body;
  }

  assignBtn.addEventListener("click", async () => {
    const defectId = defectIdInput.value.trim();
    const assignedTo = assignedToInput.value.trim();
    if (!defectId || !assignedTo) {
      showResult("warn", "Defect ID and assignee are required.");
      return;
    }
    await withBusyButton(assignBtn, "Assigning...", async () => {
      try {
        const note = (assignNoteInput && assignNoteInput.value ? assignNoteInput.value : "").trim();
        const payload = { assigned_to: assignedTo };
        if (note) {
          payload.note = note;
        }
        const body = await callApi(`/api/defects/${defectId}/assign`, payload);
        showResult("success", `Assigned. Current status: ${body.status}`);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  });

  statusBtn.addEventListener("click", async () => {
    const defectId = defectIdInput.value.trim();
    const nextStatus = statusSelect.value;
    if (!defectId || !nextStatus) {
      showResult("warn", "Defect ID and status are required.");
      return;
    }
    await withBusyButton(statusBtn, "Updating...", async () => {
      try {
        const note = (statusNoteInput && statusNoteInput.value ? statusNoteInput.value : "").trim();
        const payload = { status: nextStatus };
        if (note) {
          payload.note = note;
        }
        const body = await callApi(`/api/defects/${defectId}/status`, payload);
        showResult("success", `Status updated: ${body.status}`);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  });

  if (detailBtn && detailIdInput && detailBox) {
    detailBtn.addEventListener("click", async () => {
      const defectId = detailIdInput.value.trim();
      if (!defectId) {
        showResult("warn", "Defect ID is required.");
        return;
      }
      await withBusyButton(detailBtn, "Loading...", async () => {
        try {
          const body = await getApi(`/api/defects/${defectId}`);
          const actions = Array.isArray(body.actions) ? body.actions : [];
          detailBox.textContent = [
            `id: ${body.defect.id}`,
            `status: ${body.defect.status}`,
            `severity: ${body.defect.severity}`,
            `assigned_to: ${body.defect.assigned_to || "-"}`,
            `observation_id: ${body.defect.observation_id}`,
            "--- actions ---",
            actions.length
              ? actions.map((item) => `[${item.created_at}] ${item.action_type}: ${item.note || ""}`).join("\n")
              : "No actions.",
          ].join("\n");
          if (defectIdInput) {
            defectIdInput.value = body.defect.id;
          }
          if (observationIdInput) {
            observationIdInput.value = body.defect.observation_id || "";
          }
          showResult("success", "Detail loaded.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  document.querySelectorAll(".js-prefill-defect").forEach((button) => {
    button.addEventListener("click", () => {
      const defectId = button.getAttribute("data-defect-id") || "";
      const observationId = button.getAttribute("data-observation-id") || "";
      if (defectIdInput) {
        defectIdInput.value = defectId;
      }
      if (detailIdInput) {
        detailIdInput.value = defectId;
      }
      if (observationIdInput) {
        observationIdInput.value = observationId;
      }
      showResult("success", `Selected defect: ${defectId}`);
    });
  });

  if (statusBtn && statusBtn.disabled && assignBtn && assignBtn.disabled) {
    if (resultNode && resultNode.textContent.trim().length === 0) {
      showResult("warn", "Read-only mode: write actions are disabled.");
    }
  });
})();
