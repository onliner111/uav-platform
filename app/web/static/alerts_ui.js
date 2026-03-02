(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canAlertWrite = Boolean(window.__CAN_ALERT_WRITE);
  const selectionBanner = document.getElementById("alert-selection-banner");

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
    if (selectionBanner) {
      selectionBanner.innerHTML = `<strong>当前选中告警：${rowId}</strong><div class="selection-meta">协同处理区已自动带入当前告警，可直接执行确认、关闭、补充动作或复盘。</div>`;
    }
  }

  document.querySelectorAll(".js-alert-select").forEach((button) => {
    button.addEventListener("click", () => {
      const rowId = button.getAttribute("data-alert-id") || "";
      setAlertId(rowId);
      showResult("success", `已选中告警：${rowId}`);
    });
  });

  if (ackBtn && ackId) {
    ackBtn.addEventListener("click", async () => {
      const alertId = (ackId.value || "").trim();
      if (!alertId) {
        showResult("warn", "请先选择告警。");
        return;
      }
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      await withBusyButton(ackBtn, "确认中...", async () => {
        try {
          const body = await post(`/api/alert/alerts/${alertId}/ack`, {
            comment: (ackComment && ackComment.value ? ackComment.value : "").trim() || null,
          });
          showResult("success", `已确认告警：${body.id} -> ${body.status}`);
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
        showResult("warn", "请先选择告警。");
        return;
      }
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      await withBusyButton(closeBtn, "关闭中...", async () => {
        try {
          const body = await post(`/api/alert/alerts/${alertId}/close`, {
            comment: (closeComment && closeComment.value ? closeComment.value : "").trim() || null,
          });
          showResult("success", `已关闭告警：${body.id} -> ${body.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (routingCreateBtn && routingPriority && routingChannel && routingTarget) {
    routingCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const target = (routingTarget.value || "").trim();
      if (!target) {
        showResult("warn", "请填写通知目标。");
        return;
      }
      await withBusyButton(routingCreateBtn, "创建中...", async () => {
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
          showResult("success", `已创建路由规则：${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (oncallCreateBtn && oncallName && oncallTarget && oncallStartsAt && oncallEndsAt && oncallTimezone) {
    oncallCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const shiftName = (oncallName.value || "").trim();
      const target = (oncallTarget.value || "").trim();
      const startsAt = (oncallStartsAt.value || "").trim();
      const endsAt = (oncallEndsAt.value || "").trim();
      if (!shiftName || !target || !startsAt || !endsAt) {
        showResult("warn", "请填写班次名称、通知目标、开始时间和结束时间。");
        return;
      }
      await withBusyButton(oncallCreateBtn, "创建中...", async () => {
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
          showResult("success", `已创建值守班次：${body.id}`);
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
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      await withBusyButton(escalationCreateBtn, "创建中...", async () => {
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
          showResult("success", `已创建升级策略：${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (escalationRunBtn && escalationRunDry && escalationRunLimit && escalationRunBox) {
    escalationRunBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      await withBusyButton(escalationRunBtn, "执行中...", async () => {
        try {
          const body = await post("/api/alert/alerts:escalation-run", {
            dry_run: parseBool(escalationRunDry.value),
            limit: parseIntOr(escalationRunLimit.value, 200),
          });
          const items = Array.isArray(body.items) ? body.items : [];
          escalationRunBox.textContent = [
            `扫描数量: ${body.scanned_count}`,
            `升级数量: ${body.escalated_count}`,
            `演练模式: ${body.dry_run}`,
            "--- 明细 ---",
            items.length
              ? items.map((item) => `${item.alert_id} ${item.reason} ${item.from_target || "-"} -> ${item.to_target}`).join("\n")
              : "暂无升级项。",
          ].join("\n");
          showResult("success", `升级策略执行完成：已升级 ${body.escalated_count} 条。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (silenceCreateBtn && silenceName) {
    silenceCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const name = (silenceName.value || "").trim();
      if (!name) {
        showResult("warn", "请填写静默规则名称。");
        return;
      }
      await withBusyButton(silenceCreateBtn, "创建中...", async () => {
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
          showResult("success", `已创建静默规则：${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (aggregationCreateBtn && aggregationName && aggregationWindow) {
    aggregationCreateBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const name = (aggregationName.value || "").trim();
      if (!name) {
        showResult("warn", "请填写聚合规则名称。");
        return;
      }
      await withBusyButton(aggregationCreateBtn, "创建中...", async () => {
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
          showResult("success", `已创建聚合规则：${body.id}`);
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
        showResult("warn", "请先选择告警。");
        return;
      }
      await withBusyButton(alertRoutesBtn, "加载中...", async () => {
        try {
          const rows = await get(`/api/alert/alerts/${alertId}/routes`);
          alertReviewBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无路由日志。"
            : rows.map((item) => `[${item.created_at}] ${item.channel} ${item.target} ${item.delivery_status}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条路由日志。`);
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
        showResult("warn", "请先选择告警。");
        return;
      }
      await withBusyButton(alertActionsBtn, "加载中...", async () => {
        try {
          const rows = await get(`/api/alert/alerts/${alertId}/actions`);
          alertReviewBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无动作日志。"
            : rows.map((item) => `[${item.created_at}] ${item.action_type} ${item.actor_id || "-"} ${item.note || ""}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条动作日志。`);
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
        showResult("warn", "请先选择告警。");
        return;
      }
      await withBusyButton(alertReviewBtn, "加载中...", async () => {
        try {
          const body = await get(`/api/alert/alerts/${alertId}/review`);
          const routes = Array.isArray(body.routes) ? body.routes.length : 0;
          const actions = Array.isArray(body.actions) ? body.actions.length : 0;
          alertReviewBox.textContent = [
            `告警标识: ${body.alert.id}`,
            `告警类型: ${body.alert.alert_type}`,
            `优先级: ${body.alert.priority_level}`,
            `当前状态: ${body.alert.status}`,
            `路由数量: ${routes}`,
            `动作数量: ${actions}`,
          ].join("\n");
          showResult("success", "已加载告警复盘。");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (alertActionBtn && alertActionId && alertActionType) {
    alertActionBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const alertId = (alertActionId.value || "").trim();
      if (!alertId) {
        showResult("warn", "请先选择告警。");
        return;
      }
      await withBusyButton(alertActionBtn, "提交中...", async () => {
        try {
          const body = await post(`/api/alert/alerts/${alertId}/actions`, {
            action_type: alertActionType.value,
            note: (alertActionNote && alertActionNote.value ? alertActionNote.value : "").trim() || null,
            detail: {},
          });
          showResult("success", `已补充处理动作：${body.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (routeReceiptBtn && routeReceiptId && routeReceiptStatus) {
    routeReceiptBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const routeId = (routeReceiptId.value || "").trim();
      if (!routeId) {
        showResult("warn", "请填写路由日志标识。");
        return;
      }
      await withBusyButton(routeReceiptBtn, "提交中...", async () => {
        try {
          const body = await post(`/api/alert/routes/${routeId}:receipt`, {
            delivery_status: routeReceiptStatus.value,
            receipt_id: null,
            detail: {},
          });
          showResult("success", `已更新回执状态：${body.id} -> ${body.delivery_status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (slaLoadBtn && slaBox) {
    slaLoadBtn.addEventListener("click", async () => {
      await withBusyButton(slaLoadBtn, "加载中...", async () => {
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
            `告警总量: ${body.total_alerts}`,
            `已确认: ${body.acked_alerts}`,
            `已关闭: ${body.closed_alerts}`,
            `超时升级: ${body.timeout_escalated_alerts}`,
            `平均确认时长(秒): ${body.mtta_seconds_avg}`,
            `平均恢复时长(秒): ${body.mttr_seconds_avg}`,
            `超时升级占比: ${body.timeout_escalation_rate}`,
          ].join("\n");
          showResult("success", "已加载值守 SLA 概览。");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (batchCloseBtn && batchCloseIds) {
    batchCloseBtn.addEventListener("click", async () => {
      if (!canAlertWrite) {
        showResult("warn", "当前为只读模式，告警写入动作已禁用。");
        return;
      }
      const ids = (batchCloseIds.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!ids.length) {
        showResult("warn", "请至少提供一条告警标识。");
        return;
      }
      const comment = (batchCloseComment && batchCloseComment.value ? batchCloseComment.value : "").trim() || null;
      await withBusyButton(batchCloseBtn, "关闭中...", async () => {
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
          showResult("success", `批量关闭已完成：成功 ${success}/${ids.length}。`);
          return;
        }
        showResult("warn", `批量关闭部分完成：成功 ${success}/${ids.length}。${failures.join(" | ")}`);
      });
    });
  }

  if (!canAlertWrite) {
    showResult("warn", "当前为只读模式，告警写入动作已禁用。");
  }
})();
