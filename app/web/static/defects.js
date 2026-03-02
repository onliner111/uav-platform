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
  const selectionBanner = document.getElementById("defect-selection-banner");
  const assignRetryBtn = document.getElementById("assign-retry-btn");
  const statusRetryBtn = document.getElementById("status-retry-btn");
  const assignRetryHint = document.getElementById("assign-retry-hint");
  const statusRetryHint = document.getElementById("status-retry-hint");
  const networkText = document.getElementById("defect-network-text");
  const fieldNoteInput = document.getElementById("defect-field-note");
  const fieldNoteBtn = document.getElementById("defect-field-note-btn");
  const fieldNoteResult = document.getElementById("defect-field-note-result");

  let lastAssignPayload = null;
  let lastStatusPayload = null;

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
    if (resultNode) {
      resultNode.textContent = message;
    }
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

  function updateNetworkState() {
    if (!networkText) {
      return;
    }
    if (navigator.onLine) {
      networkText.textContent = "在线，可直接提交缺陷处理动作。";
      return;
    }
    networkText.textContent = "当前网络不稳定，建议保持当前选择并使用重试按钮恢复提交。";
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
      throw new Error(body.detail || "请求失败，请稍后重试。");
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
      throw new Error(body.detail || "请求失败，请稍后重试。");
    }
    return body;
  }

  updateNetworkState();
  window.addEventListener("online", updateNetworkState);
  window.addEventListener("offline", updateNetworkState);
  if (assignRetryHint) {
    assignRetryHint.textContent = "当前没有待重试的分派动作。";
  }
  if (statusRetryHint) {
    statusRetryHint.textContent = "当前没有待重试的状态动作。";
  }

  async function submitAssign(payload, triggerBtn, isRetry) {
    await withBusyButton(triggerBtn, isRetry ? "重试中..." : "分派中...", async () => {
      try {
        const body = await callApi(`/api/defects/${payload.defectId}/assign`, payload.request);
        lastAssignPayload = payload;
        if (assignRetryHint) {
          assignRetryHint.textContent = "上一笔分派已保留，可继续重试同样动作。";
        }
        showResult("success", `已完成分派，当前状态：${body.status}`);
      } catch (err) {
        lastAssignPayload = payload;
        if (assignRetryHint) {
          assignRetryHint.textContent = "上一笔分派已保留，网络恢复后可点击“重试上一笔分派”。";
        }
        showResult("danger", toMessage(err));
      }
    });
  }

  if (assignBtn) {
    assignBtn.addEventListener("click", async () => {
      const defectId = (defectIdInput && defectIdInput.value ? defectIdInput.value : "").trim();
      const assignedTo = (assignedToInput && assignedToInput.value ? assignedToInput.value : "").trim();
      if (!defectId || !assignedTo) {
        showResult("warn", "请先选择缺陷，并填写处理人。");
        return;
      }
      const note = (assignNoteInput && assignNoteInput.value ? assignNoteInput.value : "").trim();
      const request = { assigned_to: assignedTo };
      if (note) {
        request.note = note;
      }
      await submitAssign({ defectId, request }, assignBtn, false);
    });
  }

  if (assignRetryBtn) {
    assignRetryBtn.addEventListener("click", async () => {
      if (!lastAssignPayload) {
        showResult("warn", "当前没有可重试的分派动作。");
        return;
      }
      await submitAssign(lastAssignPayload, assignRetryBtn, true);
    });
  }

  async function submitStatus(payload, triggerBtn, isRetry) {
    await withBusyButton(triggerBtn, isRetry ? "重试中..." : "更新中...", async () => {
      try {
        const body = await callApi(`/api/defects/${payload.defectId}/status`, payload.request);
        lastStatusPayload = payload;
        if (statusRetryHint) {
          statusRetryHint.textContent = "上一笔状态动作已保留，可继续重试同样操作。";
        }
        showResult("success", `状态已更新：${body.status}`);
      } catch (err) {
        lastStatusPayload = payload;
        if (statusRetryHint) {
          statusRetryHint.textContent = "上一笔状态动作已保留，网络恢复后可点击“重试上一笔状态更新”。";
        }
        showResult("danger", toMessage(err));
      }
    });
  }

  if (statusBtn) {
    statusBtn.addEventListener("click", async () => {
      const defectId = (defectIdInput && defectIdInput.value ? defectIdInput.value : "").trim();
      const nextStatus = statusSelect ? statusSelect.value : "";
      if (!defectId || !nextStatus) {
        showResult("warn", "请先选择缺陷，并指定目标状态。");
        return;
      }
      const note = (statusNoteInput && statusNoteInput.value ? statusNoteInput.value : "").trim();
      const request = { status: nextStatus };
      if (note) {
        request.note = note;
      }
      await submitStatus({ defectId, request }, statusBtn, false);
    });
  }

  if (statusRetryBtn) {
    statusRetryBtn.addEventListener("click", async () => {
      if (!lastStatusPayload) {
        showResult("warn", "当前没有可重试的状态动作。");
        return;
      }
      await submitStatus(lastStatusPayload, statusRetryBtn, true);
    });
  }

  if (detailBtn && detailIdInput && detailBox) {
    detailBtn.addEventListener("click", async () => {
      const defectId = detailIdInput.value.trim();
      if (!defectId) {
        showResult("warn", "请先选择缺陷或填写缺陷 ID。");
        return;
      }
      await withBusyButton(detailBtn, "加载中...", async () => {
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
              : "暂无动作记录。",
          ].join("\n");
          if (defectIdInput) {
            defectIdInput.value = body.defect.id;
          }
          if (observationIdInput) {
            observationIdInput.value = body.defect.observation_id || "";
          }
          if (selectionBanner) {
            selectionBanner.innerHTML = `<strong>当前选中缺陷：${body.defect.id}</strong><div class="selection-meta">关联观察记录：${body.defect.observation_id || "-"}</div>`;
          }
          showResult("success", "已加载缺陷详情。");
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
      if (selectionBanner) {
        selectionBanner.innerHTML = `<strong>当前选中缺陷：${defectId}</strong><div class="selection-meta">关联观察记录：${observationId || "-"}</div>`;
      }
      showResult("success", `已选中缺陷：${defectId}`);
    });
  });

  if (fieldNoteBtn && fieldNoteResult) {
    fieldNoteBtn.addEventListener("click", () => {
      const note = (fieldNoteInput && fieldNoteInput.value ? fieldNoteInput.value : "").trim();
      if (!note) {
        fieldNoteResult.textContent = "请先填写现场补充说明。";
        return;
      }
      fieldNoteResult.textContent = `已记录现场补充：${note}`;
      showResult("success", "现场补充已记录，可继续处理当前缺陷。");
    });
  }

  if (statusBtn && statusBtn.disabled && assignBtn && assignBtn.disabled) {
    if (resultNode && resultNode.textContent.trim().length === 0) {
      showResult("warn", "当前为只读模式，写操作已禁用。");
    }
  }
})();
