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

  const healthId = document.getElementById("asset-health-id");
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

  if (availabilityBtn && availabilityId && availabilityStatus) {
    availabilityBtn.addEventListener("click", async () => {
      const assetId = (availabilityId.value || "").trim();
      const status = availabilityStatus.value || "";
      const region = (availabilityRegion && availabilityRegion.value ? availabilityRegion.value : "").trim();
      if (!assetId || !status) {
        showResult("warn", "Asset ID and availability status are required.");
        return;
      }
      const payload = { availability_status: status };
      if (region) {
        payload.region_code = region;
      }
      await withBusyButton(availabilityBtn, "Applying...", async () => {
        try {
          const body = await post(`/api/assets/${assetId}/availability`, payload);
          showResult("success", `Availability updated: ${body.id} -> ${body.availability_status}`);
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
        showResult("warn", "Asset ID and health status are required.");
        return;
      }
      const payload = {
        health_status: status,
        detail: {},
      };
      if (scoreRaw) {
        payload.health_score = Number(scoreRaw);
      }
      await withBusyButton(healthBtn, "Applying...", async () => {
        try {
          const body = await post(`/api/assets/${assetId}/health`, payload);
          showResult("success", `Health updated: ${body.id} -> ${body.health_status} (${body.health_score ?? "-"})`);
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
        showResult("warn", "Asset ID and title are required.");
        return;
      }
      await withBusyButton(mwCreateBtn, "Creating...", async () => {
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
          showResult("success", `Workorder created: ${body.id}`);
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
        showResult("warn", "Workorder ID and target status are required.");
        return;
      }
      await withBusyButton(mwTransitionBtn, "Applying...", async () => {
        try {
          const payload = { status };
          if (assignedTo) {
            payload.assigned_to = assignedTo;
          }
          if (note) {
            payload.note = note;
          }
          const body = await post(`/api/assets/maintenance/workorders/${workorderId}/transition`, payload);
          showResult("success", `Workorder transitioned: ${body.id} -> ${body.status}`);
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
        showResult("warn", "Workorder ID is required.");
        return;
      }
      await withBusyButton(mwCloseBtn, "Closing...", async () => {
        try {
          const body = await post(`/api/assets/maintenance/workorders/${workorderId}/close`, {
            note: note || null,
          });
          showResult("success", `Workorder closed: ${body.id} -> ${body.status}`);
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
        showResult("warn", "Workorder ID is required.");
        return;
      }
      await withBusyButton(mwHistoryBtn, "Loading...", async () => {
        try {
          const rows = await get(`/api/assets/maintenance/workorders/${workorderId}/history`);
          if (!Array.isArray(rows) || !rows.length) {
            mwHistoryBox.textContent = "No history.";
          } else {
            mwHistoryBox.textContent = rows
              .map(
                (item) =>
                  `[${item.created_at}] ${item.action} ${item.from_status || "-"} -> ${item.to_status || "-"} (${item.actor_id || "-"})`,
              )
              .join("\n");
          }
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} history rows.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
