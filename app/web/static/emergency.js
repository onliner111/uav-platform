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
  const incidentSelectionBanner = document.getElementById("incident-selection-banner");
  const locationText = document.getElementById("incident-location-text");
  const wizardStatusNode = document.getElementById("incident-wizard-status");
  const wizardSummaryNode = document.getElementById("incident-wizard-summary");
  const wizardErrorNode = document.getElementById("incident-wizard-error");
  const wizardConfirmNode = document.getElementById("incident-wizard-confirm");
  const levelGuidanceNode = document.getElementById("incident-level-guidance");
  const taskSuggestionNode = document.getElementById("incident-task-suggestion");
  const wizardStepNodes = document.querySelectorAll("#incident-wizard-steps [data-step]");
  const wizardPanels = document.querySelectorAll("[data-step-panel]");
  const stepButtons = {
    next1: document.getElementById("incident-step1-next"),
    prev2: document.getElementById("incident-step2-prev"),
    next2: document.getElementById("incident-step2-next"),
    prev3: document.getElementById("incident-step3-prev"),
  };

  if (!token) {
    if (resultNode) {
      resultNode.textContent = "缺少会话令牌。";
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

  function setWizardError(message) {
    if (!wizardErrorNode) {
      return;
    }
    wizardErrorNode.hidden = !message;
    wizardErrorNode.textContent = message || "";
  }

  function toMessage(err) {
    if (ui && typeof ui.toMessage === "function") {
      return ui.toMessage(err);
    }
    return String((err && err.message) || err || "请求失败，请稍后重试。");
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
  let currentStep = 1;
  const stepMeta = {
    1: {
      title: "第 1 步：确定事件位置",
      summary: "先在地图上确认位置，再继续创建事件单。",
    },
    2: {
      title: "第 2 步：创建事件",
      summary: "填写标题和等级，系统会自动使用当前坐标建单。",
    },
    3: {
      title: "第 3 步：联动任务",
      summary: "基于当前事件继续联动任务，无需手动填写事件 ID。",
    },
  };

  function updateLocationText() {
    if (locationText) {
      locationText.textContent = `${selected.lat.toFixed(6)}, ${selected.lon.toFixed(6)}`;
    }
    if (currentStep === 3) {
      updateIncidentSummary();
    }
  }

  function suggestedTaskName() {
    const title = (titleInput && titleInput.value ? titleInput.value : "").trim();
    return title ? `${title}-联动巡查` : "应急联动巡查";
  }

  function updateLevelGuidance() {
    if (!levelGuidanceNode || !levelSelect) {
      return;
    }
    const level = String(levelSelect.value || "HIGH").toUpperCase();
    if (level === "HIGH") {
      levelGuidanceNode.innerHTML = "<strong>风险提示：</strong>高等级事件会优先走快速联动链路，请确认等级选择准确。";
      return;
    }
    if (level === "MEDIUM") {
      levelGuidanceNode.innerHTML = "<strong>风险提示：</strong>中等级事件适合常规联动处置，建议确认周边资源是否充足。";
      return;
    }
    levelGuidanceNode.innerHTML = "<strong>风险提示：</strong>低等级事件通常可纳入常规处置队列，仍建议保留现场位置。";
  }

  function updateTaskSuggestion() {
    if (taskSuggestionNode) {
      taskSuggestionNode.textContent = `系统建议任务名称：${suggestedTaskName()}`;
    }
    if (taskNameInput && !(taskNameInput.value || "").trim()) {
      taskNameInput.value = suggestedTaskName();
    }
  }

  function updateIncidentSummary(title = "", status = "", hasTask = false) {
    if (!wizardConfirmNode) {
      return;
    }
    if (!incidentId) {
      wizardConfirmNode.textContent = "当前尚未创建或选中事件。";
      return;
    }
    wizardConfirmNode.innerHTML =
      `<strong>当前事件：</strong><code>${incidentId}</code>` +
      `${title ? `，标题：${title}` : ""}` +
      `${status ? `，状态：${status}` : ""}` +
      `${hasTask ? "，已存在联动任务。" : "，可继续一键联动任务。"}<br>` +
      `<strong>坐标：</strong>${selected.lat.toFixed(6)}, ${selected.lon.toFixed(6)}`;
  }

  function setStep(step) {
    currentStep = step;
    setWizardError("");
    const meta = stepMeta[step] || stepMeta[1];
    if (wizardStatusNode) {
      wizardStatusNode.textContent = meta.title;
    }
    if (wizardSummaryNode) {
      wizardSummaryNode.textContent = meta.summary;
    }
    wizardStepNodes.forEach((node) => {
      node.classList.toggle("active", Number(node.getAttribute("data-step")) === step);
    });
    wizardPanels.forEach((node) => {
      node.hidden = Number(node.getAttribute("data-step-panel")) !== step;
    });
    if (step === 1) {
      setTimeout(() => map.invalidateSize(), 0);
    }
  }

  function setSelectedIncident(targetIncidentId, title, status, hasTask) {
    incidentId = targetIncidentId;
    if (incidentSelectionBanner) {
      incidentSelectionBanner.innerHTML =
        `<strong>当前事件：</strong><code>${targetIncidentId}</code>` +
        `${title ? `，标题：${title}` : ""}` +
        `${status ? `，状态：${status}` : ""}` +
        `${hasTask ? "，已有关联任务。" : "，可继续联动任务。"} `;
    }
    updateIncidentSummary(title, status, hasTask);
  }

  const map = L.map("map").setView([selected.lat, selected.lon], 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);
  const marker = L.marker([selected.lat, selected.lon]).addTo(map);
  updateLocationText();

  map.on("click", (event) => {
    selected = { lat: event.latlng.lat, lon: event.latlng.lng };
    marker.setLatLng([selected.lat, selected.lon]);
    updateLocationText();
    showResult("success", `已更新事件坐标：${selected.lat.toFixed(6)}, ${selected.lon.toFixed(6)}`);
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
      throw new Error(body.detail || "请求失败，请稍后重试。");
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

  if (stepButtons.next1) {
    stepButtons.next1.addEventListener("click", () => {
      setStep(2);
    });
  }
  if (stepButtons.prev2) {
    stepButtons.prev2.addEventListener("click", () => {
      setStep(1);
    });
  }
  if (stepButtons.next2) {
    stepButtons.next2.addEventListener("click", () => {
      if (!incidentId) {
        setWizardError("请先创建事件，或先从下方列表选中已有事件，再进入联动任务。");
        showResult("warn", "请先创建事件，或从下方列表选中已有事件。");
        return;
      }
      setStep(3);
    });
  }
  if (stepButtons.prev3) {
    stepButtons.prev3.addEventListener("click", () => {
      setStep(2);
    });
  }

  if (titleInput) {
    titleInput.addEventListener("input", () => {
      updateTaskSuggestion();
    });
  }
  if (levelSelect) {
    levelSelect.addEventListener("change", () => {
      updateLevelGuidance();
    });
  }

  async function createTaskForIncident(targetIncidentId, triggerBtn, title) {
    await withBusyButton(triggerBtn, "创建中...", async () => {
      try {
        const task = await post(`/api/incidents/${targetIncidentId}/create-task`, buildCreateTaskPayload());
        setSelectedIncident(targetIncidentId, title || "", "TASK_CREATED", true);
        setStep(3);
        showResult("success", `已创建联动任务：${task.task_id}（任务编排 ${task.mission_id}）`);
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
        setWizardError("事件标题不能为空，建议使用“地点 + 事件类型 + 处置目标”的表达方式。");
        showResult("warn", "请填写事件标题。");
        return;
      }
      const locationGeom = `POINT(${selected.lon.toFixed(6)} ${selected.lat.toFixed(6)})`;
      await withBusyButton(createIncidentBtn, "创建中...", async () => {
        try {
          const incident = await post("/api/incidents", {
            title,
            level,
            location_geom: locationGeom,
          });
          setSelectedIncident(incident.id, incident.title || title, incident.status || "CREATED", false);
          setWizardError("");
          setStep(3);
          showResult("success", `已创建应急事件：${incident.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (canIncidentWrite && createTaskBtn) {
    createTaskBtn.addEventListener("click", async () => {
      if (!incidentId) {
        setWizardError("当前还没有事件上下文，请先完成建单或选中事件。");
        showResult("warn", "请先创建或选中事件。");
        return;
      }
      await createTaskForIncident(incidentId, createTaskBtn, titleInput ? titleInput.value.trim() : "");
    });
  }

  document.querySelectorAll(".js-incident-select").forEach((button) => {
    button.addEventListener("click", () => {
      const rowIncidentId = button.getAttribute("data-incident-id") || "";
      const title = button.getAttribute("data-incident-title") || "";
      const status = button.getAttribute("data-incident-status") || "";
      const hasTask = button.getAttribute("data-has-task") === "true";
      setSelectedIncident(rowIncidentId, title, status, hasTask);
      setStep(3);
      if (titleInput) {
        titleInput.value = title || titleInput.value;
      }
      showResult("success", `已选中事件：${title || rowIncidentId}`);
    });
  });

  document.querySelectorAll(".js-incident-create-task").forEach((button) => {
    button.addEventListener("click", async () => {
      if (!canIncidentWrite || button.disabled) {
        return;
      }
      const rowIncidentId = button.getAttribute("data-incident-id") || "";
      const title = button.getAttribute("data-incident-title") || "";
      if (!rowIncidentId) {
        showResult("warn", "事件 ID 缺失。");
        return;
      }
      setSelectedIncident(rowIncidentId, title, "处理中", false);
      setStep(3);
      await createTaskForIncident(rowIncidentId, button, title);
    });
  });

  if (!canIncidentWrite) {
    showResult("warn", "当前为只读模式，无法创建事件或联动任务。");
  }

  updateIncidentSummary();
  updateLevelGuidance();
  updateTaskSuggestion();
  setStep(1);
})();
