(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";

  const templateInput = document.getElementById("inspection-create-template");
  const nameInput = document.getElementById("inspection-create-name");
  const priorityInput = document.getElementById("inspection-create-priority");
  const geomInput = document.getElementById("inspection-create-geom");
  const createBtn = document.getElementById("inspection-create-btn");
  const resultNode = document.getElementById("inspection-list-result");

  if (!token || !createBtn || !resultNode || !templateInput || !nameInput) {
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

  createBtn.addEventListener("click", async () => {
    const templateId = (templateInput.value || "").trim();
    const name = (nameInput.value || "").trim();
    const priority = Number.parseInt(String(priorityInput ? priorityInput.value : "5"), 10) || 5;
    const areaGeom = (geomInput && geomInput.value ? geomInput.value : "").trim();
    if (!templateId || !name) {
      showResult("warn", "Template and task name are required.");
      return;
    }
    await withBusyButton(createBtn, "Creating...", async () => {
      try {
        const task = await post("/api/inspection/tasks", {
          name,
          template_id: templateId,
          area_geom: areaGeom,
          priority,
        });
        showResult("success", `Task created: ${task.id}`);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  });
})();
