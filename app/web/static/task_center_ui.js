(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const resultNode = document.getElementById("task-center-result");

  const transitionTaskId = document.getElementById("task-transition-id");
  const transitionState = document.getElementById("task-transition-state");
  const transitionNote = document.getElementById("task-transition-note");
  const transitionBtn = document.getElementById("task-transition-btn");

  const dispatchTaskId = document.getElementById("task-dispatch-id");
  const dispatchUser = document.getElementById("task-dispatch-user");
  const dispatchNote = document.getElementById("task-dispatch-note");
  const dispatchBtn = document.getElementById("task-dispatch-btn");

  const createType = document.getElementById("task-create-type");
  const createTemplate = document.getElementById("task-create-template");
  const createName = document.getElementById("task-create-name");
  const createPriority = document.getElementById("task-create-priority");
  const createRisk = document.getElementById("task-create-risk");
  const createBtn = document.getElementById("task-create-btn");

  const submitApprovalId = document.getElementById("task-submit-approval-id");
  const submitApprovalNote = document.getElementById("task-submit-approval-note");
  const submitApprovalBtn = document.getElementById("task-submit-approval-btn");

  const approveId = document.getElementById("task-approve-id");
  const approveDecision = document.getElementById("task-approve-decision");
  const approveNote = document.getElementById("task-approve-note");
  const approveBtn = document.getElementById("task-approve-btn");

  const commentId = document.getElementById("task-comment-id");
  const commentContent = document.getElementById("task-comment-content");
  const commentBtn = document.getElementById("task-comment-btn");

  const batchType = document.getElementById("task-batch-type");
  const batchTemplate = document.getElementById("task-batch-template");
  const batchNames = document.getElementById("task-batch-names");
  const batchBtn = document.getElementById("task-batch-create-btn");

  const commentsId = document.getElementById("task-comments-id");
  const commentsLoadBtn = document.getElementById("task-comments-load-btn");
  const commentsBox = document.getElementById("task-comments-box");

  const historyId = document.getElementById("task-history-id");
  const historyLoadBtn = document.getElementById("task-history-load-btn");
  const historyBox = document.getElementById("task-history-box");
  const selectionBanner = document.getElementById("task-selection-banner");

  if (!token || !resultNode) {
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

  async function get(path) {
    const resp = await fetch(path, {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-CSRF-Token": csrfToken,
      },
    });
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "请求失败，请稍后重试。");
    }
    return body;
  }

  function parseIntOrDefault(value, fallback) {
    const parsed = Number.parseInt(String(value || ""), 10);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return parsed;
  }

  function renderRows(rows, formatter, emptyText) {
    if (!Array.isArray(rows) || !rows.length) {
      return emptyText;
    }
    return rows.map(formatter).join("\n");
  }

  function setSelectedTask(taskId, taskName, taskState, assignedTo) {
    const safeTaskId = String(taskId || "").trim();
    if (!safeTaskId) {
      return;
    }
    [transitionTaskId, dispatchTaskId, submitApprovalId, approveId, commentId, commentsId, historyId].forEach((node) => {
      if (node) {
        node.value = safeTaskId;
      }
    });
    if (selectionBanner) {
      selectionBanner.innerHTML = [
        `<strong>当前选中任务：${safeTaskId}</strong>`,
        `<div class="selection-meta">任务名称：${taskName || "-"} | 当前状态：${taskState || "-"} | 处理人：${assignedTo || "-"}</div>`,
      ].join("");
    }
  }

  document.querySelectorAll(".js-task-select").forEach((button) => {
    button.addEventListener("click", () => {
      const taskId = button.getAttribute("data-task-id") || "";
      const taskName = button.getAttribute("data-task-name") || "";
      const taskState = button.getAttribute("data-task-state") || "";
      const assignedTo = button.getAttribute("data-task-assigned") || "";
      setSelectedTask(taskId, taskName, taskState, assignedTo);
      showResult("success", `已选中任务：${taskId}`);
    });
  });

  if (createBtn && createType && createName) {
    createBtn.addEventListener("click", async () => {
      const taskTypeId = (createType.value || "").trim();
      const templateId = (createTemplate && createTemplate.value ? createTemplate.value : "").trim();
      const name = (createName.value || "").trim();
      const priority = parseIntOrDefault(createPriority ? createPriority.value : "", 5);
      const riskLevel = parseIntOrDefault(createRisk ? createRisk.value : "", 3);
      if (!taskTypeId || !name) {
        showResult("warn", "请选择任务类型并填写任务名称。");
        return;
      }
      await withBusyButton(createBtn, "创建中...", async () => {
        try {
          const payload = {
            task_type_id: taskTypeId,
            name,
            priority,
            risk_level: riskLevel,
            area_geom: "",
          };
          if (templateId) {
            payload.template_id = templateId;
          }
          const row = await post("/api/task-center/tasks", payload);
          setSelectedTask(row.id, row.name || name, row.state || "", row.assigned_to || "-");
          showResult("success", `已创建任务：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (transitionBtn && transitionTaskId && transitionState) {
    transitionBtn.addEventListener("click", async () => {
      const taskId = (transitionTaskId.value || "").trim();
      const targetState = transitionState.value || "";
      const note = (transitionNote && transitionNote.value ? transitionNote.value : "").trim();
      if (!taskId || !targetState) {
        showResult("warn", "请先选择任务，并指定目标状态。");
        return;
      }
      await withBusyButton(transitionBtn, "更新中...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/transition`, {
            target_state: targetState,
            note: note || null,
          });
          setSelectedTask(body.id, body.name || "", body.state || "", body.assigned_to || "-");
          showResult("success", `任务已更新：${body.id} -> ${body.state}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (dispatchBtn && dispatchTaskId && dispatchUser) {
    dispatchBtn.addEventListener("click", async () => {
      const taskId = (dispatchTaskId.value || "").trim();
      const assignedTo = (dispatchUser.value || "").trim();
      const note = (dispatchNote && dispatchNote.value ? dispatchNote.value : "").trim();
      if (!taskId || !assignedTo) {
        showResult("warn", "请先选择任务，并填写处理人。");
        return;
      }
      await withBusyButton(dispatchBtn, "派发中...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/dispatch`, {
            assigned_to: assignedTo,
            note: note || null,
          });
          setSelectedTask(body.id, body.name || "", body.state || "", body.assigned_to || "-");
          showResult("success", `已派发任务：${body.id} -> ${body.assigned_to || "-"}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (submitApprovalBtn && submitApprovalId) {
    submitApprovalBtn.addEventListener("click", async () => {
      const taskId = (submitApprovalId.value || "").trim();
      const note = (submitApprovalNote && submitApprovalNote.value ? submitApprovalNote.value : "").trim();
      if (!taskId) {
        showResult("warn", "请先选择任务。");
        return;
      }
      await withBusyButton(submitApprovalBtn, "提交中...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/submit-approval`, {
            note: note || null,
          });
          setSelectedTask(body.id, body.name || "", body.state || "", body.assigned_to || "-");
          showResult("success", `已提交审批：${body.id} -> ${body.state}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approveBtn && approveId && approveDecision) {
    approveBtn.addEventListener("click", async () => {
      const taskId = (approveId.value || "").trim();
      const decision = (approveDecision.value || "").trim();
      const note = (approveNote && approveNote.value ? approveNote.value : "").trim();
      if (!taskId || !decision) {
        showResult("warn", "请先选择任务，并指定审批结果。");
        return;
      }
      await withBusyButton(approveBtn, "处理中...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/approve`, {
            decision,
            note: note || null,
          });
          setSelectedTask(body.id, body.name || "", body.state || "", body.assigned_to || "-");
          showResult("success", `已应用审批结果：${body.id} -> ${body.state}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (commentBtn && commentId && commentContent) {
    commentBtn.addEventListener("click", async () => {
      const taskId = (commentId.value || "").trim();
      const content = (commentContent.value || "").trim();
      if (!taskId || !content) {
        showResult("warn", "请先选择任务，并填写评论内容。");
        return;
      }
      await withBusyButton(commentBtn, "提交中...", async () => {
        try {
          await post(`/api/task-center/tasks/${taskId}/comments`, { content });
          showResult("success", `已为任务 ${taskId} 添加评论。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (batchBtn && batchType && batchNames) {
    batchBtn.addEventListener("click", async () => {
      const taskTypeId = (batchType.value || "").trim();
      const templateId = (batchTemplate && batchTemplate.value ? batchTemplate.value : "").trim();
      const names = (batchNames.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!taskTypeId || !names.length) {
        showResult("warn", "请选择任务类型，并至少填写一个任务名称。");
        return;
      }
      const tasks = names.map((name) => {
        const row = {
          task_type_id: taskTypeId,
          name,
          area_geom: "",
        };
        if (templateId) {
          row.template_id = templateId;
        }
        return row;
      });
      await withBusyButton(batchBtn, "创建中...", async () => {
        try {
          const body = await post("/api/task-center/tasks:batch-create", { tasks });
          showResult("success", `已批量创建 ${body.total} 个任务。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (commentsLoadBtn && commentsId && commentsBox) {
    commentsLoadBtn.addEventListener("click", async () => {
      const taskId = (commentsId.value || "").trim();
      if (!taskId) {
        showResult("warn", "请先选择任务。");
        return;
      }
      await withBusyButton(commentsLoadBtn, "加载中...", async () => {
        try {
          const rows = await get(`/api/task-center/tasks/${taskId}/comments`);
          commentsBox.textContent = renderRows(
            rows,
            (item) => `[${item.created_at}] ${item.created_by}: ${item.content}`,
            "暂无评论。",
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条评论。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (historyLoadBtn && historyId && historyBox) {
    historyLoadBtn.addEventListener("click", async () => {
      const taskId = (historyId.value || "").trim();
      if (!taskId) {
        showResult("warn", "请先选择任务。");
        return;
      }
      await withBusyButton(historyLoadBtn, "加载中...", async () => {
        try {
          const rows = await get(`/api/task-center/tasks/${taskId}/history`);
          historyBox.textContent = renderRows(
            rows,
            (item) =>
              `[${item.created_at}] ${item.action} ${item.from_state || "-"} -> ${item.to_state || "-"} (${item.actor_id || "-"})`,
            "暂无历史记录。",
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条历史记录。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
