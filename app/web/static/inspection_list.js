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
  const wizardStatusNode = document.getElementById("inspection-wizard-status");
  const wizardSummaryNode = document.getElementById("inspection-wizard-summary");
  const wizardErrorNode = document.getElementById("inspection-wizard-error");
  const confirmNode = document.getElementById("inspection-wizard-confirm");
  const templateRecommendationNode = document.getElementById("inspection-template-recommendation");
  const priorityHintNode = document.getElementById("inspection-priority-hint");
  const stepButtons = {
    next1: document.getElementById("inspection-step1-next"),
    prev2: document.getElementById("inspection-step2-prev"),
    next2: document.getElementById("inspection-step2-next"),
    prev3: document.getElementById("inspection-step3-prev"),
  };
  const stepLabels = document.querySelectorAll("#inspection-wizard-steps [data-step]");
  const panels = document.querySelectorAll("[data-step-panel]");

  if (!token || !createBtn || !resultNode || !templateInput || !nameInput) {
    return;
  }

  const stepMeta = {
    1: {
      title: "第 1 步：选择巡检模板",
      summary: "先选定合适模板，系统会以模板为基础继续创建流程。",
    },
    2: {
      title: "第 2 步：填写任务信息",
      summary: "补充任务名称、优先级和区域信息，形成可执行的巡检安排。",
    },
    3: {
      title: "第 3 步：确认并创建",
      summary: "确认任务摘要后提交，避免直接使用字段式创建操作。",
    },
  };
  let currentStep = 1;

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

  function selectedTemplateLabel() {
    if (!templateInput || !templateInput.selectedOptions.length) {
      return "未选择模板";
    }
    return templateInput.selectedOptions[0].textContent || "未选择模板";
  }

  function updateTemplateRecommendation() {
    const templateName = selectedTemplateLabel();
    if (templateRecommendationNode) {
      templateRecommendationNode.innerHTML =
        `<strong>推荐提示：</strong>当前选择 <code>${templateName}</code>，建议沿用“区域 + ${templateName} + 班次”命名方式。`;
    }
    if (nameInput && !(nameInput.value || "").trim() && templateName !== "未选择模板") {
      nameInput.value = `${templateName}-巡检任务`;
    }
    if (currentStep === 3) {
      updateConfirmSummary();
    }
  }

  function updatePriorityHint() {
    if (!priorityHintNode || !priorityInput) {
      return;
    }
    const priority = Number.parseInt(String(priorityInput.value || "5"), 10) || 5;
    if (priority >= 8) {
      priorityHintNode.textContent = "当前为高优先级，建议确认人员、空域和结果回传链路已准备完成。";
      return;
    }
    if (priority <= 3) {
      priorityHintNode.textContent = "当前为低优先级，适合纳入常规排班处理。";
      return;
    }
    priorityHintNode.textContent = "当前为标准优先级，适合常规巡检。";
  }

  function updateConfirmSummary() {
    if (!confirmNode) {
      return;
    }
    const name = (nameInput.value || "").trim() || "未填写任务名称";
    const priority = Number.parseInt(String(priorityInput ? priorityInput.value : "5"), 10) || 5;
    const areaGeom = (geomInput && geomInput.value ? geomInput.value : "").trim() || "未填写区域几何";
    confirmNode.innerHTML =
      `<strong>模板：</strong>${selectedTemplateLabel()}<br>` +
      `<strong>任务名称：</strong>${name}<br>` +
      `<strong>优先级：</strong>${priority}<br>` +
      `<strong>区域信息：</strong>${areaGeom}`;
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
    stepLabels.forEach((node) => {
      node.classList.toggle("active", Number(node.getAttribute("data-step")) === step);
    });
    panels.forEach((node) => {
      node.hidden = Number(node.getAttribute("data-step-panel")) !== step;
    });
    if (step === 3) {
      updateConfirmSummary();
    }
  }

  function goNextFromTemplate() {
    const templateId = (templateInput.value || "").trim();
    if (!templateId) {
      setWizardError("请选择一个巡检模板后再进入下一步。");
      showResult("warn", "请先选择巡检模板。");
      return;
    }
    setStep(2);
  }

  function goNextFromDetails() {
    const name = (nameInput.value || "").trim();
    if (!name) {
      setWizardError("任务名称不能为空，建议使用“区域 + 任务类型 + 班次”的命名方式。");
      showResult("warn", "请先填写任务名称。");
      return;
    }
    setStep(3);
  }

  if (stepButtons.next1) {
    stepButtons.next1.addEventListener("click", goNextFromTemplate);
  }
  if (stepButtons.prev2) {
    stepButtons.prev2.addEventListener("click", () => setStep(1));
  }
  if (stepButtons.next2) {
    stepButtons.next2.addEventListener("click", goNextFromDetails);
  }
  if (stepButtons.prev3) {
    stepButtons.prev3.addEventListener("click", () => setStep(2));
  }

  templateInput.addEventListener("change", () => {
    updateTemplateRecommendation();
    if (currentStep === 3) {
      updateConfirmSummary();
    }
  });
  nameInput.addEventListener("input", () => {
    if (currentStep === 3) {
      updateConfirmSummary();
    }
  });
  if (priorityInput) {
    priorityInput.addEventListener("input", () => {
      updatePriorityHint();
      if (currentStep === 3) {
        updateConfirmSummary();
      }
    });
  }
  if (geomInput) {
    geomInput.addEventListener("input", () => {
      if (currentStep === 3) {
        updateConfirmSummary();
      }
    });
  }

  createBtn.addEventListener("click", async () => {
    const templateId = (templateInput.value || "").trim();
    const name = (nameInput.value || "").trim();
    const priority = Number.parseInt(String(priorityInput ? priorityInput.value : "5"), 10) || 5;
    const areaGeom = (geomInput && geomInput.value ? geomInput.value : "").trim();
    if (!templateId || !name) {
      showResult("warn", "请选择模板并填写任务名称。");
      return;
    }
    await withBusyButton(createBtn, "创建中...", async () => {
      try {
        const task = await post("/api/inspection/tasks", {
          name,
          template_id: templateId,
          area_geom: areaGeom,
          priority,
        });
        showResult("success", `已创建巡检任务：${task.id}`);
        if (nameInput) {
          nameInput.value = "";
        }
        if (geomInput) {
          geomInput.value = "";
        }
        if (priorityInput) {
          priorityInput.value = "5";
        }
        setWizardError("");
        setStep(1);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  });

  updateTemplateRecommendation();
  updatePriorityHint();
  setStep(1);
})();
