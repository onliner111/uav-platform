(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canAlertWrite = Boolean(window.__CAN_ALERT_WRITE);

  const resultNode = document.getElementById("alerts-result");

  const ackId = document.getElementById("alert-ack-id");
  const ackComment = document.getElementById("alert-ack-comment");
  const ackBtn = document.getElementById("alert-ack-btn");

  const closeId = document.getElementById("alert-close-id");
  const closeComment = document.getElementById("alert-close-comment");
  const closeBtn = document.getElementById("alert-close-btn");

  const routingPriority = document.getElementById("routing-priority");
  const routingType = document.getElementById("routing-type");
  const routingChannel = document.getElementById("routing-channel");
  const routingTarget = document.getElementById("routing-target");
  const routingCreateBtn = document.getElementById("routing-create-btn");

  const oncallName = document.getElementById("oncall-name");
  const oncallTarget = document.getElementById("oncall-target");
  const oncallStartsAt = document.getElementById("oncall-starts-at");
  const oncallEndsAt = document.getElementById("oncall-ends-at");
  const oncallTimezone = document.getElementById("oncall-timezone");
  const oncallCreateBtn = document.getElementById("oncall-create-btn");

  const escalationPriority = document.getElementById("escalation-priority");
  const escalationAckTimeout = document.getElementById("escalation-ack-timeout");
  const escalationRepeatThreshold = document.getElementById("escalation-repeat-threshold");
  const escalationMaxLevel = document.getElementById("escalation-max-level");
  const escalationChannel = document.getElementById("escalation-channel");
  const escalationTarget = document.getElementById("escalation-target");
  const escalationCreateBtn = document.getElementById("escalation-create-btn");

  const escalationRunDry = document.getElementById("escalation-run-dry");
  const escalationRunLimit = document.getElementById("escalation-run-limit");
  const escalationRunBtn = document.getElementById("escalation-run-btn");
  const escalationRunBox = document.getElementById("escalation-run-box");

  const silenceName = document.getElementById("silence-name");
  const silenceType = document.getElementById("silence-type");
  const silenceDroneId = document.getElementById("silence-drone-id");
  const silenceStartsAt = document.getElementById("silence-starts-at");
  const silenceEndsAt = document.getElementById("silence-ends-at");
  const silenceCreateBtn = document.getElementById("silence-create-btn");

  const aggregationName = document.getElementById("aggregation-name");
  const aggregationType = document.getElementById("aggregation-type");
  const aggregationWindow = document.getElementById("aggregation-window");
  const aggregationCreateBtn = document.getElementById("aggregation-create-btn");

  const alertReviewId = document.getElementById("alert-review-id");
  const alertRoutesBtn = document.getElementById("alert-routes-btn");
  const alertActionsBtn = document.getElementById("alert-actions-btn");
  const alertReviewBtn = document.getElementById("alert-review-btn");
  const alertReviewBox = document.getElementById("alert-review-box");

  const alertActionId = document.getElementById("alert-action-id");
  const alertActionType = document.getElementById("alert-action-type");
  const alertActionNote = document.getElementById("alert-action-note");
  const alertActionBtn = document.getElementById("alert-action-btn");

  const routeReceiptId = document.getElementById("route-receipt-id");
  const routeReceiptStatus = document.getElementById("route-receipt-status");
  const routeReceiptBtn = document.getElementById("route-receipt-btn");

  const slaFromTs = document.getElementById("sla-from-ts");
  const slaToTs = document.getElementById("sla-to-ts");
  const slaLoadBtn = document.getElementById("sla-load-btn");
  const slaBox = document.getElementById("sla-box");

  const batchCloseIds = document.getElementById("batch-close-ids");
  const batchCloseComment = document.getElementById("batch-close-comment");
  const batchCloseBtn = document.getElementById("batch-close-btn");

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

  function parseIntOr(value, fallback) {
    const parsed = Number.parseInt(String(value || ""), 10);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return parsed;
  }

  function parseBool(value) {
    return String(value).toLowerCase() === "true";
  }

  function setAlertId(id) {
    const rowId = String(id || "").trim();
    if (!rowId) {
      return;
    }
    if (ackId) {
      ackId.value = rowId;
    }
    if (closeId) {
      closeId.value = rowId;
    }
    if (alertReviewId) {
      alertReviewId.value = rowId;
    }
    if (alertActionId) {
      alertActionId.value = rowId;
    }
  }

  document.querySelectorAll(".js-alert-select").forEach((button) => {
    button.addEventListener("click", () => {
      const rowId = button.getAttribute("data-alert-id") || "";
      setAlertId(rowId);
      showResult("success", `Selected alert: ${rowId}`);
    });
  });

  if (ackBtn && ackId) {
    ackBtn.addEventListener("click", async () => {
      const alertId = (ackId.value || "").trim();
      if (!alertId) {
        showResult("warn", "Alert ID is required.");
        return;
      }
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      await withBusyButton(ackBtn, "Acknowledging...", async () => {
        try {
          const body = await post(`/api/alert/alerts/${alertId}/ack`, {
            comment: (ackComment && ackComment.value ? ackComment.value : "").trim() || null,
          });
          showResult("success", `Acked alert ${body.id} -> ${body.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (closeBtn && closeId) {
    closeBtn.addEventListener("click", async () => {
      const alertId = (closeId.value || "").trim();
      if (!alertId) {
        showResult("warn", "Alert ID is required.");
        return;
      }
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      await withBusyButton(closeBtn, "Closing...", async () => {
        try {
          const body = await post(`/api/alert/alerts/${alertId}/close`, {
            comment: (closeComment && closeComment.value ? closeComment.value : "").trim() || null,
          });
          showResult("success", `Closed alert ${body.id} -> ${body.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (routingCreateBtn && routingPriority && routingChannel && routingTarget) {
    routingCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const target = (routingTarget.value || "").trim();
      if (!target) {
        showResult("warn", "Routing target is required.");
        return;
      }
      await withBusyButton(routingCreateBtn, "Creating...", async () => {
        try {
          const payload = {
            priority_level: routingPriority.value,
            channel: routingChannel.value,
            target,
            is_active: true,
            detail: {},
          };
          const typeValue = (routingType && routingType.value ? routingType.value : "").trim();
          if (typeValue) {
            payload.alert_type = typeValue;
          }
          const body = await post("/api/alert/routing-rules", payload);
          showResult("success", `Routing rule created: ${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (oncallCreateBtn && oncallName && oncallTarget && oncallStartsAt && oncallEndsAt && oncallTimezone) {
    oncallCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const shiftName = (oncallName.value || "").trim();
      const target = (oncallTarget.value || "").trim();
      const startsAt = (oncallStartsAt.value || "").trim();
      const endsAt = (oncallEndsAt.value || "").trim();
      if (!shiftName || !target || !startsAt || !endsAt) {
        showResult("warn", "Shift name, target, starts_at and ends_at are required.");
        return;
      }
      await withBusyButton(oncallCreateBtn, "Creating...", async () => {
        try {
          const body = await post("/api/alert/oncall/shifts", {
            shift_name: shiftName,
            target,
            starts_at: startsAt,
            ends_at: endsAt,
            timezone: (oncallTimezone.value || "UTC").trim() || "UTC",
            is_active: true,
            detail: {},
          });
          showResult("success", `Oncall shift created: ${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (
    escalationCreateBtn &&
    escalationPriority &&
    escalationAckTimeout &&
    escalationRepeatThreshold &&
    escalationMaxLevel &&
    escalationChannel &&
    escalationTarget
  ) {
    escalationCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      await withBusyButton(escalationCreateBtn, "Creating...", async () => {
        try {
          const body = await post("/api/alert/escalation-policies", {
            priority_level: escalationPriority.value,
            ack_timeout_seconds: parseIntOr(escalationAckTimeout.value, 1800),
            repeat_threshold: parseIntOr(escalationRepeatThreshold.value, 3),
            max_escalation_level: parseIntOr(escalationMaxLevel.value, 1),
            escalation_channel: escalationChannel.value,
            escalation_target: (escalationTarget.value || "").trim() || "oncall://active",
            is_active: true,
            detail: {},
          });
          showResult("success", `Escalation policy created: ${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (escalationRunBtn && escalationRunDry && escalationRunLimit && escalationRunBox) {
    escalationRunBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      await withBusyButton(escalationRunBtn, "Running...", async () => {
        try {
          const body = await post("/api/alert/alerts:escalation-run", {
            dry_run: parseBool(escalationRunDry.value),
            limit: parseIntOr(escalationRunLimit.value, 200),
          });
          const items = Array.isArray(body.items) ? body.items : [];
          escalationRunBox.textContent = [
            `scanned_count: ${body.scanned_count}`,
            `escalated_count: ${body.escalated_count}`,
            `dry_run: ${body.dry_run}`,
            "--- items ---",
            items.length
              ? items.map((item) => `${item.alert_id} ${item.reason} ${item.from_target || "-"} -> ${item.to_target}`).join("\n")
              : "No escalation items.",
          ].join("\n");
          showResult("success", `Escalation run completed: ${body.escalated_count} escalated.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (silenceCreateBtn && silenceName) {
    silenceCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const name = (silenceName.value || "").trim();
      if (!name) {
        showResult("warn", "Silence rule name is required.");
        return;
      }
      await withBusyButton(silenceCreateBtn, "Creating...", async () => {
        try {
          const payload = {
            name,
            is_active: true,
            detail: {},
          };
          const typeValue = (silenceType && silenceType.value ? silenceType.value : "").trim();
          const droneValue = (silenceDroneId && silenceDroneId.value ? silenceDroneId.value : "").trim();
          const startsAt = (silenceStartsAt && silenceStartsAt.value ? silenceStartsAt.value : "").trim();
          const endsAt = (silenceEndsAt && silenceEndsAt.value ? silenceEndsAt.value : "").trim();
          if (typeValue) {
            payload.alert_type = typeValue;
          }
          if (droneValue) {
            payload.drone_id = droneValue;
          }
          if (startsAt) {
            payload.starts_at = startsAt;
          }
          if (endsAt) {
            payload.ends_at = endsAt;
          }
          const body = await post("/api/alert/silence-rules", payload);
          showResult("success", `Silence rule created: ${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (aggregationCreateBtn && aggregationName && aggregationWindow) {
    aggregationCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const name = (aggregationName.value || "").trim();
      if (!name) {
        showResult("warn", "Aggregation rule name is required.");
        return;
      }
      await withBusyButton(aggregationCreateBtn, "Creating...", async () => {
        try {
          const payload = {
            name,
            window_seconds: parseIntOr(aggregationWindow.value, 300),
            is_active: true,
            detail: {},
          };
          const typeValue = (aggregationType && aggregationType.value ? aggregationType.value : "").trim();
          if (typeValue) {
            payload.alert_type = typeValue;
          }
          const body = await post("/api/alert/aggregation-rules", payload);
          showResult("success", `Aggregation rule created: ${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  function reviewedAlertId() {
    return (alertReviewId && alertReviewId.value ? alertReviewId.value : "").trim();
  }

  if (alertRoutesBtn && alertReviewBox) {
    alertRoutesBtn.addEventListener("click", async () => {
      const alertId = reviewedAlertId();
      if (!alertId) {
        showResult("warn", "Alert ID is required.");
        return;
      }
      await withBusyButton(alertRoutesBtn, "Loading...", async () => {
        try {
          const rows = await get(`/api/alert/alerts/${alertId}/routes`);
          alertReviewBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No route logs."
            : rows.map((item) => `[${item.created_at}] ${item.channel} ${item.target} ${item.delivery_status}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} route logs.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (alertActionsBtn && alertReviewBox) {
    alertActionsBtn.addEventListener("click", async () => {
      const alertId = reviewedAlertId();
      if (!alertId) {
        showResult("warn", "Alert ID is required.");
        return;
      }
      await withBusyButton(alertActionsBtn, "Loading...", async () => {
        try {
          const rows = await get(`/api/alert/alerts/${alertId}/actions`);
          alertReviewBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No action logs."
            : rows.map((item) => `[${item.created_at}] ${item.action_type} ${item.actor_id || "-"} ${item.note || ""}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} action logs.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (alertReviewBtn && alertReviewBox) {
    alertReviewBtn.addEventListener("click", async () => {
      const alertId = reviewedAlertId();
      if (!alertId) {
        showResult("warn", "Alert ID is required.");
        return;
      }
      await withBusyButton(alertReviewBtn, "Loading...", async () => {
        try {
          const body = await get(`/api/alert/alerts/${alertId}/review`);
          const routes = Array.isArray(body.routes) ? body.routes.length : 0;
          const actions = Array.isArray(body.actions) ? body.actions.length : 0;
          alertReviewBox.textContent = [
            `alert_id: ${body.alert.id}`,
            `type: ${body.alert.alert_type}`,
            `priority: ${body.alert.priority_level}`,
            `status: ${body.alert.status}`,
            `route_count: ${routes}`,
            `action_count: ${actions}`,
          ].join("\n");
          showResult("success", "Loaded alert review.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (alertActionBtn && alertActionId && alertActionType) {
    alertActionBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const alertId = (alertActionId.value || "").trim();
      if (!alertId) {
        showResult("warn", "Alert ID is required.");
        return;
      }
      await withBusyButton(alertActionBtn, "Submitting...", async () => {
        try {
          const body = await post(`/api/alert/alerts/${alertId}/actions`, {
            action_type: alertActionType.value,
            note: (alertActionNote && alertActionNote.value ? alertActionNote.value : "").trim() || null,
            detail: {},
          });
          showResult("success", `Action added: ${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (routeReceiptBtn && routeReceiptId && routeReceiptStatus) {
    routeReceiptBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const routeId = (routeReceiptId.value || "").trim();
      if (!routeId) {
        showResult("warn", "Route log ID is required.");
        return;
      }
      await withBusyButton(routeReceiptBtn, "Submitting...", async () => {
        try {
          const body = await post(`/api/alert/routes/${routeId}:receipt`, {
            delivery_status: routeReceiptStatus.value,
            receipt_id: null,
            detail: {},
          });
          showResult("success", `Route receipt updated: ${body.id} -> ${body.delivery_status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (slaLoadBtn && slaBox) {
    slaLoadBtn.addEventListener("click", async () => {
      await withBusyButton(slaLoadBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const fromTs = (slaFromTs && slaFromTs.value ? slaFromTs.value : "").trim();
          const toTs = (slaToTs && slaToTs.value ? slaToTs.value : "").trim();
          if (fromTs) {
            params.set("from_ts", fromTs);
          }
          if (toTs) {
            params.set("to_ts", toTs);
          }
          const query = params.toString();
          const body = await get(`/api/alert/sla/overview${query ? `?${query}` : ""}`);
          slaBox.textContent = [
            `total_alerts: ${body.total_alerts}`,
            `acked_alerts: ${body.acked_alerts}`,
            `closed_alerts: ${body.closed_alerts}`,
            `timeout_escalated_alerts: ${body.timeout_escalated_alerts}`,
            `mtta_seconds_avg: ${body.mtta_seconds_avg}`,
            `mttr_seconds_avg: ${body.mttr_seconds_avg}`,
            `timeout_escalation_rate: ${body.timeout_escalation_rate}`,
          ].join("\n");
          showResult("success", "Loaded SLA overview.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (batchCloseBtn && batchCloseIds) {
    batchCloseBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "Read-only mode: alert write actions are disabled.");
        return;
      }
      const ids = (batchCloseIds.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!ids.length) {
        showResult("warn", "At least one alert ID is required.");
        return;
      }
      const comment = (batchCloseComment && batchCloseComment.value ? batchCloseComment.value : "").trim() || null;
      await withBusyButton(batchCloseBtn, "Closing...", async () => {
        let success = 0;
        const failures = [];
        for (const alertId of ids) {
          try {
            await post(`/api/alert/alerts/${alertId}/close`, { comment });
            success += 1;
          } catch (err) {
            failures.push(`${alertId}: ${toMessage(err)}`);
          }
        }
        if (!failures.length) {
          showResult("success", `Batch close completed: ${success}/${ids.length} succeeded.`);
          return;
        }
        showResult("warn", `Batch close partial: ${success}/${ids.length} succeeded. ${failures.join(" | ")}`);
      });
    });
  }

  if (!canAlertWrite) {
    showResult("warn", "Read-only mode: alert write actions are disabled.");
  }
})();
