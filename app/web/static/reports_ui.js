(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";

  const canReportingRead = Boolean(window.__CAN_REPORTING_READ);
  const canReportingWrite = Boolean(window.__CAN_REPORTING_WRITE);
  const canInspectionRead = Boolean(window.__CAN_INSPECTION_READ);
  const canInspectionWrite = Boolean(window.__CAN_INSPECTION_WRITE);

  const resultNode = document.getElementById("reports-result");
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

  function parseBool(value) {
    return String(value).toLowerCase() === "true";
  }

  function parseIntOr(value, fallback) {
    const parsed = Number.parseInt(String(value || ""), 10);
    if (!Number.isFinite(parsed)) {
      return fallback;
    }
    return parsed;
  }

  function parseJsonOrDefault(raw, fallback) {
    const text = String(raw || "").trim();
    if (!text) {
      return fallback;
    }
    return JSON.parse(text);
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
      throw new Error(body.detail || "request failed");
    }
    return body;
  }

  const rawFilterTaskId = document.getElementById("raw-filter-task-id");
  const rawFilterMissionId = document.getElementById("raw-filter-mission-id");
  const rawFilterType = document.getElementById("raw-filter-type");
  const rawFilterBtn = document.getElementById("raw-filter-btn");
  const rawStorageId = document.getElementById("raw-storage-id");
  const rawStorageTier = document.getElementById("raw-storage-tier");
  const rawStorageRegion = document.getElementById("raw-storage-region");
  const rawStorageBtn = document.getElementById("raw-storage-btn");
  const rawBox = document.getElementById("raw-box");

  if (rawFilterBtn && rawBox) {
    rawFilterBtn.addEventListener("click", async () => {
      if (!canInspectionRead) {
        showResult("warn", "inspection:read is required.");
        return;
      }
      await withBusyButton(rawFilterBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const taskId = (rawFilterTaskId && rawFilterTaskId.value ? rawFilterTaskId.value : "").trim();
          const missionId = (rawFilterMissionId && rawFilterMissionId.value ? rawFilterMissionId.value : "").trim();
          const dataType = (rawFilterType && rawFilterType.value ? rawFilterType.value : "").trim();
          if (taskId) {
            params.set("task_id", taskId);
          }
          if (missionId) {
            params.set("mission_id", missionId);
          }
          if (dataType) {
            params.set("data_type", dataType);
          }
          const query = params.toString();
          const rows = await request(`/api/outcomes/raw${query ? `?${query}` : ""}`, "GET");
          rawBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No raw data."
            : rows.map((item) => `${item.id} ${item.data_type} ${item.access_tier} ${item.storage_region || "-"}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} raw records.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (rawStorageBtn && rawStorageId && rawStorageTier) {
    rawStorageBtn.addEventListener("click", async () => {
      if (!canInspectionWrite) {
        showResult("warn", "inspection:write is required.");
        return;
      }
      const rawId = (rawStorageId.value || "").trim();
      if (!rawId) {
        showResult("warn", "Raw ID is required.");
        return;
      }
      await withBusyButton(rawStorageBtn, "Submitting...", async () => {
        try {
          const payload = {
            access_tier: rawStorageTier.value,
          };
          const storageRegion = (rawStorageRegion && rawStorageRegion.value ? rawStorageRegion.value : "").trim();
          if (storageRegion) {
            payload.storage_region = storageRegion;
          }
          const row = await request(`/api/outcomes/raw/${rawId}/storage`, "PATCH", payload);
          showResult("success", `Raw storage transitioned: ${row.id} -> ${row.access_tier}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const outcomeFilterTaskId = document.getElementById("outcome-filter-task-id");
  const outcomeFilterMissionId = document.getElementById("outcome-filter-mission-id");
  const outcomeFilterSource = document.getElementById("outcome-filter-source");
  const outcomeFilterType = document.getElementById("outcome-filter-type");
  const outcomeFilterStatus = document.getElementById("outcome-filter-status");
  const outcomeFilterBtn = document.getElementById("outcome-filter-btn");
  const outcomeBox = document.getElementById("outcome-box");

  if (outcomeFilterBtn && outcomeBox) {
    outcomeFilterBtn.addEventListener("click", async () => {
      if (!canInspectionRead) {
        showResult("warn", "inspection:read is required.");
        return;
      }
      await withBusyButton(outcomeFilterBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const taskId = (outcomeFilterTaskId && outcomeFilterTaskId.value ? outcomeFilterTaskId.value : "").trim();
          const missionId = (outcomeFilterMissionId && outcomeFilterMissionId.value ? outcomeFilterMissionId.value : "").trim();
          const sourceType = (outcomeFilterSource && outcomeFilterSource.value ? outcomeFilterSource.value : "").trim();
          const outcomeType = (outcomeFilterType && outcomeFilterType.value ? outcomeFilterType.value : "").trim();
          const outcomeStatus = (outcomeFilterStatus && outcomeFilterStatus.value ? outcomeFilterStatus.value : "").trim();
          if (taskId) {
            params.set("task_id", taskId);
          }
          if (missionId) {
            params.set("mission_id", missionId);
          }
          if (sourceType) {
            params.set("source_type", sourceType);
          }
          if (outcomeType) {
            params.set("outcome_type", outcomeType);
          }
          if (outcomeStatus) {
            params.set("outcome_status", outcomeStatus);
          }
          const query = params.toString();
          const rows = await request(`/api/outcomes/records${query ? `?${query}` : ""}`, "GET");
          outcomeBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No outcomes."
            : rows.map((item) => `${item.id} ${item.source_type} ${item.outcome_type} ${item.status}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} outcomes.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const outcomeCreateSource = document.getElementById("outcome-create-source");
  const outcomeCreateSourceId = document.getElementById("outcome-create-source-id");
  const outcomeCreateType = document.getElementById("outcome-create-type");
  const outcomeCreateTaskId = document.getElementById("outcome-create-task-id");
  const outcomeCreateMissionId = document.getElementById("outcome-create-mission-id");
  const outcomeCreatePayload = document.getElementById("outcome-create-payload");
  const outcomeCreateBtn = document.getElementById("outcome-create-btn");

  if (outcomeCreateBtn && outcomeCreateSource && outcomeCreateSourceId && outcomeCreateType) {
    outcomeCreateBtn.addEventListener("click", async () => {
      if (!canInspectionWrite) {
        showResult("warn", "inspection:write is required.");
        return;
      }
      const sourceId = (outcomeCreateSourceId.value || "").trim();
      if (!sourceId) {
        showResult("warn", "Source ID is required.");
        return;
      }
      await withBusyButton(outcomeCreateBtn, "Creating...", async () => {
        try {
          const payload = {
            source_type: outcomeCreateSource.value,
            source_id: sourceId,
            outcome_type: outcomeCreateType.value,
            payload: parseJsonOrDefault(outcomeCreatePayload && outcomeCreatePayload.value, {}),
          };
          const taskId = (outcomeCreateTaskId && outcomeCreateTaskId.value ? outcomeCreateTaskId.value : "").trim();
          const missionId = (outcomeCreateMissionId && outcomeCreateMissionId.value ? outcomeCreateMissionId.value : "").trim();
          if (taskId) {
            payload.task_id = taskId;
          }
          if (missionId) {
            payload.mission_id = missionId;
          }
          const row = await request("/api/outcomes/records", "POST", payload);
          showResult("success", `Outcome created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const outcomeStatusId = document.getElementById("outcome-status-id");
  const outcomeStatusTarget = document.getElementById("outcome-status-target");
  const outcomeStatusNote = document.getElementById("outcome-status-note");
  const outcomeStatusBtn = document.getElementById("outcome-status-btn");

  if (outcomeStatusBtn && outcomeStatusId && outcomeStatusTarget) {
    outcomeStatusBtn.addEventListener("click", async () => {
      if (!canInspectionWrite) {
        showResult("warn", "inspection:write is required.");
        return;
      }
      const outcomeId = (outcomeStatusId.value || "").trim();
      if (!outcomeId) {
        showResult("warn", "Outcome ID is required.");
        return;
      }
      await withBusyButton(outcomeStatusBtn, "Submitting...", async () => {
        try {
          const row = await request(`/api/outcomes/records/${outcomeId}/status`, "PATCH", {
            status: outcomeStatusTarget.value,
            note: (outcomeStatusNote && outcomeStatusNote.value ? outcomeStatusNote.value : "").trim() || null,
          });
          showResult("success", `Outcome status updated: ${row.id} -> ${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const outcomeVersionsId = document.getElementById("outcome-versions-id");
  const outcomeVersionsBtn = document.getElementById("outcome-versions-btn");
  const outcomeVersionsBox = document.getElementById("outcome-versions-box");

  if (outcomeVersionsBtn && outcomeVersionsId && outcomeVersionsBox) {
    outcomeVersionsBtn.addEventListener("click", async () => {
      if (!canInspectionRead) {
        showResult("warn", "inspection:read is required.");
        return;
      }
      const outcomeId = (outcomeVersionsId.value || "").trim();
      if (!outcomeId) {
        showResult("warn", "Outcome ID is required.");
        return;
      }
      await withBusyButton(outcomeVersionsBtn, "Loading...", async () => {
        try {
          const rows = await request(`/api/outcomes/records/${outcomeId}/versions`, "GET");
          outcomeVersionsBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No versions."
            : rows.map((item) => `v${item.version_no} ${item.change_type} ${item.status} ${item.created_at}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} versions.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const reportTemplateName = document.getElementById("report-template-name");
  const reportTemplateFormat = document.getElementById("report-template-format");
  const reportTemplateTitle = document.getElementById("report-template-title");
  const reportTemplateBody = document.getElementById("report-template-body");
  const reportTemplateCreateBtn = document.getElementById("report-template-create-btn");

  if (reportTemplateCreateBtn && reportTemplateName && reportTemplateFormat && reportTemplateTitle && reportTemplateBody) {
    reportTemplateCreateBtn.addEventListener("click", async () => {
      if (!canReportingWrite) {
        showResult("warn", "reporting.write is required.");
        return;
      }
      const name = (reportTemplateName.value || "").trim();
      if (!name) {
        showResult("warn", "Template name is required.");
        return;
      }
      await withBusyButton(reportTemplateCreateBtn, "Creating...", async () => {
        try {
          const row = await request("/api/reporting/outcome-report-templates", "POST", {
            name,
            format_default: reportTemplateFormat.value,
            title_template: (reportTemplateTitle.value || "").trim() || "Outcome Report",
            body_template: (reportTemplateBody.value || "").trim(),
            is_active: true,
          });
          showResult("success", `Report template created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const reportExportTemplateId = document.getElementById("report-export-template-id");
  const reportExportFormat = document.getElementById("report-export-format");
  const reportExportTaskId = document.getElementById("report-export-task-id");
  const reportExportTopic = document.getElementById("report-export-topic");
  const reportExportCreateBtn = document.getElementById("report-export-create-btn");
  const reportExportBox = document.getElementById("report-export-box");

  if (reportExportCreateBtn && reportExportTemplateId && reportExportBox) {
    reportExportCreateBtn.addEventListener("click", async () => {
      if (!canReportingWrite) {
        showResult("warn", "reporting.write is required.");
        return;
      }
      const templateId = (reportExportTemplateId.value || "").trim();
      if (!templateId) {
        showResult("warn", "Template ID is required.");
        return;
      }
      await withBusyButton(reportExportCreateBtn, "Creating...", async () => {
        try {
          const payload = {
            template_id: templateId,
          };
          const reportFormat = (reportExportFormat && reportExportFormat.value ? reportExportFormat.value : "").trim();
          const taskId = (reportExportTaskId && reportExportTaskId.value ? reportExportTaskId.value : "").trim();
          const topic = (reportExportTopic && reportExportTopic.value ? reportExportTopic.value : "").trim();
          if (reportFormat) {
            payload.report_format = reportFormat;
          }
          if (taskId) {
            payload.task_id = taskId;
          }
          if (topic) {
            payload.topic = topic;
          }
          const row = await request("/api/reporting/outcome-report-exports", "POST", payload);
          reportExportBox.textContent = [
            `export_id: ${row.id}`,
            `status: ${row.status}`,
            `format: ${row.report_format}`,
            `file_path: ${row.file_path || "-"}`,
          ].join("\n");
          showResult("success", `Export task created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const reportExportsStatus = document.getElementById("report-exports-status");
  const reportExportsLimit = document.getElementById("report-exports-limit");
  const reportExportsLoadBtn = document.getElementById("report-exports-load-btn");
  const reportExportId = document.getElementById("report-export-id");
  const reportExportGetBtn = document.getElementById("report-export-get-btn");
  const reportExportDetailBox = document.getElementById("report-export-detail-box");

  if (reportExportsLoadBtn && reportExportDetailBox) {
    reportExportsLoadBtn.addEventListener("click", async () => {
      if (!canReportingRead) {
        showResult("warn", "reporting.read is required.");
        return;
      }
      await withBusyButton(reportExportsLoadBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const statusFilter = (reportExportsStatus && reportExportsStatus.value ? reportExportsStatus.value : "").trim();
          const limit = parseIntOr(reportExportsLimit && reportExportsLimit.value, 20);
          if (statusFilter) {
            params.set("status_filter", statusFilter);
          }
          params.set("limit", String(limit));
          const rows = await request(`/api/reporting/outcome-report-exports?${params.toString()}`, "GET");
          reportExportDetailBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No export rows."
            : rows.map((item) => `${item.id} ${item.status} ${item.report_format} ${item.file_path || "-"}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} export rows.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (reportExportGetBtn && reportExportId && reportExportDetailBox) {
    reportExportGetBtn.addEventListener("click", async () => {
      if (!canReportingRead) {
        showResult("warn", "reporting.read is required.");
        return;
      }
      const exportId = (reportExportId.value || "").trim();
      if (!exportId) {
        showResult("warn", "Export ID is required.");
        return;
      }
      await withBusyButton(reportExportGetBtn, "Loading...", async () => {
        try {
          const row = await request(`/api/reporting/outcome-report-exports/${exportId}`, "GET");
          reportExportDetailBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `Loaded export detail: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const reportRetentionDays = document.getElementById("report-retention-days");
  const reportRetentionDry = document.getElementById("report-retention-dry");
  const reportRetentionBtn = document.getElementById("report-retention-btn");
  const reportRetentionBox = document.getElementById("report-retention-box");

  if (reportRetentionBtn && reportRetentionBox) {
    reportRetentionBtn.addEventListener("click", async () => {
      if (!canReportingWrite) {
        showResult("warn", "reporting.write is required.");
        return;
      }
      await withBusyButton(reportRetentionBtn, "Running...", async () => {
        try {
          const body = await request("/api/reporting/outcome-report-exports:retention", "POST", {
            retention_days: parseIntOr(reportRetentionDays && reportRetentionDays.value, 30),
            dry_run: parseBool(reportRetentionDry && reportRetentionDry.value),
          });
          reportRetentionBox.textContent = JSON.stringify(body, null, 2);
          showResult("success", "Retention run completed.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
