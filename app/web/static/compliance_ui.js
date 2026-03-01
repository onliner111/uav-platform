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
      await withBusyButton(approvalFilterBtn, "Loading...", async () => {
        try {
          const params = selectedApprovalFilters();
          const query = params.toString();
          const rows = await get(`/api/approvals${query ? `?${query}` : ""}`);
          approvalBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No approvals."
            : rows.map((item) => `${item.id} ${item.entity_type} ${item.entity_id} ${item.status}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} approvals.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approvalExportBtn) {
    approvalExportBtn.addEventListener("click", async () => {
      await withBusyButton(approvalExportBtn, "Exporting...", async () => {
        try {
          const body = await get("/api/approvals/audit-export");
          if (approvalBox) {
            approvalBox.textContent = `audit_export_path: ${body.file_path}`;
          }
          showResult("success", `Approval audit exported: ${body.file_path}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approvalCreateBtn && approvalCreateEntityType && approvalCreateEntityId && approvalCreateStatus) {
    approvalCreateBtn.addEventListener("click", async () => {
      if (!canApprovalWrite) {
        showResult("warn", "Read-only mode: approval write actions are disabled.");
        return;
      }
      const entityType = (approvalCreateEntityType.value || "").trim();
      const entityId = (approvalCreateEntityId.value || "").trim();
      const status = (approvalCreateStatus.value || "").trim();
      if (!entityType || !entityId || !status) {
        showResult("warn", "Entity type, entity id and status are required.");
        return;
      }
      await withBusyButton(approvalCreateBtn, "Creating...", async () => {
        try {
          const row = await post("/api/approvals", {
            entity_type: entityType,
            entity_id: entityId,
            status,
          });
          showResult("success", `Approval created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (approvalBatchCreateBtn && approvalBatchEntityType && approvalBatchStatus && approvalBatchEntityIds) {
    approvalBatchCreateBtn.addEventListener("click", async () => {
      if (!canApprovalWrite) {
        showResult("warn", "Read-only mode: approval write actions are disabled.");
        return;
      }
      const entityType = (approvalBatchEntityType.value || "").trim();
      const status = (approvalBatchStatus.value || "").trim();
      const ids = (approvalBatchEntityIds.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!entityType || !status || !ids.length) {
        showResult("warn", "Entity type, status and at least one entity id are required.");
        return;
      }
      await withBusyButton(approvalBatchCreateBtn, "Creating...", async () => {
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
          showResult("success", `Batch approvals created: ${success}/${ids.length}`);
          return;
        }
        showResult("warn", `Batch partial: ${success}/${ids.length}. ${failures.join(" | ")}`);
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
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const name = (flowTemplateName.value || "").trim();
      const entityType = (flowTemplateEntityType.value || "").trim();
      if (!name || !entityType) {
        showResult("warn", "Template name and entity type are required.");
        return;
      }
      await withBusyButton(flowTemplateCreateBtn, "Creating...", async () => {
        try {
          const steps = parseJsonOrDefault(flowTemplateSteps.value, []);
          if (!Array.isArray(steps) || !steps.length) {
            showResult("warn", "Steps JSON must be a non-empty array.");
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
          showResult("success", `Flow template created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowInstanceCreateBtn && flowInstanceTemplateId && flowInstanceEntityType && flowInstanceEntityId) {
    flowInstanceCreateBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const templateId = (flowInstanceTemplateId.value || "").trim();
      const entityType = (flowInstanceEntityType.value || "").trim();
      const entityId = (flowInstanceEntityId.value || "").trim();
      if (!templateId || !entityType || !entityId) {
        showResult("warn", "Template id, entity type and entity id are required.");
        return;
      }
      await withBusyButton(flowInstanceCreateBtn, "Creating...", async () => {
        try {
          const row = await post("/api/compliance/approval-flows/instances", {
            template_id: templateId,
            entity_type: entityType,
            entity_id: entityId,
          });
          if (flowBox) {
            flowBox.textContent = `flow_instance_id: ${row.id}\nstatus: ${row.status}`;
          }
          if (flowActionInstanceId) {
            flowActionInstanceId.value = row.id;
          }
          showResult("success", `Flow instance created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowActionBtn && flowActionInstanceId && flowActionType) {
    flowActionBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const instanceId = (flowActionInstanceId.value || "").trim();
      if (!instanceId) {
        showResult("warn", "Flow instance id is required.");
        return;
      }
      await withBusyButton(flowActionBtn, "Applying...", async () => {
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
          showResult("success", `Flow action applied: ${row.status}`);
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
        showResult("warn", "Flow instance id is required.");
        return;
      }
      await withBusyButton(flowLoadBtn, "Loading...", async () => {
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
          showResult("success", "Flow instance loaded.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (flowBatchActionBtn && flowBatchInstanceIds && flowBatchAction) {
    flowBatchActionBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const ids = (flowBatchInstanceIds.value || "")
        .split(/\r?\n/)
        .map((item) => item.trim())
        .filter((item) => item.length > 0);
      if (!ids.length) {
        showResult("warn", "At least one flow instance id is required.");
        return;
      }
      await withBusyButton(flowBatchActionBtn, "Applying...", async () => {
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
          showResult("success", `Batch flow actions applied: ${success}/${ids.length}`);
          return;
        }
        showResult("warn", `Batch partial: ${success}/${ids.length}. ${failures.join(" | ")}`);
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
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const name = (zoneCreateName.value || "").trim();
      const geomWkt = (zoneCreateWkt.value || "").trim();
      if (!name || !geomWkt) {
        showResult("warn", "Zone name and polygon WKT are required.");
        return;
      }
      await withBusyButton(zoneCreateBtn, "Creating...", async () => {
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
          showResult("success", `Zone created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (zoneFilterBtn && zoneBox) {
    zoneFilterBtn.addEventListener("click", async () => {
      await withBusyButton(zoneFilterBtn, "Loading...", async () => {
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
            ? "No zones."
            : rows.map((item) => `${item.id} ${item.zone_type} ${item.policy_layer} ${item.policy_effect}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} zones.`);
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
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const name = (preflightTemplateName.value || "").trim();
      if (!name) {
        showResult("warn", "Template name is required.");
        return;
      }
      await withBusyButton(preflightTemplateCreateBtn, "Creating...", async () => {
        try {
          const items = parseJsonOrDefault(preflightTemplateItems.value, []);
          if (!Array.isArray(items) || !items.length) {
            showResult("warn", "Template items JSON must be a non-empty array.");
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
          showResult("success", `Preflight template created: ${row.id}`);
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
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const missionId = currentMissionId();
      if (!missionId) {
        showResult("warn", "Mission ID is required.");
        return;
      }
      await withBusyButton(preflightInitBtn, "Initializing...", async () => {
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
            preflightBox.textContent = `status: ${row.status}\nrequired_items: ${row.required_items.length}`;
          }
          showResult("success", `Preflight initialized: ${row.status}`);
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
        showResult("warn", "Mission ID is required.");
        return;
      }
      await withBusyButton(preflightLoadBtn, "Loading...", async () => {
        try {
          const row = await get(`/api/compliance/missions/${missionId}/preflight`);
          preflightBox.textContent = [
            `status: ${row.status}`,
            `required_items: ${Array.isArray(row.required_items) ? row.required_items.length : 0}`,
            `completed_items: ${Array.isArray(row.completed_items) ? row.completed_items.length : 0}`,
            `completed_at: ${row.completed_at || "-"}`,
          ].join("\n");
          showResult("success", "Loaded mission preflight.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (preflightCheckBtn && preflightMissionId && preflightItemCode && preflightItemChecked) {
    preflightCheckBtn.addEventListener("click", async () => {
      if (!canMissionWrite) {
        showResult("warn", "Read-only mode: mission write actions are disabled.");
        return;
      }
      const missionId = currentMissionId();
      const itemCode = (preflightItemCode.value || "").trim();
      if (!missionId || !itemCode) {
        showResult("warn", "Mission ID and item code are required.");
        return;
      }
      await withBusyButton(preflightCheckBtn, "Submitting...", async () => {
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
              `status: ${row.status}`,
              `required_items: ${Array.isArray(row.required_items) ? row.required_items.length : 0}`,
              `completed_items: ${Array.isArray(row.completed_items) ? row.completed_items.length : 0}`,
            ].join("\n");
          }
          showResult("success", `Preflight item updated: ${row.status}`);
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
      await withBusyButton(decisionFilterBtn, "Loading...", async () => {
        try {
          const params = decisionQueryParams();
          const query = params.toString();
          const rows = await get(`/api/compliance/decision-records${query ? `?${query}` : ""}`);
          decisionBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No decision records."
            : rows.map((item) => `${item.id} ${item.source} ${item.entity_type}/${item.entity_id} ${item.decision}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} decision records.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (decisionExportBtn && decisionBox) {
    decisionExportBtn.addEventListener("click", async () => {
      await withBusyButton(decisionExportBtn, "Exporting...", async () => {
        try {
          const params = decisionQueryParams();
          const query = params.toString();
          const body = await get(`/api/compliance/decision-records/export${query ? `?${query}` : ""}`);
          decisionBox.textContent = `decision_export_path: ${body.file_path}`;
          showResult("success", `Decision records exported: ${body.file_path}`);
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
      showResult("success", `Selected entity: ${entityType}/${entityId}`);
    });
  });

  if (!canApprovalWrite && !canMissionWrite) {
    showResult("warn", "Read-only mode: write actions are disabled.");
  } else if (!canMissionRead) {
    showResult("warn", "Mission compliance datasets are hidden because mission.read is missing.");
  }
})();
