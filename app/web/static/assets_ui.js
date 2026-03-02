(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const resultNode = document.getElementById("assets-result");

  const availabilityId = document.getElementById("asset-availability-id");
  const availabilityStatus = document.getElementById("asset-availability-status");
  const availabilityRegion = document.getElementById("asset-availability-region");
  const availabilityBtn = document.getElementById("asset-availability-btn");

  const healthId = document.getElementById("asset-availability-id");
  const healthStatus = document.getElementById("asset-health-status");
  const healthScore = document.getElementById("asset-health-score");
  const healthBtn = document.getElementById("asset-health-btn");

  const mwCreateAssetId = document.getElementById("mw-create-asset-id");
  const mwCreateTitle = document.getElementById("mw-create-title");
  const mwCreatePriority = document.getElementById("mw-create-priority");
  const mwCreateAssignedTo = document.getElementById("mw-create-assigned-to");
  const mwCreateNote = document.getElementById("mw-create-note");
  const mwCreateBtn = document.getElementById("mw-create-btn");

  const mwTransitionId = document.getElementById("mw-transition-id");
  const mwTransitionStatus = document.getElementById("mw-transition-status");
  const mwTransitionAssignedTo = document.getElementById("mw-transition-assigned-to");
  const mwTransitionNote = document.getElementById("mw-transition-note");
  const mwTransitionBtn = document.getElementById("mw-transition-btn");

  const mwCloseBtn = document.getElementById("mw-close-btn");
  const mwHistoryId = document.getElementById("mw-history-id");
  const mwHistoryBtn = document.getElementById("mw-history-btn");
  const mwHistoryBox = document.getElementById("mw-history-box");
  const assetSelectionBanner = document.getElementById("asset-selection-banner");
  const workorderSelectionBanner = document.getElementById("workorder-selection-banner");

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

  function setSelectedAsset(assetId, assetCode, assetType, regionCode) {
    const region = (regionCode || "").trim();
    if (availabilityId) {
      availabilityId.value = assetId;
    }
    if (mwCreateAssetId) {
      mwCreateAssetId.value = assetId;
    }
    if (availabilityRegion && region) {
      availabilityRegion.value = region;
    }
    if (assetSelectionBanner) {
      assetSelectionBanner.innerHTML = `<strong>当前资产：</strong>${assetCode || assetId}（${assetType || "未标注类型"}），资产 ID：<code>${assetId}</code>${region ? `，区域：${region}` : ""}`;
    }
  }

  function setSelectedWorkorder(workorderId, assetId, status, assignedTo) {
    if (mwTransitionId) {
      mwTransitionId.value = workorderId;
    }
    if (mwHistoryId) {
      mwHistoryId.value = workorderId;
    }
    if (mwCreateAssetId && assetId) {
      mwCreateAssetId.value = assetId;
    }
    if (mwTransitionAssignedTo && assignedTo) {
      mwTransitionAssignedTo.value = assignedTo;
    }
    if (workorderSelectionBanner) {
      workorderSelectionBanner.innerHTML = `<strong>当前工单：</strong><code>${workorderId}</code>，状态：${status || "-"}${assignedTo ? `，处理人：${assignedTo}` : ""}`;
    }
  }

  if (availabilityBtn && availabilityId && availabilityStatus) {
    availabilityBtn.addEventListener("click", async () => {
      const assetId = (availabilityId.value || "").trim();
      const status = availabilityStatus.value || "";
      const region = (availabilityRegion && availabilityRegion.value ? availabilityRegion.value : "").trim();
      if (!assetId || !status) {
        showResult("warn", "请先选择资产，并确认可用状态。");
        return;
      }
      const payload = { availability_status: status };
      if (region) {
        payload.region_code = region;
      }
      await withBusyButton(availabilityBtn, "提交中...", async () => {
        try {
          const body = await post(`/api/assets/${assetId}/availability`, payload);
          setSelectedAsset(body.id, "", "", body.region_code || region);
          showResult("success", `已更新资产可用状态：${body.id} -> ${body.availability_status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (healthBtn && healthId && healthStatus) {
    healthBtn.addEventListener("click", async () => {
      const assetId = (healthId.value || "").trim();
      const status = healthStatus.value || "";
      const scoreRaw = (healthScore && healthScore.value ? healthScore.value : "").trim();
      if (!assetId || !status) {
        showResult("warn", "请先选择资产，并确认健康状态。");
        return;
      }
      const payload = {
        health_status: status,
        detail: {},
      };
      if (scoreRaw) {
        payload.health_score = Number(scoreRaw);
      }
      await withBusyButton(healthBtn, "提交中...", async () => {
        try {
          const body = await post(`/api/assets/${assetId}/health`, payload);
          showResult("success", `已更新健康状态：${body.id} -> ${body.health_status}（${body.health_score ?? "-"}）`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (mwCreateBtn && mwCreateAssetId && mwCreateTitle) {
    mwCreateBtn.addEventListener("click", async () => {
      const assetId = (mwCreateAssetId.value || "").trim();
      const title = (mwCreateTitle.value || "").trim();
      const priority = parseIntOrDefault(mwCreatePriority ? mwCreatePriority.value : "", 5);
      const assignedTo = (mwCreateAssignedTo && mwCreateAssignedTo.value ? mwCreateAssignedTo.value : "").trim();
      const note = (mwCreateNote && mwCreateNote.value ? mwCreateNote.value : "").trim();
      if (!assetId || !title) {
        showResult("warn", "请先选择资产，并填写工单标题。");
        return;
      }
      await withBusyButton(mwCreateBtn, "创建中...", async () => {
        try {
          const payload = {
            asset_id: assetId,
            title,
            priority,
          };
          if (assignedTo) {
            payload.assigned_to = assignedTo;
          }
          if (note) {
            payload.note = note;
          }
          const body = await post("/api/assets/maintenance/workorders", payload);
          setSelectedWorkorder(body.id, body.asset_id, body.status, body.assigned_to || "");
          showResult("success", `已创建维护工单：${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (mwTransitionBtn && mwTransitionId && mwTransitionStatus) {
    mwTransitionBtn.addEventListener("click", async () => {
      const workorderId = (mwTransitionId.value || "").trim();
      const status = (mwTransitionStatus.value || "").trim();
      const assignedTo =
        (mwTransitionAssignedTo && mwTransitionAssignedTo.value ? mwTransitionAssignedTo.value : "").trim();
      const note = (mwTransitionNote && mwTransitionNote.value ? mwTransitionNote.value : "").trim();
      if (!workorderId || !status) {
        showResult("warn", "请先选择工单，并确认目标状态。");
        return;
      }
      await withBusyButton(mwTransitionBtn, "提交中...", async () => {
        try {
          const payload = { status };
          if (assignedTo) {
            payload.assigned_to = assignedTo;
          }
          if (note) {
            payload.note = note;
          }
          const body = await post(`/api/assets/maintenance/workorders/${workorderId}/transition`, payload);
          setSelectedWorkorder(body.id, body.asset_id || "", body.status, body.assigned_to || assignedTo);
          showResult("success", `已更新工单状态：${body.id} -> ${body.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (mwCloseBtn && mwTransitionId) {
    mwCloseBtn.addEventListener("click", async () => {
      const workorderId = (mwTransitionId.value || "").trim();
      const note = (mwTransitionNote && mwTransitionNote.value ? mwTransitionNote.value : "").trim();
      if (!workorderId) {
        showResult("warn", "请先选择工单。");
        return;
      }
      await withBusyButton(mwCloseBtn, "关闭中...", async () => {
        try {
          const body = await post(`/api/assets/maintenance/workorders/${workorderId}/close`, {
            note: note || null,
          });
          setSelectedWorkorder(body.id, body.asset_id || "", body.status, body.assigned_to || "");
          showResult("success", `已关闭工单：${body.id} -> ${body.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (mwHistoryBtn && mwHistoryId && mwHistoryBox) {
    mwHistoryBtn.addEventListener("click", async () => {
      const workorderId = (mwHistoryId.value || "").trim();
      if (!workorderId) {
        showResult("warn", "请先选择工单。");
        return;
      }
      await withBusyButton(mwHistoryBtn, "加载中...", async () => {
        try {
          const rows = await get(`/api/assets/maintenance/workorders/${workorderId}/history`);
          if (!Array.isArray(rows) || !rows.length) {
            mwHistoryBox.textContent = "暂无工单历史。";
          } else {
            mwHistoryBox.textContent = rows
              .map(
                (item) =>
                  `[${item.created_at}] ${item.action} ${item.from_status || "-"} -> ${item.to_status || "-"}（${item.actor_id || "-"}）`,
              )
              .join("\n");
          }
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条工单历史。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  document.querySelectorAll(".js-select-asset").forEach((button) => {
    button.addEventListener("click", () => {
      const assetId = button.getAttribute("data-asset-id") || "";
      const assetCode = button.getAttribute("data-asset-code") || "";
      const assetType = button.getAttribute("data-asset-type") || "";
      const regionCode = button.getAttribute("data-region-code") || "";
      setSelectedAsset(assetId, assetCode, assetType, regionCode);
      showResult("success", `已选中资产：${assetCode || assetId}`);
    });
  });

  document.querySelectorAll(".js-select-workorder").forEach((button) => {
    button.addEventListener("click", () => {
      const workorderId = button.getAttribute("data-workorder-id") || "";
      const assetId = button.getAttribute("data-asset-id") || "";
      const status = button.getAttribute("data-status") || "";
      const assignedTo = button.getAttribute("data-assigned-to") || "";
      setSelectedWorkorder(workorderId, assetId, status, assignedTo);
      if (assetId) {
        setSelectedAsset(assetId, "", "", availabilityRegion ? availabilityRegion.value : "");
      }
      showResult("success", `已选中工单：${workorderId}`);
    });
  });
})();
