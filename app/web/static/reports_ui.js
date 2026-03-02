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

  function statusLabel(value) {
    const mapping = {
      NEW: "已发现",
      IN_REVIEW: "整改中",
      VERIFIED: "待归档",
      ARCHIVED: "已闭环",
    };
    return mapping[String(value || "").trim()] || String(value || "");
  }

  function sourceLabel(value) {
    const mapping = {
      INSPECTION_OBSERVATION: "巡检发现",
      ALERT: "告警转入",
      MANUAL: "人工补录",
    };
    return mapping[String(value || "").trim()] || String(value || "");
  }

  function outcomeTypeLabel(value) {
    const mapping = {
      DEFECT: "缺陷",
      HIDDEN_RISK: "隐患",
      INCIDENT: "事件",
      OTHER: "其他",
    };
    return mapping[String(value || "").trim()] || String(value || "");
  }

  function reportStatusLabel(value) {
    const mapping = {
      RUNNING: "生成中",
      SUCCEEDED: "已完成",
      FAILED: "失败",
    };
    return mapping[String(value || "").trim()] || String(value || "");
  }

  function reportFormatLabel(value) {
    const mapping = {
      PDF: "PDF 文件",
      WORD: "Word 文档",
    };
    return mapping[String(value || "").trim()] || String(value || "");
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

  const outcomeReviewContext = document.getElementById("outcome-review-context");
  const leaderExportContext = document.getElementById("leader-export-context");

  function setOutcomeContext(item) {
    const outcomeId = String(item.id || "").trim();
    const outcomeTitle = String(item.title || "当前事项").trim() || "当前事项";
    const taskId = String(item.taskId || "").trim();

    if (outcomeStatusId) {
      outcomeStatusId.value = outcomeId;
    }
    if (outcomeVersionsId) {
      outcomeVersionsId.value = outcomeId;
    }
    if (outcomeCreateTaskId && taskId && !String(outcomeCreateTaskId.value || "").trim()) {
      outcomeCreateTaskId.value = taskId;
    }
    if (reportExportTaskId && taskId && !String(reportExportTaskId.value || "").trim()) {
      reportExportTaskId.value = taskId;
    }
    if (outcomeReviewContext) {
      outcomeReviewContext.textContent = `${outcomeTitle} 已进入当前复核区（成果标识：${outcomeId || "未填写"}）`;
    }
  }

  function setTemplateContext(item) {
    const templateId = String(item.id || "").trim();
    const templateName = String(item.name || "").trim() || "当前模板";
    if (reportExportTemplateId) {
      reportExportTemplateId.value = templateId;
    }
    if (leaderExportContext) {
      leaderExportContext.textContent = `已选中汇报模板：${templateName}（${templateId}）。可直接生成新的汇报任务。`;
    }
  }

  function setExportContext(item) {
    const exportId = String(item.id || "").trim();
    const taskId = String(item.taskId || "").trim();
    const topic = String(item.topic || "").trim() || "综合复盘";
    if (reportExportId) {
      reportExportId.value = exportId;
    }
    if (reportExportTaskId && taskId) {
      reportExportTaskId.value = taskId;
    }
    if (reportExportTopic && !String(reportExportTopic.value || "").trim()) {
      reportExportTopic.value = topic;
    }
    if (leaderExportContext) {
      leaderExportContext.textContent = `已选中汇报任务：${exportId}，专题方向为“${topic}”。可直接加载详情或复用任务条件。`;
    }
  }

  document.querySelectorAll("[data-select-outcome]").forEach((button) => {
    button.addEventListener("click", () => {
      setOutcomeContext({
        id: button.getAttribute("data-select-outcome") || "",
        taskId: button.getAttribute("data-select-task") || "",
        title: button.getAttribute("data-outcome-title") || "",
      });
      showResult("success", "已将事项带入复核工作台。");
    });
  });

  document.querySelectorAll("[data-select-template]").forEach((button) => {
    button.addEventListener("click", () => {
      setTemplateContext({
        id: button.getAttribute("data-select-template") || "",
        name: button.getAttribute("data-template-name") || "",
      });
      showResult("success", "已将模板带入汇报生成区。");
    });
  });

  document.querySelectorAll("[data-select-export]").forEach((button) => {
    button.addEventListener("click", () => {
      setExportContext({
        id: button.getAttribute("data-select-export") || "",
        taskId: button.getAttribute("data-export-task") || "",
        topic: button.getAttribute("data-export-topic") || "",
      });
      showResult("success", "已将汇报任务带入详情区。");
    });
  });

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
          const taskId = String(rawFilterTaskId && rawFilterTaskId.value ? rawFilterTaskId.value : "").trim();
          const missionId = String(rawFilterMissionId && rawFilterMissionId.value ? rawFilterMissionId.value : "").trim();
          const dataType = String(rawFilterType && rawFilterType.value ? rawFilterType.value : "").trim();
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
            : rows.map((item) => `${item.id} · ${item.data_type} · ${item.access_tier} · ${item.storage_region || "-"}`).join("\n");
          if (Array.isArray(rows) && rows.length && rawStorageId && !String(rawStorageId.value || "").trim()) {
            rawStorageId.value = String(rows[0].id || "");
          }
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
      const rawId = String(rawStorageId.value || "").trim();
      if (!rawId) {
        showResult("warn", "请先选择原始记录。");
        return;
      }
      await withBusyButton(rawStorageBtn, "提交中...", async () => {
        try {
          const payload = {
            access_tier: rawStorageTier.value,
          };
          const storageRegion = String(rawStorageRegion && rawStorageRegion.value ? rawStorageRegion.value : "").trim();
          if (storageRegion) {
            payload.storage_region = storageRegion;
          }
          const row = await request(`/api/outcomes/raw/${rawId}/storage`, "PATCH", payload);
          showResult("success", `已调整原始记录留存层级：${row.id} -> ${row.access_tier}`);
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
          const taskId = String(outcomeFilterTaskId && outcomeFilterTaskId.value ? outcomeFilterTaskId.value : "").trim();
          const missionId = String(outcomeFilterMissionId && outcomeFilterMissionId.value ? outcomeFilterMissionId.value : "").trim();
          const sourceType = String(outcomeFilterSource && outcomeFilterSource.value ? outcomeFilterSource.value : "").trim();
          const outcomeType = String(outcomeFilterType && outcomeFilterType.value ? outcomeFilterType.value : "").trim();
          const outcomeStatus = String(outcomeFilterStatus && outcomeFilterStatus.value ? outcomeFilterStatus.value : "").trim();
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
            : rows.map((item) => `${item.id} · ${sourceLabel(item.source_type)} · ${outcomeTypeLabel(item.outcome_type)} · ${statusLabel(item.status)}`).join("\n");
          if (Array.isArray(rows) && rows.length) {
            setOutcomeContext({
              id: rows[0].id,
              taskId: rows[0].task_id || "",
              title: `${outcomeTypeLabel(rows[0].outcome_type)}事项`,
            });
          }
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
      const sourceId = String(outcomeCreateSourceId.value || "").trim();
      if (!sourceId) {
        showResult("warn", "请填写来源对象标识。");
        return;
      }
      await withBusyButton(outcomeCreateBtn, "登记中...", async () => {
        try {
          const payload = {
            source_type: outcomeCreateSource.value,
            source_id: sourceId,
            outcome_type: outcomeCreateType.value,
            payload: parseJsonOrDefault(outcomeCreatePayload && outcomeCreatePayload.value, {}),
          };
          const taskId = String(outcomeCreateTaskId && outcomeCreateTaskId.value ? outcomeCreateTaskId.value : "").trim();
          const missionId = String(outcomeCreateMissionId && outcomeCreateMissionId.value ? outcomeCreateMissionId.value : "").trim();
          if (taskId) {
            payload.task_id = taskId;
          }
          if (missionId) {
            payload.mission_id = missionId;
          }
          const row = await request("/api/outcomes/records", "POST", payload);
          setOutcomeContext({
            id: row.id,
            taskId: row.task_id || taskId,
            title: `${outcomeTypeLabel(row.outcome_type)}事项`,
          });
          showResult("success", `已登记新成果：${row.id}`);
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
      const outcomeId = String(outcomeStatusId.value || "").trim();
      if (!outcomeId) {
        showResult("warn", "请先从看板中选择成果事项。");
        return;
      }
      await withBusyButton(outcomeStatusBtn, "提交中...", async () => {
        try {
          const row = await request(`/api/outcomes/records/${outcomeId}/status`, "PATCH", {
            status: outcomeStatusTarget.value,
            note: String(outcomeStatusNote && outcomeStatusNote.value ? outcomeStatusNote.value : "").trim() || null,
          });
          if (outcomeReviewContext) {
            outcomeReviewContext.textContent = `当前事项 ${row.id} 已推进到“${statusLabel(row.status)}”。`;
          }
          showResult("success", `已更新闭环状态：${row.id} -> ${statusLabel(row.status)}`);
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
      const outcomeId = String(outcomeVersionsId.value || "").trim();
      if (!outcomeId) {
        showResult("warn", "请先选择成果记录。");
        return;
      }
      await withBusyButton(outcomeVersionsBtn, "加载中...", async () => {
        try {
          const rows = await request(`/api/outcomes/records/${outcomeId}/versions`, "GET");
          outcomeVersionsBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无版本留痕。"
            : rows.map((item) => `v${item.version_no} · ${item.change_type} · ${statusLabel(item.status)} · ${item.created_at}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条版本留痕。`);
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
      const name = String(reportTemplateName.value || "").trim();
      if (!name) {
        showResult("warn", "请填写模板名称。");
        return;
      }
      await withBusyButton(reportTemplateCreateBtn, "创建中...", async () => {
        try {
          const row = await request("/api/reporting/outcome-report-templates", "POST", {
            name,
            format_default: reportTemplateFormat.value,
            title_template: String(reportTemplateTitle.value || "").trim() || "成果汇报",
            body_template: String(reportTemplateBody.value || "").trim(),
            is_active: true,
          });
          if (reportExportTemplateId) {
            const option = document.createElement("option");
            option.value = row.id;
            option.textContent = `${row.name} (${row.id})`;
            reportExportTemplateId.appendChild(option);
          }
          setTemplateContext({ id: row.id, name: row.name });
          showResult("success", `已创建汇报模板：${row.id}`);
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
      const templateId = String(reportExportTemplateId.value || "").trim();
      if (!templateId) {
        showResult("warn", "请先选择汇报模板。");
        return;
      }
      await withBusyButton(reportExportCreateBtn, "生成中...", async () => {
        try {
          const payload = {
            template_id: templateId,
          };
          const reportFormat = String(reportExportFormat && reportExportFormat.value ? reportExportFormat.value : "").trim();
          const taskId = String(reportExportTaskId && reportExportTaskId.value ? reportExportTaskId.value : "").trim();
          const topic = String(reportExportTopic && reportExportTopic.value ? reportExportTopic.value : "").trim();
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
            `汇报任务：${row.id}`,
            `当前状态：${reportStatusLabel(row.status)}`,
            `导出格式：${reportFormatLabel(row.report_format)}`,
            `文件路径：${row.file_path || "-"}`,
          ].join("\n");
          setExportContext({
            id: row.id,
            taskId: row.task_id || taskId,
            topic: row.topic || topic,
          });
          showResult("success", `已创建汇报任务：${row.id}`);
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
          const statusFilter = String(reportExportsStatus && reportExportsStatus.value ? reportExportsStatus.value : "").trim();
          const limit = parseIntOr(reportExportsLimit && reportExportsLimit.value, 20);
          if (statusFilter) {
            params.set("status_filter", statusFilter);
          }
          params.set("limit", String(limit));
          const rows = await request(`/api/reporting/outcome-report-exports?${params.toString()}`, "GET");
          reportExportDetailBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无汇报任务。"
            : rows.map((item) => `${item.id} · ${reportStatusLabel(item.status)} · ${reportFormatLabel(item.report_format)} · ${item.file_path || "-"}`).join("\n");
          if (Array.isArray(rows) && rows.length) {
            setExportContext({
              id: rows[0].id,
              taskId: rows[0].task_id || "",
              topic: rows[0].topic || "",
            });
          }
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条汇报任务。`);
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
      const exportId = String(reportExportId.value || "").trim();
      if (!exportId) {
        showResult("warn", "请先选择汇报任务。");
        return;
      }
      await withBusyButton(reportExportGetBtn, "加载中...", async () => {
        try {
          const row = await request(`/api/reporting/outcome-report-exports/${exportId}`, "GET");
          reportExportDetailBox.textContent = [
            `汇报任务：${row.id}`,
            `当前状态：${reportStatusLabel(row.status)}`,
            `导出格式：${reportFormatLabel(row.report_format)}`,
            `专题：${row.topic || "综合复盘"}`,
            `任务：${row.task_id || "-"}`,
            `文件路径：${row.file_path || "-"}`,
          ].join("\n");
          setExportContext({
            id: row.id,
            taskId: row.task_id || "",
            topic: row.topic || "",
          });
          showResult("success", `已加载汇报任务详情：${row.id}`);
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
          showResult("success", "保留治理已执行完成。");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
