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

  async function get(path) {
    const resp = await fetch(path, {
      headers: {
        Authorization: `Bearer ${token}`,
        "X-CSRF-Token": csrfToken,
      },
    });
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "request failed");
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

  if (createBtn && createType && createName) {
    createBtn.addEventListener("click", async () => {
      const taskTypeId = (createType.value || "").trim();
      const templateId = (createTemplate && createTemplate.value ? createTemplate.value : "").trim();
      const name = (createName.value || "").trim();
      const priority = parseIntOrDefault(createPriority ? createPriority.value : "", 5);
      const riskLevel = parseIntOrDefault(createRisk ? createRisk.value : "", 3);
      if (!taskTypeId || !name) {
        showResult("warn", "Task type and task name are required.");
        return;
      }
      await withBusyButton(createBtn, "Creating...", async () => {
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
          showResult("success", `Task created: ${row.id}`);
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
        showResult("warn", "Task ID and target state are required.");
        return;
      }
      await withBusyButton(transitionBtn, "Transitioning...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/transition`, {
            target_state: targetState,
            note: note || null,
          });
          showResult("success", `Transitioned: ${body.id} -> ${body.state}`);
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
        showResult("warn", "Task ID and assigned user are required.");
        return;
      }
      await withBusyButton(dispatchBtn, "Dispatching...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/dispatch`, {
            assigned_to: assignedTo,
            note: note || null,
          });
          showResult("success", `Dispatched: ${body.id} -> ${body.assigned_to || "-"}`);
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
        showResult("warn", "Task ID is required.");
        return;
      }
      await withBusyButton(submitApprovalBtn, "Submitting...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/submit-approval`, {
            note: note || null,
          });
          showResult("success", `Submitted for approval: ${body.id} -> ${body.state}`);
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
        showResult("warn", "Task ID and decision are required.");
        return;
      }
      await withBusyButton(approveBtn, "Applying...", async () => {
        try {
          const body = await post(`/api/task-center/tasks/${taskId}/approve`, {
            decision,
            note: note || null,
          });
          showResult("success", `Approval applied: ${body.id} -> ${body.state}`);
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
        showResult("warn", "Task ID and comment content are required.");
        return;
      }
      await withBusyButton(commentBtn, "Posting...", async () => {
        try {
          await post(`/api/task-center/tasks/${taskId}/comments`, { content });
          showResult("success", `Comment added for task ${taskId}.`);
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
        showResult("warn", "Task type and at least one task name are required.");
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
      await withBusyButton(batchBtn, "Creating...", async () => {
        try {
          const body = await post("/api/task-center/tasks:batch-create", { tasks });
          showResult("success", `Batch created ${body.total} tasks.`);
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
        showResult("warn", "Task ID is required.");
        return;
      }
      await withBusyButton(commentsLoadBtn, "Loading...", async () => {
        try {
          const rows = await get(`/api/task-center/tasks/${taskId}/comments`);
          commentsBox.textContent = renderRows(
            rows,
            (item) => `[${item.created_at}] ${item.created_by}: ${item.content}`,
            "No comments.",
          );
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} comments.`);
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
        showResult("warn", "Task ID is required.");
        return;
      }
      await withBusyButton(historyLoadBtn, "Loading...", async () => {
        try {
          const rows = await get(`/api/task-center/tasks/${taskId}/history`);
          historyBox.textContent = renderRows(
            rows,
            (item) =>
              `[${item.created_at}] ${item.action} ${item.from_state || "-"} -> ${item.to_state || "-"} (${item.actor_id || "-"})`,
            "No history.",
          );
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} history events.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
