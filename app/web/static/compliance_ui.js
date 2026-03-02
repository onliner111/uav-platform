(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canApprovalWrite = Boolean(window.__CAN_APPROVAL_WRITE);
  const canMissionWrite = Boolean(window.__CAN_MISSION_WRITE);
  const canMissionRead = Boolean(window.__CAN_MISSION_READ);

  const resultNode = document.getElementById("compliance-result");
  const approvalBox = document.getElementById("approval-box");
  const flowBox = document.getElementById("flow-box");
  const zoneBox = document.getElementById("zone-box");
  const preflightBox = document.getElementById("preflight-box");
  const decisionBox = document.getElementById("decision-box");
  const approvalSelectionBanner = document.getElementById("approval-selection-banner");
  const flowSelectionBanner = document.getElementById("flow-selection-banner");
  const zoneSelectionBanner = document.getElementById("zone-selection-banner");
  const preflightSelectionBanner = document.getElementById("preflight-selection-banner");
  const approvalFlowGuidance = document.getElementById("approval-flow-guidance");
  const approvalFlowStageEntity = document.getElementById("approval-flow-state-entity");
  const approvalFlowStageApproval = document.getElementById("approval-flow-state-approval");
  const approvalFlowStageInstance = document.getElementById("approval-flow-state-instance");
  const approvalFlowStageClose = document.getElementById("approval-flow-state-close");
  const approvalFlowState = {
    entitySelected: false,
    approvalRecorded: false,
    flowStarted: false,
    flowStatus: "",
  };

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

  function parseJsonOrDefault(raw, fallback) {
    const text = String(raw || "").trim();
    if (!text) {
      return fallback;
    }
    return JSON.parse(text);
  }

  function parseBool(value) {
    return String(value).toLowerCase() === "true";
  }

  function parseFloatOrNull(value) {
    const text = String(value || "").trim();
    if (!text) {
      return null;
    }
    const parsed = Number.parseFloat(text);
    return Number.isFinite(parsed) ? parsed : null;
  }

  function setFlowStage(node, text, tone) {
    if (!node) {
      return;
    }
    node.textContent = text;
    node.className = `status-pill ${tone || "muted"}`;
  }

  function refreshApprovalFlowVisualization() {
    const flowStatus = String(approvalFlowState.flowStatus || "").toUpperCase();
    const flowDone = flowStatus.includes("APPROVED") || flowStatus.includes("DONE") || flowStatus.includes("COMPLETE");
    setFlowStage(
      approvalFlowStageEntity,
      approvalFlowState.entitySelected ? "已选中" : "待选择",
      approvalFlowState.entitySelected ? "success" : "muted",
    );
    setFlowStage(
      approvalFlowStageApproval,
      approvalFlowState.approvalRecorded ? "已登记" : "待处理",
      approvalFlowState.approvalRecorded ? "success" : (approvalFlowState.entitySelected ? "warn" : "muted"),
    );
    setFlowStage(
      approvalFlowStageInstance,
      approvalFlowState.flowStarted ? "已发起" : "待创建",
      approvalFlowState.flowStarted ? "success" : (approvalFlowState.approvalRecorded ? "warn" : "muted"),
    );
    setFlowStage(
      approvalFlowStageClose,
      flowDone ? "已完成" : (approvalFlowState.flowStarted ? "推进中" : "待完成"),
      flowDone ? "success" : (approvalFlowState.flowStarted ? "warn" : "muted"),
    );
    if (!approvalFlowGuidance) {
      return;
    }
    if (!approvalFlowState.entitySelected) {
      approvalFlowGuidance.innerHTML = "<strong>流程提示：</strong>请先从审批记录中选中业务对象，再继续后续动作。";
      return;
    }
    if (!approvalFlowState.approvalRecorded) {
      approvalFlowGuidance.innerHTML = "<strong>流程提示：</strong>业务对象已选中，建议先登记审批结果，再发起流程实例。";
      return;
    }
    if (!approvalFlowState.flowStarted) {
      approvalFlowGuidance.innerHTML = "<strong>流程提示：</strong>审批结果已记录，下一步可直接发起审批流程。";
      return;
    }
    if (flowDone) {
      approvalFlowGuidance.innerHTML = "<strong>流程提示：</strong>当前流程已达到完成状态，可导出审计记录或切换到下一个对象。";
      return;
    }
    approvalFlowGuidance.innerHTML = "<strong>流程提示：</strong>流程正在推进中，可继续提交动作或查看流程详情。";
  }

  function setSelectedEntity(entityType, entityId) {
    if (approvalCreateEntityType) {
      approvalCreateEntityType.value = entityType;
    }
    if (approvalCreateEntityId) {
      approvalCreateEntityId.value = entityId;
    }
    if (flowInstanceEntityType) {
      flowInstanceEntityType.value = entityType;
    }
    if (flowInstanceEntityId) {
      flowInstanceEntityId.value = entityId;
    }
    if (entityType === "MISSION" && preflightMissionId) {
      preflightMissionId.value = entityId;
    }
    if (approvalSelectionBanner) {
      approvalSelectionBanner.innerHTML = `<strong>当前业务对象：</strong>${entityType || "-"} / <code>${entityId || "-"}</code>`;
    }
    approvalFlowState.entitySelected = Boolean(entityType && entityId);
    approvalFlowState.approvalRecorded = false;
    approvalFlowState.flowStarted = false;
    approvalFlowState.flowStatus = "";
    refreshApprovalFlowVisualization();
  }

  function setSelectedFlowInstance(instanceId, status) {
    if (flowActionInstanceId) {
      flowActionInstanceId.value = instanceId;
    }
    if (flowSelectionBanner) {
      flowSelectionBanner.innerHTML = `<strong>当前流程实例：</strong><code>${instanceId || "-"}</code>${status ? `，状态：${status}` : ""}`;
    }
    approvalFlowState.flowStarted = Boolean(instanceId);
    approvalFlowState.flowStatus = status || "";
    refreshApprovalFlowVisualization();
  }

  function setSelectedZone(zoneId, zoneName, zoneType, zoneLayer) {
    if (zoneSelectionBanner) {
      zoneSelectionBanner.innerHTML =
        `<strong>当前空域规则：</strong>${zoneName || "未命名规则"}（<code>${zoneId || "-"}</code>）` +
        `${zoneType ? `，类型：${zoneType}` : ""}` +
        `${zoneLayer ? `，层级：${zoneLayer}` : ""}`;
    }
  }

  function setSelectedPreflightTemplate(templateId, templateName, templateVersion) {
    if (preflightTemplateId) {
      preflightTemplateId.value = templateId;
    }
    if (preflightSelectionBanner) {
      preflightSelectionBanner.innerHTML =
        `<strong>当前模板：</strong>${templateName || "未命名模板"}（<code>${templateId || "-"}</code>）` +
        `${templateVersion ? `，版本：${templateVersion}` : ""}`;
    }
  }

  const approvalFilterEntityType = document.getElementById("approval-filter-entity-type");
  const approvalFilterEntityId = document.getElementById("approval-filter-entity-id");
  const approvalFilterBtn = document.getElementById("approval-filter-btn");
  const approvalExportBtn = document.getElementById("approval-export-btn");
  const approvalCreateEntityType = document.getElementById("approval-create-entity-type");
  const approvalCreateEntityId = document.getElementById("approval-create-entity-id");
  const approvalCreateStatus = document.getElementById("approval-create-status");
  const approvalCreateBtn = document.getElementById("approval-create-btn");
  const approvalBatchEntityType = document.getElementById("approval-batch-entity-type");
  const approvalBatchStatus = document.getElementById("approval-batch-status");
  const approvalBatchEntityIds = document.getElementById("approval-batch-entity-ids");
  const approvalBatchCreateBtn = document.getElementById("approval-batch-create-btn");

  function selectedApprovalFilters() {
    const params = new URLSearchParams();
    const entityType = (approvalFilterEntityType && approvalFilterEntityType.value ? approvalFilterEntityType.value : "").trim();
    const entityId = (approvalFilterEntityId && approvalFilterEntityId.value ? approvalFilterEntityId.value : "").trim();
    if (entityType) {
      params.set("entity_type", entityType);
    }
    if (entityId) {
      params.set("entity_id", entityId);
    }
    return params;
  }

  if (approvalFilterBtn && approvalBox) {
    approvalFilterBtn.addEventListener("click", async () => {
      await withBusyButton(approvalFilterBtn, "加载中...", async () => {
        try {
          const params = selectedApprovalFilters();
          const query = params.toString();
          const rows = await get(`/api/approvals${query ? `?${query}` : ""}`);
          approvalBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无审批记录。"
            : rows.map((item) => `${item.id} ${item.entity_type} ${item.entity_id} ${item.status}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条审批记录。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approvalExportBtn) {
    approvalExportBtn.addEventListener("click", async () => {
      await withBusyButton(approvalExportBtn, "导出中...", async () => {
        try {
          const body = await get("/api/approvals/audit-export");
          if (approvalBox) {
            approvalBox.textContent = `audit_export_path: ${body.file_path}`;
          }
          showResult("success", `已导出审批审计：${body.file_path}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approvalCreateBtn && approvalCreateEntityType && approvalCreateEntityId && approvalCreateStatus) {
    approvalCreateBtn.addEventListener("click", async () => {
      if (!canApprovalWrite) {
        showResult("warn", "当前为只读模式，审批写入已禁用。");
        return;
      }
      const entityType = (approvalCreateEntityType.value || "").trim();
      const entityId = (approvalCreateEntityId.value || "").trim();
      const status = (approvalCreateStatus.value || "").trim();
      if (!entityType || !entityId || !status) {
        showResult("warn", "请先确认业务对象类型、业务对象 ID 和审批状态。");
        return;
      }
      await withBusyButton(approvalCreateBtn, "提交中...", async () => {
        try {
          const row = await post("/api/approvals", {
            entity_type: entityType,
            entity_id: entityId,
            status,
          });
          setSelectedEntity(entityType, entityId);
          approvalFlowState.approvalRecorded = true;
          refreshApprovalFlowVisualization();
          showResult("success", `已登记审批结果：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approvalBatchCreateBtn && approvalBatchEntityType && approvalBatchStatus && approvalBatchEntityIds) {
    approvalBatchCreateBtn.addEventListener("click", async () => {
      if (!canApprovalWrite) {
        showResult("warn", "当前为只读模式，审批写入已禁用。");
        return;
      }
      const entityType = (approvalBatchEntityType.value || "").trim();
      const status = (approvalBatchStatus.value || "").trim();
      const ids = (approvalBatchEntityIds.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!entityType || !status || !ids.length) {
        showResult("warn", "请填写业务对象类型、审批状态，并至少提供一个业务对象 ID。");
        return;
      }
      await withBusyButton(approvalBatchCreateBtn, "提交中...", async () => {
        let success = 0;
        const failures = [];
        for (const entityId of ids) {
          try {
            await post("/api/approvals", { entity_type: entityType, entity_id: entityId, status });
            success += 1;
          } catch (err) {
            failures.push(`${entityId}: ${toMessage(err)}`);
          }
        }
        if (!failures.length) {
          showResult("success", `批量审批已完成：${success}/${ids.length}`);
          return;
        }
        showResult("warn", `批量审批部分完成：${success}/${ids.length}。${failures.join(" | ")}`);
      });
    });
  }

  const flowTemplateName = document.getElementById("flow-template-name");
  const flowTemplateEntityType = document.getElementById("flow-template-entity-type");
  const flowTemplateSteps = document.getElementById("flow-template-steps");
  const flowTemplateCreateBtn = document.getElementById("flow-template-create-btn");

  const flowInstanceTemplateId = document.getElementById("flow-instance-template-id");
  const flowInstanceEntityType = document.getElementById("flow-instance-entity-type");
  const flowInstanceEntityId = document.getElementById("flow-instance-entity-id");
  const flowInstanceCreateBtn = document.getElementById("flow-instance-create-btn");

  const flowActionInstanceId = document.getElementById("flow-action-instance-id");
  const flowActionType = document.getElementById("flow-action-type");
  const flowActionNote = document.getElementById("flow-action-note");
  const flowActionBtn = document.getElementById("flow-action-btn");
  const flowLoadBtn = document.getElementById("flow-load-btn");
  const flowBatchInstanceIds = document.getElementById("flow-batch-instance-ids");
  const flowBatchAction = document.getElementById("flow-batch-action");
  const flowBatchActionBtn = document.getElementById("flow-batch-action-btn");

  if (flowTemplateCreateBtn && flowTemplateName && flowTemplateEntityType && flowTemplateSteps) {
    flowTemplateCreateBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，流程配置写入已禁用。");
        return;
      }
      const name = (flowTemplateName.value || "").trim();
      const entityType = (flowTemplateEntityType.value || "").trim();
      if (!name || !entityType) {
        showResult("warn", "请填写模板名称和业务对象类型。");
        return;
      }
      await withBusyButton(flowTemplateCreateBtn, "创建中...", async () => {
        try {
          const steps = parseJsonOrDefault(flowTemplateSteps.value, []);
          if (!Array.isArray(steps) || !steps.length) {
            showResult("warn", "流程步骤 JSON 不能为空，且必须是数组。");
            return;
          }
          const row = await post("/api/compliance/approval-flows/templates", {
            name,
            entity_type: entityType,
            steps,
            is_active: true,
          });
          if (flowBox) {
            flowBox.textContent = `flow_template_id: ${row.id}`;
          }
          if (flowInstanceTemplateId) {
            flowInstanceTemplateId.value = row.id;
          }
          showResult("success", `已创建流程模板：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowInstanceCreateBtn && flowInstanceTemplateId && flowInstanceEntityType && flowInstanceEntityId) {
    flowInstanceCreateBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，流程写入已禁用。");
        return;
      }
      const templateId = (flowInstanceTemplateId.value || "").trim();
      const entityType = (flowInstanceEntityType.value || "").trim();
      const entityId = (flowInstanceEntityId.value || "").trim();
      if (!templateId || !entityType || !entityId) {
        showResult("warn", "请先确认模板 ID、业务对象类型和业务对象 ID。");
        return;
      }
      await withBusyButton(flowInstanceCreateBtn, "创建中...", async () => {
        try {
          const row = await post("/api/compliance/approval-flows/instances", {
            template_id: templateId,
            entity_type: entityType,
            entity_id: entityId,
          });
          if (flowBox) {
            flowBox.textContent = `flow_instance_id: ${row.id}\nstatus: ${row.status}`;
          }
          setSelectedFlowInstance(row.id, row.status);
          approvalFlowState.approvalRecorded = true;
          refreshApprovalFlowVisualization();
          showResult("success", `已发起审批流程：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowActionBtn && flowActionInstanceId && flowActionType) {
    flowActionBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，流程写入已禁用。");
        return;
      }
      const instanceId = (flowActionInstanceId.value || "").trim();
      if (!instanceId) {
        showResult("warn", "请先选择流程实例。");
        return;
      }
      await withBusyButton(flowActionBtn, "提交中...", async () => {
        try {
          const row = await post(`/api/compliance/approval-flows/instances/${instanceId}/actions`, {
            action: flowActionType.value,
            note: (flowActionNote && flowActionNote.value ? flowActionNote.value : "").trim() || null,
          });
          if (flowBox) {
            flowBox.textContent = [
              `instance_id: ${row.id}`,
              `status: ${row.status}`,
              `current_step_index: ${row.current_step_index}`,
              `history_count: ${Array.isArray(row.action_history) ? row.action_history.length : 0}`,
            ].join("\n");
          }
          setSelectedFlowInstance(row.id, row.status);
          showResult("success", `已提交流程动作：${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowLoadBtn && flowActionInstanceId) {
    flowLoadBtn.addEventListener("click", async () => {
      const instanceId = (flowActionInstanceId.value || "").trim();
      if (!instanceId) {
        showResult("warn", "请先选择流程实例。");
        return;
      }
      await withBusyButton(flowLoadBtn, "加载中...", async () => {
        try {
          const row = await get(`/api/compliance/approval-flows/instances/${instanceId}`);
          if (flowBox) {
            flowBox.textContent = [
              `instance_id: ${row.id}`,
              `entity: ${row.entity_type}/${row.entity_id}`,
              `status: ${row.status}`,
              `current_step_index: ${row.current_step_index}`,
              `history_count: ${Array.isArray(row.action_history) ? row.action_history.length : 0}`,
            ].join("\n");
          }
          setSelectedFlowInstance(row.id, row.status);
          showResult("success", "已加载流程详情。");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowBatchActionBtn && flowBatchInstanceIds && flowBatchAction) {
    flowBatchActionBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，流程写入已禁用。");
        return;
      }
      const ids = (flowBatchInstanceIds.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!ids.length) {
        showResult("warn", "请至少提供一个流程实例 ID。");
        return;
      }
      await withBusyButton(flowBatchActionBtn, "提交中...", async () => {
        let success = 0;
        const failures = [];
        for (const id of ids) {
          try {
            await post(`/api/compliance/approval-flows/instances/${id}/actions`, {
              action: flowBatchAction.value,
            });
            success += 1;
          } catch (err) {
            failures.push(`${id}: ${toMessage(err)}`);
          }
        }
        if (!failures.length) {
          showResult("success", `批量流程处理已完成：${success}/${ids.length}`);
          return;
        }
        showResult("warn", `批量流程处理部分完成：${success}/${ids.length}。${failures.join(" | ")}`);
      });
    });
  }

  const zoneCreateName = document.getElementById("zone-create-name");
  const zoneCreateType = document.getElementById("zone-create-type");
  const zoneCreateLayer = document.getElementById("zone-create-layer");
  const zoneCreateEffect = document.getElementById("zone-create-effect");
  const zoneCreateOrgUnitId = document.getElementById("zone-create-org-unit-id");
  const zoneCreateAreaCode = document.getElementById("zone-create-area-code");
  const zoneCreateWkt = document.getElementById("zone-create-wkt");
  const zoneCreateMaxAlt = document.getElementById("zone-create-max-alt");
  const zoneCreateBtn = document.getElementById("zone-create-btn");

  const zoneFilterType = document.getElementById("zone-filter-type");
  const zoneFilterLayer = document.getElementById("zone-filter-layer");
  const zoneFilterOrgUnitId = document.getElementById("zone-filter-org-unit-id");
  const zoneFilterBtn = document.getElementById("zone-filter-btn");

  if (zoneCreateBtn && zoneCreateName && zoneCreateType && zoneCreateLayer && zoneCreateEffect && zoneCreateWkt) {
    zoneCreateBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，规则写入已禁用。");
        return;
      }
      const name = (zoneCreateName.value || "").trim();
      const geomWkt = (zoneCreateWkt.value || "").trim();
      if (!name || !geomWkt) {
        showResult("warn", "请填写规则名称和多边形 WKT。");
        return;
      }
      await withBusyButton(zoneCreateBtn, "创建中...", async () => {
        try {
          const payload = {
            name,
            zone_type: zoneCreateType.value,
            policy_layer: zoneCreateLayer.value,
            policy_effect: zoneCreateEffect.value,
            geom_wkt: geomWkt,
            is_active: true,
            detail: {},
          };
          const orgUnitId = (zoneCreateOrgUnitId && zoneCreateOrgUnitId.value ? zoneCreateOrgUnitId.value : "").trim();
          const areaCode = (zoneCreateAreaCode && zoneCreateAreaCode.value ? zoneCreateAreaCode.value : "").trim();
          const maxAlt = parseFloatOrNull(zoneCreateMaxAlt && zoneCreateMaxAlt.value);
          if (orgUnitId) {
            payload.org_unit_id = orgUnitId;
          }
          if (areaCode) {
            payload.area_code = areaCode;
          }
          if (maxAlt !== null) {
            payload.max_alt_m = maxAlt;
          }
          const row = await post("/api/compliance/zones", payload);
          setSelectedZone(row.id, row.name || name, row.zone_type || payload.zone_type, row.policy_layer || payload.policy_layer);
          showResult("success", `已创建空域规则：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (zoneFilterBtn && zoneBox) {
    zoneFilterBtn.addEventListener("click", async () => {
      await withBusyButton(zoneFilterBtn, "加载中...", async () => {
        try {
          const params = new URLSearchParams();
          const zoneType = (zoneFilterType && zoneFilterType.value ? zoneFilterType.value : "").trim();
          const layer = (zoneFilterLayer && zoneFilterLayer.value ? zoneFilterLayer.value : "").trim();
          const orgUnitId = (zoneFilterOrgUnitId && zoneFilterOrgUnitId.value ? zoneFilterOrgUnitId.value : "").trim();
          if (zoneType) {
            params.set("zone_type", zoneType);
          }
          if (layer) {
            params.set("policy_layer", layer);
          }
          if (orgUnitId) {
            params.set("org_unit_id", orgUnitId);
          }
          const query = params.toString();
          const rows = await get(`/api/compliance/zones${query ? `?${query}` : ""}`);
          zoneBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无空域规则。"
            : rows.map((item) => `${item.id} ${item.zone_type} ${item.policy_layer} ${item.policy_effect}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条空域规则。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const preflightTemplateName = document.getElementById("preflight-template-name");
  const preflightTemplateDescription = document.getElementById("preflight-template-description");
  const preflightTemplateVersion = document.getElementById("preflight-template-version");
  const preflightTemplateItems = document.getElementById("preflight-template-items");
  const preflightTemplateEvidence = document.getElementById("preflight-template-evidence");
  const preflightTemplateCreateBtn = document.getElementById("preflight-template-create-btn");

  const preflightMissionId = document.getElementById("preflight-mission-id");
  const preflightTemplateId = document.getElementById("preflight-template-id");
  const preflightRequiredItems = document.getElementById("preflight-required-items");
  const preflightInitBtn = document.getElementById("preflight-init-btn");
  const preflightLoadBtn = document.getElementById("preflight-load-btn");
  const preflightItemCode = document.getElementById("preflight-item-code");
  const preflightItemChecked = document.getElementById("preflight-item-checked");
  const preflightItemNote = document.getElementById("preflight-item-note");
  const preflightItemEvidence = document.getElementById("preflight-item-evidence");
  const preflightCheckBtn = document.getElementById("preflight-check-btn");

  if (preflightTemplateCreateBtn && preflightTemplateName && preflightTemplateItems && preflightTemplateEvidence) {
    preflightTemplateCreateBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，模板写入已禁用。");
        return;
      }
      const name = (preflightTemplateName.value || "").trim();
      if (!name) {
        showResult("warn", "请填写模板名称。");
        return;
      }
      await withBusyButton(preflightTemplateCreateBtn, "创建中...", async () => {
        try {
          const items = parseJsonOrDefault(preflightTemplateItems.value, []);
          if (!Array.isArray(items) || !items.length) {
            showResult("warn", "检查项 JSON 不能为空，且必须是数组。");
            return;
          }
          const evidenceRequirements = parseJsonOrDefault(preflightTemplateEvidence.value, {});
          const row = await post("/api/compliance/preflight/templates", {
            name,
            description: (preflightTemplateDescription && preflightTemplateDescription.value
              ? preflightTemplateDescription.value
              : "").trim() || null,
            items,
            template_version: (preflightTemplateVersion && preflightTemplateVersion.value
              ? preflightTemplateVersion.value
              : "").trim() || "v1",
            evidence_requirements: evidenceRequirements,
            require_approval_before_run: true,
            is_active: true,
          });
          setSelectedPreflightTemplate(row.id, row.name || name, row.template_version || "v1");
          showResult("success", `已创建起飞前检查模板：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  function currentMissionId() {
    return (preflightMissionId && preflightMissionId.value ? preflightMissionId.value : "").trim();
  }

  if (preflightInitBtn && preflightMissionId) {
    preflightInitBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，任务检查写入已禁用。");
        return;
      }
      const missionId = currentMissionId();
      if (!missionId) {
        showResult("warn", "请先填写任务 ID。");
        return;
      }
      await withBusyButton(preflightInitBtn, "初始化中...", async () => {
        try {
          const payload = {};
          const templateId = (preflightTemplateId && preflightTemplateId.value ? preflightTemplateId.value : "").trim();
          const requiredItemsRaw = (preflightRequiredItems && preflightRequiredItems.value ? preflightRequiredItems.value : "").trim();
          if (templateId) {
            payload.template_id = templateId;
          }
          if (requiredItemsRaw) {
            payload.required_items = parseJsonOrDefault(requiredItemsRaw, []);
          }
          const row = await post(`/api/compliance/missions/${missionId}/preflight/init`, payload);
          if (preflightBox) {
            preflightBox.textContent = `当前状态: ${row.status}\n必检项数量: ${row.required_items.length}`;
          }
          showResult("success", `已初始化起飞前检查：${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (preflightLoadBtn && preflightMissionId && preflightBox) {
    preflightLoadBtn.addEventListener("click", async () => {
      const missionId = currentMissionId();
      if (!missionId) {
        showResult("warn", "请先填写任务 ID。");
        return;
      }
      await withBusyButton(preflightLoadBtn, "加载中...", async () => {
        try {
          const row = await get(`/api/compliance/missions/${missionId}/preflight`);
          preflightBox.textContent = [
            `当前状态: ${row.status}`,
            `必检项数量: ${Array.isArray(row.required_items) ? row.required_items.length : 0}`,
            `已完成数量: ${Array.isArray(row.completed_items) ? row.completed_items.length : 0}`,
            `完成时间: ${row.completed_at || "-"}`,
          ].join("\n");
          showResult("success", "已加载任务起飞前检查。");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (preflightCheckBtn && preflightMissionId && preflightItemCode && preflightItemChecked) {
    preflightCheckBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "当前为只读模式，任务检查写入已禁用。");
        return;
      }
      const missionId = currentMissionId();
      const itemCode = (preflightItemCode.value || "").trim();
      if (!missionId || !itemCode) {
        showResult("warn", "请先填写任务 ID 和检查项编码。");
        return;
      }
      await withBusyButton(preflightCheckBtn, "提交中...", async () => {
        try {
          const payload = {
            item_code: itemCode,
            checked: parseBool(preflightItemChecked.value),
            note: (preflightItemNote && preflightItemNote.value ? preflightItemNote.value : "").trim() || null,
            evidence: parseJsonOrDefault(preflightItemEvidence && preflightItemEvidence.value, {}),
          };
          const row = await post(`/api/compliance/missions/${missionId}/preflight/check-item`, payload);
          if (preflightBox) {
            preflightBox.textContent = [
              `当前状态: ${row.status}`,
              `必检项数量: ${Array.isArray(row.required_items) ? row.required_items.length : 0}`,
              `已完成数量: ${Array.isArray(row.completed_items) ? row.completed_items.length : 0}`,
            ].join("\n");
          }
          showResult("success", `已更新检查项：${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const decisionFilterSource = document.getElementById("decision-filter-source");
  const decisionFilterEntityType = document.getElementById("decision-filter-entity-type");
  const decisionFilterEntityId = document.getElementById("decision-filter-entity-id");
  const decisionFilterBtn = document.getElementById("decision-filter-btn");
  const decisionExportBtn = document.getElementById("decision-export-btn");

  function decisionQueryParams() {
    const params = new URLSearchParams();
    const source = (decisionFilterSource && decisionFilterSource.value ? decisionFilterSource.value : "").trim();
    const entityType = (decisionFilterEntityType && decisionFilterEntityType.value ? decisionFilterEntityType.value : "").trim();
    const entityId = (decisionFilterEntityId && decisionFilterEntityId.value ? decisionFilterEntityId.value : "").trim();
    if (source) {
      params.set("source", source);
    }
    if (entityType) {
      params.set("entity_type", entityType);
    }
    if (entityId) {
      params.set("entity_id", entityId);
    }
    return params;
  }

  if (decisionFilterBtn && decisionBox) {
    decisionFilterBtn.addEventListener("click", async () => {
      await withBusyButton(decisionFilterBtn, "加载中...", async () => {
        try {
          const params = decisionQueryParams();
          const query = params.toString();
          const rows = await get(`/api/compliance/decision-records${query ? `?${query}` : ""}`);
          decisionBox.textContent = !Array.isArray(rows) || !rows.length
            ? "暂无决策留痕。"
            : rows.map((item) => `${item.id} ${item.source} ${item.entity_type}/${item.entity_id} ${item.decision}`).join("\n");
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条决策留痕。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (decisionExportBtn && decisionBox) {
    decisionExportBtn.addEventListener("click", async () => {
      await withBusyButton(decisionExportBtn, "导出中...", async () => {
        try {
          const params = decisionQueryParams();
          const query = params.toString();
          const body = await get(`/api/compliance/decision-records/export${query ? `?${query}` : ""}`);
          decisionBox.textContent = `decision_export_path: ${body.file_path}`;
          showResult("success", `已导出决策留痕：${body.file_path}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  document.querySelectorAll(".js-select-approval").forEach((button) => {
    button.addEventListener("click", () => {
      const entityType = button.getAttribute("data-entity-type") || "";
      const entityId = button.getAttribute("data-entity-id") || "";
      setSelectedEntity(entityType, entityId);
      showResult("success", `已选中业务对象：${entityType}/${entityId}`);
    });
  });

  document.querySelectorAll(".js-select-zone").forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedZone(
        button.getAttribute("data-zone-id") || "",
        button.getAttribute("data-zone-name") || "",
        button.getAttribute("data-zone-type") || "",
        button.getAttribute("data-zone-layer") || "",
      );
      showResult("success", "已选中空域规则。");
    });
  });

  document.querySelectorAll(".js-select-preflight-template").forEach((button) => {
    button.addEventListener("click", () => {
      setSelectedPreflightTemplate(
        button.getAttribute("data-template-id") || "",
        button.getAttribute("data-template-name") || "",
        button.getAttribute("data-template-version") || "",
      );
      showResult("success", "已选中起飞前检查模板。");
    });
  });

  refreshApprovalFlowVisualization();

  if (!canApprovalWrite && !canMissionWrite) {
    showResult("warn", "当前为只读模式，写入动作已禁用。");
  } else if (!canMissionRead) {
    showResult("warn", "当前缺少 mission.read，任务合规数据已隐藏。");
  }
})();
