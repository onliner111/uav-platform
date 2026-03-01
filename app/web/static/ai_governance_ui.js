(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";

  const canRead = Boolean(window.__CAN_AI_DATA_READ);
  const canWrite = Boolean(window.__CAN_AI_DATA_WRITE);

  const resultNode = document.getElementById("ai-governance-result");
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

  const modelKey = document.getElementById("ai-model-key");
  const modelProvider = document.getElementById("ai-model-provider");
  const modelDisplayName = document.getElementById("ai-model-display-name");
  const modelDescription = document.getElementById("ai-model-description");
  const modelCreateBtn = document.getElementById("ai-model-create-btn");
  const modelFilterKey = document.getElementById("ai-model-filter-key");
  const modelFilterProvider = document.getElementById("ai-model-filter-provider");
  const modelListBtn = document.getElementById("ai-model-list-btn");
  const modelBox = document.getElementById("ai-model-box");

  if (modelCreateBtn && modelKey && modelProvider && modelDisplayName) {
    modelCreateBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const key = (modelKey.value || "").trim();
      const provider = (modelProvider.value || "").trim();
      const displayName = (modelDisplayName.value || "").trim();
      if (!key || !provider || !displayName) {
        showResult("warn", "Model key/provider/display name are required.");
        return;
      }
      await withBusyButton(modelCreateBtn, "Creating...", async () => {
        try {
          const row = await request("/api/ai/models", "POST", {
            model_key: key,
            provider,
            display_name: displayName,
            description: (modelDescription && modelDescription.value ? modelDescription.value : "").trim() || null,
            is_active: true,
          });
          showResult("success", `Model created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (modelListBtn && modelBox) {
    modelListBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      await withBusyButton(modelListBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const key = (modelFilterKey && modelFilterKey.value ? modelFilterKey.value : "").trim();
          const provider = (modelFilterProvider && modelFilterProvider.value ? modelFilterProvider.value : "").trim();
          if (key) {
            params.set("model_key", key);
          }
          if (provider) {
            params.set("provider", provider);
          }
          const query = params.toString();
          const rows = await request(`/api/ai/models${query ? `?${query}` : ""}`, "GET");
          modelBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No model rows."
            : rows.map((item) => `${item.id} ${item.model_key} ${item.provider} ${item.display_name}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} model rows.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const versionModelId = document.getElementById("ai-version-model-id");
  const versionValue = document.getElementById("ai-version-value");
  const versionStatus = document.getElementById("ai-version-status");
  const versionThresholds = document.getElementById("ai-version-thresholds");
  const versionCreateBtn = document.getElementById("ai-version-create-btn");
  const promoteVersionId = document.getElementById("ai-promote-version-id");
  const promoteStatus = document.getElementById("ai-promote-status");
  const promoteBtn = document.getElementById("ai-promote-btn");
  const versionListBtn = document.getElementById("ai-version-list-btn");
  const versionBox = document.getElementById("ai-version-box");

  if (versionCreateBtn && versionModelId && versionValue && versionStatus && versionBox) {
    versionCreateBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const modelId = (versionModelId.value || "").trim();
      const version = (versionValue.value || "").trim();
      if (!modelId || !version) {
        showResult("warn", "Model ID and version are required.");
        return;
      }
      await withBusyButton(versionCreateBtn, "Creating...", async () => {
        try {
          const row = await request(`/api/ai/models/${modelId}/versions`, "POST", {
            version,
            status: versionStatus.value,
            threshold_defaults: parseJsonOrDefault(versionThresholds && versionThresholds.value, {}),
            detail: {},
          });
          versionBox.textContent = `version_id: ${row.id}\nstatus: ${row.status}\nversion: ${row.version}`;
          if (promoteVersionId) {
            promoteVersionId.value = row.id;
          }
          showResult("success", `Version created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (promoteBtn && versionModelId && promoteVersionId && promoteStatus) {
    promoteBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const modelId = (versionModelId.value || "").trim();
      const versionId = (promoteVersionId.value || "").trim();
      if (!modelId || !versionId) {
        showResult("warn", "Model ID and version ID are required.");
        return;
      }
      await withBusyButton(promoteBtn, "Promoting...", async () => {
        try {
          const row = await request(`/api/ai/models/${modelId}/versions/${versionId}:promote`, "POST", {
            target_status: promoteStatus.value,
          });
          showResult("success", `Version promoted: ${row.id} -> ${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (versionListBtn && versionModelId && versionBox) {
    versionListBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      const modelId = (versionModelId.value || "").trim();
      if (!modelId) {
        showResult("warn", "Model ID is required.");
        return;
      }
      await withBusyButton(versionListBtn, "Loading...", async () => {
        try {
          const rows = await request(`/api/ai/models/${modelId}/versions`, "GET");
          versionBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No versions."
            : rows.map((item) => `${item.id} ${item.version} ${item.status}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} versions.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const policyModelId = document.getElementById("ai-policy-model-id");
  const policyDefaultVersionId = document.getElementById("ai-policy-default-version-id");
  const policyTraffic = document.getElementById("ai-policy-traffic");
  const policyThreshold = document.getElementById("ai-policy-threshold");
  const policyUpsertBtn = document.getElementById("ai-policy-upsert-btn");
  const policyGetBtn = document.getElementById("ai-policy-get-btn");
  const rollbackTargetVersionId = document.getElementById("ai-rollback-target-version-id");
  const rollbackReason = document.getElementById("ai-rollback-reason");
  const rollbackBtn = document.getElementById("ai-rollback-btn");
  const policyBox = document.getElementById("ai-policy-box");

  if (policyUpsertBtn && policyModelId && policyBox) {
    policyUpsertBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const modelId = (policyModelId.value || "").trim();
      if (!modelId) {
        showResult("warn", "Model ID is required.");
        return;
      }
      await withBusyButton(policyUpsertBtn, "Saving...", async () => {
        try {
          const payload = {
            traffic_allocation: parseJsonOrDefault(policyTraffic && policyTraffic.value, []),
            threshold_overrides: parseJsonOrDefault(policyThreshold && policyThreshold.value, {}),
            detail: {},
            is_active: true,
          };
          const defaultVersionId = (policyDefaultVersionId && policyDefaultVersionId.value ? policyDefaultVersionId.value : "").trim();
          if (defaultVersionId) {
            payload.default_version_id = defaultVersionId;
          }
          const row = await request(`/api/ai/models/${modelId}/rollout-policy`, "PUT", payload);
          policyBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", "Rollout policy updated.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (policyGetBtn && policyModelId && policyBox) {
    policyGetBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      const modelId = (policyModelId.value || "").trim();
      if (!modelId) {
        showResult("warn", "Model ID is required.");
        return;
      }
      await withBusyButton(policyGetBtn, "Loading...", async () => {
        try {
          const row = await request(`/api/ai/models/${modelId}/rollout-policy`, "GET");
          policyBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", "Rollout policy loaded.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (rollbackBtn && policyModelId && rollbackTargetVersionId && policyBox) {
    rollbackBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const modelId = (policyModelId.value || "").trim();
      const targetVersionId = (rollbackTargetVersionId.value || "").trim();
      if (!modelId || !targetVersionId) {
        showResult("warn", "Model ID and target version ID are required.");
        return;
      }
      await withBusyButton(rollbackBtn, "Rolling back...", async () => {
        try {
          const row = await request(`/api/ai/models/${modelId}/rollout-policy:rollback`, "POST", {
            target_version_id: targetVersionId,
            reason: (rollbackReason && rollbackReason.value ? rollbackReason.value : "").trim() || null,
          });
          policyBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", "Rollback completed.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const recomputeModelId = document.getElementById("ai-recompute-model-id");
  const recomputeJobId = document.getElementById("ai-recompute-job-id");
  const recomputeBtn = document.getElementById("ai-recompute-btn");
  const compareLeftVersionId = document.getElementById("ai-compare-left-version-id");
  const compareRightVersionId = document.getElementById("ai-compare-right-version-id");
  const compareJobId = document.getElementById("ai-compare-job-id");
  const compareBtn = document.getElementById("ai-compare-btn");
  const evalBox = document.getElementById("ai-eval-box");

  if (recomputeBtn && evalBox) {
    recomputeBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      await withBusyButton(recomputeBtn, "Recomputing...", async () => {
        try {
          const payload = {};
          const modelId = (recomputeModelId && recomputeModelId.value ? recomputeModelId.value : "").trim();
          const jobId = (recomputeJobId && recomputeJobId.value ? recomputeJobId.value : "").trim();
          if (modelId) {
            payload.model_id = modelId;
          }
          if (jobId) {
            payload.job_id = jobId;
          }
          const rows = await request("/api/ai/evaluations:recompute", "POST", payload);
          evalBox.textContent = JSON.stringify(rows, null, 2);
          showResult("success", `Recomputed ${Array.isArray(rows) ? rows.length : 0} evaluation summaries.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (compareBtn && compareLeftVersionId && compareRightVersionId && evalBox) {
    compareBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      const leftVersionId = (compareLeftVersionId.value || "").trim();
      const rightVersionId = (compareRightVersionId.value || "").trim();
      if (!leftVersionId || !rightVersionId) {
        showResult("warn", "Left and right version IDs are required.");
        return;
      }
      await withBusyButton(compareBtn, "Comparing...", async () => {
        try {
          const params = new URLSearchParams();
          params.set("left_version_id", leftVersionId);
          params.set("right_version_id", rightVersionId);
          const jobId = (compareJobId && compareJobId.value ? compareJobId.value : "").trim();
          if (jobId) {
            params.set("job_id", jobId);
          }
          const body = await request(`/api/ai/evaluations/compare?${params.toString()}`, "GET");
          evalBox.textContent = JSON.stringify(body, null, 2);
          showResult("success", "Evaluation compare completed.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const jobTaskId = document.getElementById("ai-job-task-id");
  const jobMissionId = document.getElementById("ai-job-mission-id");
  const jobTopic = document.getElementById("ai-job-topic");
  const jobType = document.getElementById("ai-job-type");
  const jobTriggerMode = document.getElementById("ai-job-trigger-mode");
  const jobModelVersionId = document.getElementById("ai-job-model-version-id");
  const jobCreateBtn = document.getElementById("ai-job-create-btn");
  const jobIdInput = document.getElementById("ai-job-id");
  const jobsListBtn = document.getElementById("ai-jobs-list-btn");
  const runsListBtn = document.getElementById("ai-runs-list-btn");
  const runTriggerBtn = document.getElementById("ai-run-trigger-btn");
  const retryRunId = document.getElementById("ai-retry-run-id");
  const runRetryBtn = document.getElementById("ai-run-retry-btn");
  const jobRunBox = document.getElementById("ai-job-run-box");

  if (jobCreateBtn && jobRunBox) {
    jobCreateBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      await withBusyButton(jobCreateBtn, "Creating...", async () => {
        try {
          const payload = {
            job_type: (jobType && jobType.value ? jobType.value : "SUMMARY"),
            trigger_mode: (jobTriggerMode && jobTriggerMode.value ? jobTriggerMode.value : "MANUAL"),
          };
          const taskId = (jobTaskId && jobTaskId.value ? jobTaskId.value : "").trim();
          const missionId = (jobMissionId && jobMissionId.value ? jobMissionId.value : "").trim();
          const topic = (jobTopic && jobTopic.value ? jobTopic.value : "").trim();
          const modelVersionId = (jobModelVersionId && jobModelVersionId.value ? jobModelVersionId.value : "").trim();
          if (taskId) {
            payload.task_id = taskId;
          }
          if (missionId) {
            payload.mission_id = missionId;
          }
          if (topic) {
            payload.topic = topic;
          }
          if (modelVersionId) {
            payload.model_version_id = modelVersionId;
          }
          const row = await request("/api/ai/jobs", "POST", payload);
          if (jobIdInput) {
            jobIdInput.value = row.id;
          }
          jobRunBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `Job created: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (jobsListBtn && jobRunBox) {
    jobsListBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      await withBusyButton(jobsListBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const taskId = (jobTaskId && jobTaskId.value ? jobTaskId.value : "").trim();
          const missionId = (jobMissionId && jobMissionId.value ? jobMissionId.value : "").trim();
          if (taskId) {
            params.set("task_id", taskId);
          }
          if (missionId) {
            params.set("mission_id", missionId);
          }
          const query = params.toString();
          const rows = await request(`/api/ai/jobs${query ? `?${query}` : ""}`, "GET");
          jobRunBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No jobs."
            : rows.map((item) => `${item.id} ${item.job_type} ${item.trigger_mode} ${item.model_version_id || "-"}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} jobs.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (runsListBtn && jobIdInput && jobRunBox) {
    runsListBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      const jobId = (jobIdInput.value || "").trim();
      if (!jobId) {
        showResult("warn", "Job ID is required.");
        return;
      }
      await withBusyButton(runsListBtn, "Loading...", async () => {
        try {
          const rows = await request(`/api/ai/jobs/${jobId}/runs`, "GET");
          jobRunBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No runs."
            : rows.map((item) => `${item.id} ${item.status} retry=${item.retry_count}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} runs.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (runTriggerBtn && jobIdInput && jobRunBox) {
    runTriggerBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const jobId = (jobIdInput.value || "").trim();
      if (!jobId) {
        showResult("warn", "Job ID is required.");
        return;
      }
      await withBusyButton(runTriggerBtn, "Triggering...", async () => {
        try {
          const row = await request(`/api/ai/jobs/${jobId}/runs`, "POST", {
            force_fail: false,
            context: { source: "ui-phase29" },
          });
          jobRunBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `Run triggered: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (runRetryBtn && retryRunId && jobRunBox) {
    runRetryBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const runId = (retryRunId.value || "").trim();
      if (!runId) {
        showResult("warn", "Run ID is required.");
        return;
      }
      await withBusyButton(runRetryBtn, "Retrying...", async () => {
        try {
          const row = await request(`/api/ai/runs/${runId}/retry`, "POST", {
            force_fail: false,
            context: { source: "ui-phase29-retry" },
          });
          jobRunBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `Run retry executed: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const outputFilterJobId = document.getElementById("ai-output-filter-job-id");
  const outputFilterRunId = document.getElementById("ai-output-filter-run-id");
  const outputFilterStatus = document.getElementById("ai-output-filter-status");
  const outputsListBtn = document.getElementById("ai-outputs-list-btn");
  const outputIdInput = document.getElementById("ai-output-id");
  const outputReviewGetBtn = document.getElementById("ai-output-review-get-btn");
  const reviewAction = document.getElementById("ai-review-action");
  const reviewNote = document.getElementById("ai-review-note");
  const reviewOverride = document.getElementById("ai-review-override");
  const outputReviewSubmitBtn = document.getElementById("ai-output-review-submit-btn");
  const outputBox = document.getElementById("ai-output-box");

  if (outputsListBtn && outputBox) {
    outputsListBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      await withBusyButton(outputsListBtn, "Loading...", async () => {
        try {
          const params = new URLSearchParams();
          const jobId = (outputFilterJobId && outputFilterJobId.value ? outputFilterJobId.value : "").trim();
          const runId = (outputFilterRunId && outputFilterRunId.value ? outputFilterRunId.value : "").trim();
          const reviewStatus = (outputFilterStatus && outputFilterStatus.value ? outputFilterStatus.value : "").trim();
          if (jobId) {
            params.set("job_id", jobId);
          }
          if (runId) {
            params.set("run_id", runId);
          }
          if (reviewStatus) {
            params.set("review_status", reviewStatus);
          }
          const query = params.toString();
          const rows = await request(`/api/ai/outputs${query ? `?${query}` : ""}`, "GET");
          outputBox.textContent = !Array.isArray(rows) || !rows.length
            ? "No outputs."
            : rows.map((item) => `${item.id} ${item.review_status} ${item.control_allowed ? "CTRL" : "NO_CTRL"}`).join("\n");
          showResult("success", `Loaded ${Array.isArray(rows) ? rows.length : 0} outputs.`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (outputReviewGetBtn && outputIdInput && outputBox) {
    outputReviewGetBtn.addEventListener("click", async () => {
      if (!canRead) {
        showResult("warn", "Read permission is required.");
        return;
      }
      const outputId = (outputIdInput.value || "").trim();
      if (!outputId) {
        showResult("warn", "Output ID is required.");
        return;
      }
      await withBusyButton(outputReviewGetBtn, "Loading...", async () => {
        try {
          const body = await request(`/api/ai/outputs/${outputId}/review`, "GET");
          outputBox.textContent = [
            `output_id: ${body.output.id}`,
            `review_status: ${body.output.review_status}`,
            `action_count: ${Array.isArray(body.actions) ? body.actions.length : 0}`,
            `evidence_count: ${Array.isArray(body.evidences) ? body.evidences.length : 0}`,
            "--- evidences ---",
            Array.isArray(body.evidences) && body.evidences.length
              ? body.evidences.map((item) => `${item.evidence_type} ${item.content_hash}`).join("\n")
              : "No evidences.",
          ].join("\n");
          showResult("success", "Review bundle loaded.");
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (outputReviewSubmitBtn && outputIdInput && reviewAction && outputBox) {
    outputReviewSubmitBtn.addEventListener("click", async () => {
      if (!canWrite) {
        showResult("warn", "Write permission is required.");
        return;
      }
      const outputId = (outputIdInput.value || "").trim();
      if (!outputId) {
        showResult("warn", "Output ID is required.");
        return;
      }
      await withBusyButton(outputReviewSubmitBtn, "Submitting...", async () => {
        try {
          const row = await request(`/api/ai/outputs/${outputId}/review`, "POST", {
            action_type: reviewAction.value,
            note: (reviewNote && reviewNote.value ? reviewNote.value : "").trim() || null,
            override_payload: parseJsonOrDefault(reviewOverride && reviewOverride.value, {}),
            detail: {},
          });
          outputBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `Review action submitted: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (!canWrite) {
    showResult("warn", "Read-only mode: AI write actions are disabled.");
  }
})();
