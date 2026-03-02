(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canObservabilityWrite = Boolean(window.__CAN_OBSERVABILITY_WRITE);

  const resultNode = document.getElementById("reliability-result");
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

  const backupRunType = document.getElementById("rel-backup-run-type");
  const backupStorageUri = document.getElementById("rel-backup-storage-uri");
  const backupIsDrill = document.getElementById("rel-backup-is-drill");
  const backupRunBtn = document.getElementById("rel-backup-run-btn");
  const restoreBackupId = document.getElementById("rel-restore-backup-id");
  const restoreObjectiveRto = document.getElementById("rel-restore-objective-rto");
  const restoreSimulatedRto = document.getElementById("rel-restore-simulated-rto");
  const restoreRunBtn = document.getElementById("rel-restore-run-btn");
  const backupBox = document.getElementById("rel-backup-box");

  if (backupRunBtn && backupBox) {
    backupRunBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      await withBusyButton(backupRunBtn, "执行中...", async () => {
        try {
          const payload = {
            run_type: backupRunType && backupRunType.value ? backupRunType.value : "FULL",
            is_drill: Boolean(backupIsDrill && backupIsDrill.value === "true"),
            detail: { source: "ui-reliability" },
          };
          const storageUri = (backupStorageUri && backupStorageUri.value ? backupStorageUri.value : "").trim();
          if (storageUri) {
            payload.storage_uri = storageUri;
          }
          const row = await request("/api/observability/backups:runs", "POST", payload);
          if (restoreBackupId) {
            restoreBackupId.value = row.id;
          }
          backupBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `备份任务已创建: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (restoreRunBtn && backupBox) {
    restoreRunBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      const backupRunId = (restoreBackupId && restoreBackupId.value ? restoreBackupId.value : "").trim();
      if (!backupRunId) {
        showResult("warn", "必须填写备份任务 ID。");
        return;
      }
      await withBusyButton(restoreRunBtn, "执行中...", async () => {
        try {
          const row = await request(
            `/api/observability/backups/runs/${backupRunId}:restore-drill`,
            "POST",
            {
              objective_rto_seconds: parseIntOr(restoreObjectiveRto && restoreObjectiveRto.value, 300),
              simulated_restore_seconds: parseIntOr(restoreSimulatedRto && restoreSimulatedRto.value, 180),
              detail: { source: "ui-reliability" },
            },
          );
          backupBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `恢复演练已完成: ${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const securityBaseline = document.getElementById("rel-security-baseline");
  const securityRunBtn = document.getElementById("rel-security-run-btn");
  const forecastMeterKey = document.getElementById("rel-forecast-meter-key");
  const forecastWindowMinutes = document.getElementById("rel-forecast-window-minutes");
  const forecastSampleMinutes = document.getElementById("rel-forecast-sample-minutes");
  const forecastRunBtn = document.getElementById("rel-forecast-run-btn");
  const securityBox = document.getElementById("rel-security-box");

  if (securityRunBtn && securityBox) {
    securityRunBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      await withBusyButton(securityRunBtn, "执行中...", async () => {
        try {
          const row = await request("/api/observability/security-inspections:runs", "POST", {
            baseline_version: (securityBaseline && securityBaseline.value ? securityBaseline.value : "").trim() || "phase31-v1",
            detail: { source: "ui-reliability" },
          });
          securityBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `安全巡检得分: ${row.score_percent}%`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (forecastRunBtn && securityBox) {
    forecastRunBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      await withBusyButton(forecastRunBtn, "预测中...", async () => {
        try {
          const meterKeyValue = (forecastMeterKey && forecastMeterKey.value ? forecastMeterKey.value : "").trim();
          if (!meterKeyValue) {
            showResult("warn", "必须填写预测指标标识。");
            return;
          }
          const row = await request("/api/observability/capacity:forecast", "POST", {
            meter_key: meterKeyValue,
            window_minutes: parseIntOr(forecastWindowMinutes && forecastWindowMinutes.value, 60),
            sample_minutes: parseIntOr(forecastSampleMinutes && forecastSampleMinutes.value, 180),
          });
          securityBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `容量预测建议: ${row.decision}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const capacityMeterKey = document.getElementById("rel-capacity-meter-key");
  const capacityTarget = document.getElementById("rel-capacity-target");
  const capacityScaleOut = document.getElementById("rel-capacity-scale-out");
  const capacityScaleIn = document.getElementById("rel-capacity-scale-in");
  const capacityMinReplicas = document.getElementById("rel-capacity-min-replicas");
  const capacityMaxReplicas = document.getElementById("rel-capacity-max-replicas");
  const capacityCurrentReplicas = document.getElementById("rel-capacity-current-replicas");
  const capacityUpsertBtn = document.getElementById("rel-capacity-upsert-btn");
  const capacityBox = document.getElementById("rel-capacity-box");

  if (capacityUpsertBtn && capacityBox) {
    capacityUpsertBtn.addEventListener("click", async () => {
      if (!canObservabilityWrite) {
        showResult("warn", "需要 observability.write 权限。");
        return;
      }
      const meterKeyValue = (capacityMeterKey && capacityMeterKey.value ? capacityMeterKey.value : "").trim();
      if (!meterKeyValue) {
        showResult("warn", "必须填写容量指标标识。");
        return;
      }
      await withBusyButton(capacityUpsertBtn, "保存中...", async () => {
        try {
          const row = await request(
            `/api/observability/capacity/policies/${encodeURIComponent(meterKeyValue)}`,
            "PUT",
            {
              target_utilization_pct: parseIntOr(capacityTarget && capacityTarget.value, 75),
              scale_out_threshold_pct: parseIntOr(capacityScaleOut && capacityScaleOut.value, 85),
              scale_in_threshold_pct: parseIntOr(capacityScaleIn && capacityScaleIn.value, 50),
              min_replicas: parseIntOr(capacityMinReplicas && capacityMinReplicas.value, 1),
              max_replicas: parseIntOr(capacityMaxReplicas && capacityMaxReplicas.value, 5),
              current_replicas: parseIntOr(capacityCurrentReplicas && capacityCurrentReplicas.value, 2),
              is_active: true,
              detail: { source: "ui-reliability" },
            },
          );
          if (forecastMeterKey) {
            forecastMeterKey.value = row.meter_key;
          }
          capacityBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `容量策略已保存: ${row.meter_key}。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
