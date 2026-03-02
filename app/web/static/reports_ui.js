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
    return String((err && err.message) || err || "请求失败，请稍后重试。");
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
      throw new Error(body.detail || "请求失败，请稍后重试。");
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
        showResult("warn", "当前账号缺少 inspection:read 权限。");
        return;
      }
      await withBusyButton(rawFilterBtn, "加载中...", async () => {
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
            ? "暂无原始记录。"
            : rows.map((item) => `${item.id} ${item.data_type} ${item.access_tier} ${item.storage_region || "-"}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条原始记录。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (rawStorageBtn && rawStorageId && rawStorageTier) {
    rawStorageBtn.addEventListener("click", async () => {
      if (!canInspectionWrite) {
        showResult("warn", "当前账号缺少 inspection:write 权限。");
        return;
      }
      const rawId = (rawStorageId.value || "").trim();
      if (!rawId) {
        showResult("warn", "请先选择原始记录。");
        return;
      }
      await withBusyButton(rawStorageBtn, "提交中...", async () => {
        try {
          const payload = {
            access_tier: rawStorageTier.value,
          };
          const storageRegion = (rawStorageRegion && rawStorageRegion.value ? rawStorageRegion.value : "").trim();
          if (storageRegion) {
            payload.storage_region = storageRegion;
          }
          const row = await request(`/api/outcomes/raw/${rawId}/storage`, "PATCH", payload);
          showResult("success", `已调整原始记录存储层级：${row.id} -> ${row.access_tier}`);
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
        showResult("warn", "当前账号缺少 inspection:read 权限。");
        return;
      }
      await withBusyButton(outcomeFilterBtn, "加载中...", async () => {
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
            ? "暂无成果记录。"
            : rows.map((item) => `${item.id} ${item.source_type} ${item.outcome_type} ${item.status}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条成果记录。`);
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
        showResult("warn", "当前账号缺少 inspection:write 权限。");
        return;
      }
      const sourceId = (outcomeCreateSourceId.value || "").trim();
      if (!sourceId) {
        showResult("warn", "请填写来源对象标识。");
        return;
      }
      await withBusyButton(outcomeCreateBtn, "创建中...", async () => {
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
          showResult("success", `已创建成果记录：${row.id}`);
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
        showResult("warn", "当前账号缺少 inspection:write 权限。");
        return;
      }
      const outcomeId = (outcomeStatusId.value || "").trim();
      if (!outcomeId) {
        showResult("warn", "请先选择成果记录。");
        return;
      }
      await withBusyButton(outcomeStatusBtn, "提交中...", async () => {
        try {
          const row = await request(`/api/outcomes/records/${outcomeId}/status`, "PATCH", {
            status: outcomeStatusTarget.value,
            note: (outcomeStatusNote && outcomeStatusNote.value ? outcomeStatusNote.value : "").trim() || null,
          });
          showResult("success", `已更新成果状态：${row.id} -> ${row.status}`);
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
        showResult("warn", "当前账号缺少 inspection:read 权限。");
        return;
      }
      const outcomeId = (outcomeVersionsId.value || "").trim();
      if (!outcomeId) {
        showResult("warn", "请先选择成果记录。");
        return;
      }
      await withBusyButton(outcomeVersionsBtn, "加载中...", async () => {
        try {
          const rows = await request(`/api/outcomes/records/${outcomeId}/versions`, "GET");
          outcomeVersionsBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无版本记录。"
            : rows.map((item) => `v${item.version_no} ${item.change_type} ${item.status} ${item.created_at}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条版本记录。`);
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
        showResult("warn", "当前账号缺少 reporting.write 权限。");
        return;
      }
      const name = (reportTemplateName.value || "").trim();
      if (!name) {
        showResult("warn", "请填写模板名称。");
        return;
      }
      await withBusyButton(reportTemplateCreateBtn, "创建中...", async () => {
        try {
          const row = await request("/api/reporting/outcome-report-templates", "POST", {
            name,
            format_default: reportTemplateFormat.value,
            title_template: (reportTemplateTitle.value || "").trim() || "Outcome Report",
            body_template: (reportTemplateBody.value || "").trim(),
            is_active: true,
          });
          showResult("success", `已创建报告模板：${row.id}`);
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
        showResult("warn", "当前账号缺少 reporting.write 权限。");
        return;
      }
      const templateId = (reportExportTemplateId.value || "").trim();
      if (!templateId) {
        showResult("warn", "请先选择报告模板。");
        return;
      }
      await withBusyButton(reportExportCreateBtn, "创建中...", async () => {
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
            `导出任务: ${row.id}`,
            `当前状态: ${row.status}`,
            `导出格式: ${row.report_format}`,
            `文件路径: ${row.file_path || "-"}`,
          ].join("\n");
          showResult("success", `已创建导出任务：${row.id}`);
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
        showResult("warn", "当前账号缺少 reporting.read 权限。");
        return;
      }
      await withBusyButton(reportExportsLoadBtn, "加载中...", async () => {
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
            ? "暂无导出任务。"
            : rows.map((item) => `${item.id} ${item.status} ${item.report_format} ${item.file_path || "-"}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条导出任务。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (reportExportGetBtn && reportExportId && reportExportDetailBox) {
    reportExportGetBtn.addEventListener("click", async () => {
      if (!canReportingRead) {
        showResult("warn", "当前账号缺少 reporting.read 权限。");
        return;
      }
      const exportId = (reportExportId.value || "").trim();
      if (!exportId) {
        showResult("warn", "请填写导出任务标识。");
        return;
      }
      await withBusyButton(reportExportGetBtn, "加载中...", async () => {
        try {
          const row = await request(`/api/reporting/outcome-report-exports/${exportId}`, "GET");
          reportExportDetailBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `已加载导出任务详情：${row.id}`);
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
        showResult("warn", "当前账号缺少 reporting.write 权限。");
        return;
      }
      await withBusyButton(reportRetentionBtn, "执行中...", async () => {
        try {
          const body = await request("/api/reporting/outcome-report-exports:retention", "POST", {
            retention_days: parseIntOr(reportRetentionDays && reportRetentionDays.value, 30),
            dry_run: parseBool(reportRetentionDry && reportRetentionDry.value),
          });
          reportRetentionBox.textContent = JSON.stringify(body, null, 2);
          showResult("success", "保留期治理已执行完成。");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
