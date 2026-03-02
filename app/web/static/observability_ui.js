(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canObservabilityWrite = Boolean(window.__CAN_OBSERVABILITY_WRITE);

  const resultNode = document.getElementById("observability-result");
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
    return String((err && err.message) || err || "请求失败");
  }

  async function withBusyButton(button, pendingLabel, action) {
    if (ui && typeof ui.withBusyButton === "function") {
      await ui.withBusyButton(button, pendingLabel, action);
      return;
    }
    await action();
  }

  function parseIntOr(value, fallback) {
    const parsed = Number.parseInt(String(value || "").trim(), 10);
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function parseFloatOr(value, fallback) {
    const parsed = Number.parseFloat(String(value || "").trim());
    return Number.isFinite(parsed) ? parsed : fallback;
  }

  function splitCsv(value) {
    return String(value || "")
      .split(",")
      .map((item) => item.trim())
      .filter(Boolean);
  }

  function renderLines(rows, formatter) {
    if (!Array.isArray(rows) || !rows.length) {
      return "暂无记录。";
    }
    return rows.map(formatter).join("\n");
  }

  async function request(path, method, payload) {
    const response = await fetch(path, {
      method,
      headers: {
        Authorization: `Bearer ${token}`,
        "X-CSRF-Token": csrfToken,
        ...(payload ? { "Content-Type": "application/json" } : {}),
      },
      ...(payload ? { body: JSON.stringify(payload) } : {}),
    });
    const body = await response.json();
    if (!response.ok) {
      throw new Error(body.detail || "请求失败");
    }
    return body;
  }

  const signalServiceName = document.getElementById("obv-signal-service-name");
  const signalName = document.getElementById("obv-signal-name");
  const signalType = document.getElementById("obv-signal-type");
  const signalLevel = document.getElementById("obv-signal-level");
  const signalLimit = document.getElementById("obv-signal-limit");
  const signalLoadBtn = document.getElementById("obv-signal-load-btn");
  const signalIngestBtn = document.getElementById("obv-signal-ingest-btn");
  const signalBox = document.getElementById("obv-signal-box");

  if (signalLoadBtn && signalBox) {
    signalLoadBtn.addEventListener("click", async () => {
      await withBusyButton(signalLoadBtn, "加载中...", async () => {
        try {
          const params = new URLSearchParams();
          if (signalServiceName && signalServiceName.value.trim()) {
            params.set("service_name", signalServiceName.value.trim());
          }
          if (signalName && signalName.value.trim()) {
            params.set("signal_name", signalName.value.trim());
          }
          if (signalType && signalType.value) {
            params.set("signal_type", signalType.value);
          }
          if (signalLevel && signalLevel.value) {
            params.set("level", signalLevel.value);
          }
          params.set("limit", String(parseIntOr(signalLimit && signalLimit.value, 20)));
          const rows = await request(`/api/observability/signals?${params.toString()}`, "GET");
          signalBox.textContent = renderLines(
            rows,
            (item) =>
              `${item.occurred_at} ${item.service_name}.${item.signal_name} ${item.signal_type}/${item.level} status=${item.status_code || "-"} latency=${item.duration_ms || "-"}`,
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条信号记录。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (signalIngestBtn && signalBox) {
    signalIngestBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      await withBusyButton(signalIngestBtn, "写入中...", async () => {
        try {
          const serviceNameValue = (signalServiceName && signalServiceName.value ? signalServiceName.value : "").trim() || "mission-dispatch";
          const signalNameValue = (signalName && signalName.value ? signalName.value : "").trim() || "request";
          const now = new Date().toISOString();
          const payload = {
            items: [
              {
                signal_type: "METRIC",
                level: "INFO",
                service_name: serviceNameValue,
                signal_name: signalNameValue,
                status_code: 200,
                duration_ms: 120,
                numeric_value: 1,
                unit: "count",
                occurred_at: now,
              },
              {
                signal_type: "METRIC",
                level: "ERROR",
                service_name: serviceNameValue,
                signal_name: signalNameValue,
                status_code: 500,
                duration_ms: 900,
                numeric_value: 1,
                unit: "count",
                occurred_at: now,
              },
              {
                signal_type: "TRACE",
                level: "INFO",
                service_name: serviceNameValue,
                signal_name: signalNameValue,
                trace_id: "ui-phase31-trace",
                span_id: "ui-phase31-span",
                duration_ms: 240,
                occurred_at: now,
              },
            ],
          };
          const row = await request("/api/observability/signals:ingest", "POST", payload);
          signalBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `已接收 ${row.accepted_count} 条模拟信号。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const sloPolicyKey = document.getElementById("obv-slo-policy-key");
  const sloServiceName = document.getElementById("obv-slo-service-name");
  const sloSignalName = document.getElementById("obv-slo-signal-name");
  const sloTargetRatio = document.getElementById("obv-slo-target-ratio");
  const sloWindowMinutes = document.getElementById("obv-slo-window-minutes");
  const sloMinSamples = document.getElementById("obv-slo-min-samples");
  const sloLatencyThreshold = document.getElementById("obv-slo-latency-threshold");
  const sloAlertSeverity = document.getElementById("obv-slo-alert-severity");
  const sloCreateBtn = document.getElementById("obv-slo-create-btn");
  const sloPolicyIds = document.getElementById("obv-slo-policy-ids");
  const sloDryRun = document.getElementById("obv-slo-dry-run");
  const sloEvaluateBtn = document.getElementById("obv-slo-evaluate-btn");
  const sloBox = document.getElementById("obv-slo-box");

  if (sloCreateBtn && sloBox) {
    sloCreateBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      await withBusyButton(sloCreateBtn, "创建中...", async () => {
        try {
          const policyKey = (sloPolicyKey && sloPolicyKey.value ? sloPolicyKey.value : "").trim();
          const serviceNameValue = (sloServiceName && sloServiceName.value ? sloServiceName.value : "").trim();
          if (!policyKey || !serviceNameValue) {
            showResult("warn", "必须填写策略标识和服务名称。");
            return;
          }
          const payload = {
            policy_key: policyKey,
            service_name: serviceNameValue,
            signal_name: (sloSignalName && sloSignalName.value ? sloSignalName.value : "").trim() || "request",
            target_ratio: parseFloatOr(sloTargetRatio && sloTargetRatio.value, 0.95),
            window_minutes: parseIntOr(sloWindowMinutes && sloWindowMinutes.value, 60),
            minimum_samples: parseIntOr(sloMinSamples && sloMinSamples.value, 1),
            alert_severity: sloAlertSeverity && sloAlertSeverity.value ? sloAlertSeverity.value : "P2",
            detail: { source: "ui-observability" },
          };
          const latencyValue = parseIntOr(sloLatencyThreshold && sloLatencyThreshold.value, 0);
          if (latencyValue > 0) {
            payload.latency_threshold_ms = latencyValue;
          }
          const row = await request("/api/observability/slo/policies", "POST", payload);
          if (sloPolicyIds) {
            sloPolicyIds.value = row.id;
          }
          sloBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `SLO 策略已创建: ${row.policy_key}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (sloEvaluateBtn && sloBox) {
    sloEvaluateBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      await withBusyButton(sloEvaluateBtn, "评估中...", async () => {
        try {
          const payload = {
            policy_ids: splitCsv(sloPolicyIds && sloPolicyIds.value),
            window_minutes: parseIntOr(sloWindowMinutes && sloWindowMinutes.value, 60),
            dry_run: Boolean(sloDryRun && sloDryRun.value === "true"),
          };
          const row = await request("/api/observability/slo:evaluate", "POST", payload);
          sloBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `已评估 ${row.evaluated_count} 条策略，触发违规 ${row.breached_count} 条。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const alertStatus = document.getElementById("obv-alert-status");
  const alertSource = document.getElementById("obv-alert-source");
  const alertLimit = document.getElementById("obv-alert-limit");
  const alertLoadBtn = document.getElementById("obv-alert-load-btn");
  const alertBox = document.getElementById("obv-alert-box");

  if (alertLoadBtn && alertBox) {
    alertLoadBtn.addEventListener("click", async () => {
      await withBusyButton(alertLoadBtn, "加载中...", async () => {
        try {
          const params = new URLSearchParams();
          if (alertStatus && alertStatus.value) {
            params.set("status", alertStatus.value);
          }
          if (alertSource && alertSource.value.trim()) {
            params.set("source", alertSource.value.trim());
          }
          params.set("limit", String(parseIntOr(alertLimit && alertLimit.value, 12)));
          const rows = await request(`/api/observability/alerts?${params.toString()}`, "GET");
          alertBox.textContent = renderLines(
            rows,
            (item) => `${item.created_at} ${item.severity} ${item.status} ${item.title} target=${item.target || "-"}`,
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条告警事件。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
