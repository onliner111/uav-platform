(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canIdentityWrite = Boolean(window.__CAN_IDENTITY_WRITE);

  const resultNode = document.getElementById("platform-result");
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
    const body = response.status === 204 ? null : await response.json();
    if (!response.ok) {
      throw new Error((body && body.detail) || "请求失败，请稍后重试。");
    }
    return body;
  }

  const wizardStatus = document.getElementById("platform-wizard-status");
  const roleContext = document.getElementById("platform-role-context");
  const userContext = document.getElementById("platform-user-context");
  const onboardingSummary = document.getElementById("platform-onboarding-summary");
  const modeStatus = document.getElementById("platform-mode-status");
  const handoffStatus = document.getElementById("platform-handoff-status");
  const releaseStatus = document.getElementById("platform-release-status");
  const releaseSummary = document.getElementById("platform-release-summary");
  const helpStatus = document.getElementById("platform-help-status");
  const helpSummary = document.getElementById("platform-help-summary");
  const releaseNoteStatus = document.getElementById("platform-release-note-status");
  const releaseNoteSummary = document.getElementById("platform-release-note-summary");
  const flagStatus = document.getElementById("platform-flag-status");

  const orgName = document.getElementById("platform-org-name");
  const orgCode = document.getElementById("platform-org-code");
  const orgType = document.getElementById("platform-org-type");
  const orgCreateBtn = document.getElementById("platform-org-create-btn");

  const roleTemplate = document.getElementById("platform-role-template");
  const roleName = document.getElementById("platform-role-name");
  const roleCreateBtn = document.getElementById("platform-role-create-btn");

  const userName = document.getElementById("platform-user-name");
  const userPassword = document.getElementById("platform-user-password");
  const userPurpose = document.getElementById("platform-user-purpose");
  const userCreateBtn = document.getElementById("platform-user-create-btn");

  const modeSelect = document.getElementById("platform-mode-select");
  const modeApplyBtn = document.getElementById("platform-mode-apply-btn");

  let selectedPackName = "";
  let createdOrg = null;
  let createdRole = null;
  let createdUser = null;
  let selectedGuideTitle = "";
  let selectedReleaseNoteTitle = "";
  const checkedReleaseItems = new Set();
  const flagStates = {
    "guided-workflows": true,
    "training-copy": true,
    "gray-release": false,
  };

  function refreshSummary() {
    if (!onboardingSummary) {
      return;
    }
    const packText = selectedPackName ? `已采用 ${selectedPackName}` : "尚未选择配置包";
    onboardingSummary.innerHTML = [
      `<div class="hint-list-item">配置包：${packText}</div>`,
      `<div class="hint-list-item">组织骨架：${createdOrg ? `${createdOrg.name}（${createdOrg.code}）` : "待创建或继续完善"}</div>`,
      `<div class="hint-list-item">标准角色：${createdRole ? createdRole.name : "待从模板生成"}</div>`,
      `<div class="hint-list-item">启动账号：${createdUser ? createdUser.username : "待创建并绑定"}</div>`,
    ].join("");
  }

  function refreshReleaseSummary() {
    if (!releaseSummary) {
      return;
    }
    const checkedCount = checkedReleaseItems.size;
    const isReady = checkedCount >= 4;
    releaseSummary.innerHTML = [
      `<div class="hint-list-item">已完成检查：${checkedCount} / 4</div>`,
      `<div class="hint-list-item">${isReady ? "可进入生产模式，但仍建议先完成交接确认。" : "未完成全部基础检查，暂不建议直接切到生产模式。"}</div>`,
    ].join("");
  }

  function setReleaseStatus(message) {
    if (releaseStatus) {
      releaseStatus.textContent = message;
    }
  }

  function setHelpStatus(message) {
    if (helpStatus) {
      helpStatus.textContent = message;
    }
  }

  function setReleaseNoteStatus(message) {
    if (releaseNoteStatus) {
      releaseNoteStatus.textContent = message;
    }
  }

  function refreshHelpSummary() {
    if (!helpSummary) {
      return;
    }
    helpSummary.innerHTML = [
      `<div class="hint-list-item">当前帮助主题：${selectedGuideTitle || "未选择，建议先使用培训演练脚本。"}</div>`,
      `<div class="hint-list-item">当前模式：${modeSelect ? modeSelect.options[modeSelect.selectedIndex].text : "演示模式"}</div>`,
    ].join("");
  }

  function refreshReleaseNoteSummary() {
    if (!releaseNoteSummary) {
      return;
    }
    releaseNoteSummary.innerHTML = [
      `<div class="hint-list-item">当前发布重点：${selectedReleaseNoteTitle || "未选择，建议先强调本轮最直接影响上线的变化。"}</div>`,
      `<div class="hint-list-item">灰度启用：${flagStates["gray-release"] ? "已开启" : "未开启"}</div>`,
    ].join("");
  }

  function flagMeta(enabled) {
    if (enabled) {
      return { label: "已开启", tone: "success" };
    }
    return { label: "已关闭", tone: "muted" };
  }

  function refreshFlagState(flagKey) {
    const pill = document.getElementById(`platform-flag-pill-${flagKey}`);
    if (!pill) {
      return;
    }
    const meta = flagMeta(Boolean(flagStates[flagKey]));
    pill.textContent = meta.label;
    pill.className = `status-pill ${meta.tone}`;
  }

  function refreshAllFlagStates() {
    Object.keys(flagStates).forEach(refreshFlagState);
    if (flagStatus) {
      const enabled = Object.entries(flagStates)
        .filter(([, value]) => Boolean(value))
        .map(([key]) => key)
        .length;
      flagStatus.textContent =
        enabled >= 2
          ? `当前已有 ${enabled} 项推荐能力处于开启状态。建议灰度启用时先覆盖管理员和关键岗位。`
          : "当前启用项较少。建议至少保持向导式主路径和培训提示开启。";
    }
    refreshReleaseNoteSummary();
  }

  function setWizardStatus(message) {
    if (wizardStatus) {
      wizardStatus.textContent = message;
    }
  }

  function setRoleStatus(message) {
    if (roleContext) {
      roleContext.textContent = message;
    }
  }

  function setUserStatus(message) {
    if (userContext) {
      userContext.textContent = message;
    }
  }

  document.querySelectorAll(".js-platform-pack").forEach((button) => {
    button.addEventListener("click", () => {
      selectedPackName = button.getAttribute("data-pack-name") || button.getAttribute("data-pack-key") || "";
      const packKey = button.getAttribute("data-pack-key") || "";
      if (modeSelect) {
        if (packKey === "training-pack") {
          modeSelect.value = "TRAINING";
        } else if (packKey === "production-pack") {
          modeSelect.value = "PRODUCTION";
        } else {
          modeSelect.value = "DEMO";
        }
      }
      refreshSummary();
      setWizardStatus(`已采用配置包：${selectedPackName}。建议按上方步骤继续完成组织、角色和账号准备。`);
      showResult("success", `已采用配置包：${selectedPackName}`);
    });
  });

  document.querySelectorAll(".js-platform-release-item").forEach((button) => {
    button.addEventListener("click", () => {
      const releaseKey = button.getAttribute("data-release-key") || "";
      const releaseLabel = button.getAttribute("data-release-label") || releaseKey;
      checkedReleaseItems.add(releaseKey);
      const checkedCount = checkedReleaseItems.size;
      const isReady = checkedCount >= 4;
      setReleaseStatus(
        isReady
          ? "基础上线检查已完成。建议切换到生产模式，并完成客户交接后再正式启用。"
          : `已核对：${releaseLabel}。当前完成 ${checkedCount} / 4 项基础检查。`
      );
      refreshReleaseSummary();
      showResult("success", `已更新上线检查：${releaseLabel}`);
    });
  });

  document.querySelectorAll(".js-platform-help-card").forEach((button) => {
    button.addEventListener("click", () => {
      selectedGuideTitle = button.getAttribute("data-guide-title") || button.getAttribute("data-guide-key") || "";
      setHelpStatus(`已将“${selectedGuideTitle}”设为当前帮助主题。建议结合当前模式进行统一讲解。`);
      refreshHelpSummary();
      showResult("success", `已更新帮助主题：${selectedGuideTitle}`);
    });
  });

  document.querySelectorAll(".js-platform-release-note").forEach((button) => {
    button.addEventListener("click", () => {
      selectedReleaseNoteTitle =
        button.getAttribute("data-note-title") || button.getAttribute("data-note-key") || "";
      setReleaseNoteStatus(`已将“${selectedReleaseNoteTitle}”设为当前发布重点。建议同步给客户管理员和关键岗位。`);
      refreshReleaseNoteSummary();
      showResult("success", `已更新发布重点：${selectedReleaseNoteTitle}`);
    });
  });

  document.querySelectorAll(".js-platform-flag-toggle").forEach((button) => {
    button.addEventListener("click", () => {
      const flagKey = button.getAttribute("data-flag-key") || "";
      const flagLabel = button.getAttribute("data-flag-label") || flagKey;
      flagStates[flagKey] = !flagStates[flagKey];
      refreshFlagState(flagKey);
      refreshAllFlagStates();
      showResult("success", `${flagLabel} 已${flagStates[flagKey] ? "开启" : "关闭"}。`);
    });
  });

  document.querySelectorAll(".js-platform-template").forEach((button) => {
    button.addEventListener("click", () => {
      const templateKey = button.getAttribute("data-template-key") || "";
      const templateName = button.getAttribute("data-template-name") || "";
      if (roleTemplate) {
        roleTemplate.value = templateKey;
      }
      if (roleName && !String(roleName.value || "").trim()) {
        roleName.value = templateName;
      }
      setRoleStatus(`已选中模板：${templateName || templateKey}。可直接创建标准角色。`);
      showResult("success", "已将角色模板带入开通向导。");
    });
  });

  if (orgCreateBtn && orgName && orgCode && orgType) {
    orgCreateBtn.addEventListener("click", async () => {
      if (!canIdentityWrite) {
        showResult("warn", "当前账号缺少 identity.write 权限。");
        return;
      }
      const name = String(orgName.value || "").trim();
      const code = String(orgCode.value || "").trim();
      if (!name || !code) {
        showResult("warn", "请先填写组织名称和组织编码。");
        return;
      }
      await withBusyButton(orgCreateBtn, "创建中...", async () => {
        try {
          const row = await request("/api/identity/org-units", "POST", {
            name,
            code,
            unit_type: orgType.value,
            is_active: true,
          });
          createdOrg = row;
          refreshSummary();
          setWizardStatus(`已创建组织骨架：${row.name}。下一步建议从模板生成角色。`);
          showResult("success", `已创建组织骨架：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (roleCreateBtn && roleTemplate) {
    roleCreateBtn.addEventListener("click", async () => {
      if (!canIdentityWrite) {
        showResult("warn", "当前账号缺少 identity.write 权限。");
        return;
      }
      const templateKey = String(roleTemplate.value || "").trim();
      if (!templateKey) {
        showResult("warn", "请先选择角色模板。");
        return;
      }
      await withBusyButton(roleCreateBtn, "生成中...", async () => {
        try {
          const payload = { template_key: templateKey };
          const desiredName = String(roleName && roleName.value ? roleName.value : "").trim();
          if (desiredName) {
            payload.name = desiredName;
          }
          const row = await request("/api/identity/roles:from-template", "POST", payload);
          createdRole = row;
          setRoleStatus(`已生成标准角色：${row.name}。创建账号时会优先绑定到该角色。`);
          refreshSummary();
          setWizardStatus(`已生成标准角色：${row.name}。下一步建议创建启动账号。`);
          showResult("success", `已生成标准角色：${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (userCreateBtn && userName && userPassword) {
    userCreateBtn.addEventListener("click", async () => {
      if (!canIdentityWrite) {
        showResult("warn", "当前账号缺少 identity.write 权限。");
        return;
      }
      const username = String(userName.value || "").trim();
      const password = String(userPassword.value || "").trim();
      if (!username || !password) {
        showResult("warn", "请先填写账号名和初始密码。");
        return;
      }
      await withBusyButton(userCreateBtn, "创建中...", async () => {
        try {
          const user = await request("/api/identity/users", "POST", {
            username,
            password,
            is_active: true,
          });
          createdUser = user;
          if (createdRole && createdRole.id) {
            await request(`/api/identity/users/${user.id}/roles/${createdRole.id}`, "POST");
          }
          if (createdOrg && createdOrg.id) {
            await request(`/api/identity/users/${user.id}/org-units/${createdOrg.id}`, "POST", {
              is_primary: true,
              job_title: userPurpose && userPurpose.value === "TRAINING" ? "培训账号" : userPurpose && userPurpose.value === "OPS" ? "运维联系人" : "交付管理员",
              is_manager: true,
            });
          }
          setUserStatus(`已创建账号：${user.username}。${createdRole ? "角色已绑定。" : "尚未绑定角色。"}${createdOrg ? "组织已绑定。" : "尚未绑定组织。"}`);
          refreshSummary();
          setWizardStatus(`开通向导已推进到账号准备阶段。建议切换到合适模式并完成交接。`);
          showResult("success", `已创建并处理启动账号：${user.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (modeApplyBtn && modeSelect) {
    modeApplyBtn.addEventListener("click", () => {
      const value = String(modeSelect.value || "DEMO");
      const mapping = {
        DEMO: "当前为演示模式：适合方案演示和领导参观，不建议录入正式生产数据。",
        TRAINING: "当前为培训模式：适合演练操作和培训新用户，建议使用专门培训账号。",
        PRODUCTION: "当前为生产模式：适合正式上线，建议确认组织、角色和交接清单均已完成。",
      };
      const handoffMapping = {
        DEMO: "演示模式已启用。优先确认演示账号、案例素材和领导汇报路径。",
        TRAINING: "培训模式已启用。优先确认培训账号、演练脚本和回退说明。",
        PRODUCTION: "生产模式已启用。优先确认客户交接、运维交接和租户导出留存。",
      };
      if (modeStatus) {
        modeStatus.textContent = mapping[value] || mapping.DEMO;
      }
      if (handoffStatus) {
        handoffStatus.textContent = handoffMapping[value] || handoffMapping.DEMO;
      }
      if (value === "TRAINING") {
        setHelpStatus("当前为培训模式。建议先使用“培训演练脚本”，再逐步演示巡检、应急和闭环路径。");
      } else if (value === "PRODUCTION") {
        setHelpStatus("当前为生产模式。帮助提示应以简洁操作路径为主，避免继续使用培训话术。");
      } else {
        setHelpStatus("当前为演示模式。建议突出角色入口、地图态势和闭环看板的演示路径。");
      }
      refreshHelpSummary();
      showResult("success", "已更新当前交付模式。");
    });
  }

  refreshSummary();
  refreshReleaseSummary();
  refreshHelpSummary();
  refreshReleaseNoteSummary();
  refreshAllFlagStates();
})();
