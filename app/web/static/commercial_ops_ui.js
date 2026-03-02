(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const tenantId = window.__TENANT_ID || "";
  const canBillingWrite = Boolean(window.__CAN_BILLING_WRITE);

  const resultNode = document.getElementById("commercial-result");
  if (!token || !tenantId || !resultNode) {
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
      throw new Error(body.detail || "请求失败");
    }
    return body;
  }

  const billingPlanCode = document.getElementById("billing-plan-code");
  const billingPlanName = document.getElementById("billing-plan-name");
  const billingPlanCycle = document.getElementById("billing-plan-cycle");
  const billingPlanPriceCents = document.getElementById("billing-plan-price-cents");
  const billingPlanCurrency = document.getElementById("billing-plan-currency");
  const billingPlanQuotasJson = document.getElementById("billing-plan-quotas-json");
  const billingPlanCreateBtn = document.getElementById("billing-plan-create-btn");

  if (billingPlanCreateBtn && billingPlanCode && billingPlanName && billingPlanCycle) {
    billingPlanCreateBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      const planCode = (billingPlanCode.value || "").trim();
      const displayName = (billingPlanName.value || "").trim();
      if (!planCode || !displayName) {
        showResult("warn", "必须填写套餐编码和显示名称。");
        return;
      }
      await withBusyButton(billingPlanCreateBtn, "创建中...", async () => {
        try {
          const row = await request("/api/billing/plans", "POST", {
            plan_code: planCode,
            display_name: displayName,
            billing_cycle: billingPlanCycle.value,
            price_cents: parseIntOr(billingPlanPriceCents && billingPlanPriceCents.value, 0),
            currency: (billingPlanCurrency && billingPlanCurrency.value ? billingPlanCurrency.value : "CNY").trim() || "CNY",
            quotas: parseJsonOrDefault(billingPlanQuotasJson && billingPlanQuotasJson.value, []),
          });
          showResult("success", `套餐已创建: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const billingSubscriptionPlanId = document.getElementById("billing-subscription-plan-id");
  const billingSubscriptionStatus = document.getElementById("billing-subscription-status");
  const billingSubscriptionAutoRenew = document.getElementById("billing-subscription-auto-renew");
  const billingSubscriptionCreateBtn = document.getElementById("billing-subscription-create-btn");
  const billingOverridesJson = document.getElementById("billing-overrides-json");
  const billingOverrideUpsertBtn = document.getElementById("billing-override-upsert-btn");
  const billingSubscriptionBox = document.getElementById("billing-subscription-box");

  if (billingSubscriptionCreateBtn && billingSubscriptionPlanId && billingSubscriptionStatus) {
    billingSubscriptionCreateBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      const planId = (billingSubscriptionPlanId.value || "").trim();
      if (!planId) {
        showResult("warn", "必须填写套餐 ID。");
        return;
      }
      await withBusyButton(billingSubscriptionCreateBtn, "创建中...", async () => {
        try {
          const row = await request(`/api/billing/tenants/${tenantId}/subscriptions`, "POST", {
            plan_id: planId,
            status: billingSubscriptionStatus.value,
            auto_renew: parseBool(billingSubscriptionAutoRenew && billingSubscriptionAutoRenew.value),
            detail: { source: "ui-commercial-ops" },
          });
          if (billingSubscriptionBox) {
            billingSubscriptionBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `订阅已创建: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (billingOverrideUpsertBtn && billingOverridesJson) {
    billingOverrideUpsertBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      await withBusyButton(billingOverrideUpsertBtn, "提交中...", async () => {
        try {
          const rows = await request(`/api/billing/tenants/${tenantId}/quotas/overrides`, "PUT", {
            overrides: parseJsonOrDefault(billingOverridesJson.value, []),
          });
          if (billingSubscriptionBox) {
            billingSubscriptionBox.textContent = JSON.stringify(rows, null, 2);
          }
          showResult("success", `已更新 ${Array.isArray(rows) ? rows.length : 0} 条配额覆盖规则。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const billingUsageMeterKey = document.getElementById("billing-usage-meter-key");
  const billingUsageQuantity = document.getElementById("billing-usage-quantity");
  const billingUsageSourceEventId = document.getElementById("billing-usage-source-event-id");
  const billingUsageIngestBtn = document.getElementById("billing-usage-ingest-btn");
  const billingUsageSummaryBtn = document.getElementById("billing-usage-summary-btn");
  const billingQuotaCheckBtn = document.getElementById("billing-quota-check-btn");
  const billingUsageBox = document.getElementById("billing-usage-box");

  if (billingUsageIngestBtn && billingUsageMeterKey && billingUsageQuantity && billingUsageSourceEventId) {
    billingUsageIngestBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      const meterKey = (billingUsageMeterKey.value || "").trim();
      const sourceEventId = (billingUsageSourceEventId.value || "").trim();
      if (!meterKey || !sourceEventId) {
        showResult("warn", "必须填写计量项标识和来源事件 ID。");
        return;
      }
      await withBusyButton(billingUsageIngestBtn, "提交中...", async () => {
        try {
          const row = await request("/api/billing/usage:ingest", "POST", {
            meter_key: meterKey,
            quantity: parseIntOr(billingUsageQuantity.value, 1),
            source_event_id: sourceEventId,
            detail: { source: "ui-commercial-ops" },
          });
          if (billingUsageBox) {
            billingUsageBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `用量事件已接收: ${row.event.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (billingUsageSummaryBtn && billingUsageMeterKey) {
    billingUsageSummaryBtn.addEventListener("click", async () => {
      await withBusyButton(billingUsageSummaryBtn, "加载中...", async () => {
        try {
          const meterKey = (billingUsageMeterKey.value || "").trim();
          const query = meterKey ? `?meter_key=${encodeURIComponent(meterKey)}` : "";
          const rows = await request(`/api/billing/tenants/${tenantId}/usage/summary${query}`, "GET");
          if (billingUsageBox) {
            billingUsageBox.textContent = JSON.stringify(rows, null, 2);
          }
          showResult("success", `用量汇总记录: ${Array.isArray(rows) ? rows.length : 0} 条。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (billingQuotaCheckBtn && billingUsageMeterKey && billingUsageQuantity) {
    billingQuotaCheckBtn.addEventListener("click", async () => {
      await withBusyButton(billingQuotaCheckBtn, "校验中...", async () => {
        try {
          const meterKey = (billingUsageMeterKey.value || "").trim();
          if (!meterKey) {
            showResult("warn", "必须填写计量项标识。");
            return;
          }
          const row = await request(`/api/billing/tenants/${tenantId}/quotas:check`, "POST", {
            meter_key: meterKey,
            quantity: parseIntOr(billingUsageQuantity.value, 1),
          });
          if (billingUsageBox) {
            billingUsageBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `配额校验结果: 允许=${row.allowed}，原因=${row.reason}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const billingInvoicePeriodStart = document.getElementById("billing-invoice-period-start");
  const billingInvoicePeriodEnd = document.getElementById("billing-invoice-period-end");
  const billingInvoiceAdjustments = document.getElementById("billing-invoice-adjustments");
  const billingInvoiceGenerateBtn = document.getElementById("billing-invoice-generate-btn");
  const billingInvoiceId = document.getElementById("billing-invoice-id");
  const billingInvoiceDetailBtn = document.getElementById("billing-invoice-detail-btn");
  const billingInvoiceCloseBtn = document.getElementById("billing-invoice-close-btn");
  const billingInvoiceVoidBtn = document.getElementById("billing-invoice-void-btn");
  const billingInvoiceBox = document.getElementById("billing-invoice-box");

  function ensureInvoiceWindowDefault() {
    if (!billingInvoicePeriodStart || !billingInvoicePeriodEnd) {
      return;
    }
    if ((billingInvoicePeriodStart.value || "").trim() && (billingInvoicePeriodEnd.value || "").trim()) {
      return;
    }
    const now = new Date();
    const start = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth(), 1, 0, 0, 0));
    const end = new Date(Date.UTC(now.getUTCFullYear(), now.getUTCMonth() + 1, 1, 0, 0, 0));
    billingInvoicePeriodStart.value = start.toISOString();
    billingInvoicePeriodEnd.value = end.toISOString();
  }
  ensureInvoiceWindowDefault();

  if (billingInvoiceGenerateBtn && billingInvoicePeriodStart && billingInvoicePeriodEnd) {
    billingInvoiceGenerateBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      await withBusyButton(billingInvoiceGenerateBtn, "生成中...", async () => {
        try {
          const row = await request("/api/billing/invoices:generate", "POST", {
            tenant_id: tenantId,
            period_start: (billingInvoicePeriodStart.value || "").trim(),
            period_end: (billingInvoicePeriodEnd.value || "").trim(),
            adjustments_cents: parseIntOr(billingInvoiceAdjustments && billingInvoiceAdjustments.value, 0),
            force_recompute: true,
            detail: { source: "ui-commercial-ops" },
          });
          if (billingInvoiceId) {
            billingInvoiceId.value = row.id;
          }
          if (billingInvoiceBox) {
            billingInvoiceBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `账单已生成: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (billingInvoiceDetailBtn && billingInvoiceId) {
    billingInvoiceDetailBtn.addEventListener("click", async () => {
      const invoiceId = (billingInvoiceId.value || "").trim();
      if (!invoiceId) {
        showResult("warn", "必须填写账单 ID。");
        return;
      }
      await withBusyButton(billingInvoiceDetailBtn, "加载中...", async () => {
        try {
          const row = await request(`/api/billing/invoices/${invoiceId}`, "GET");
          if (billingInvoiceBox) {
            billingInvoiceBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `已加载账单详情: ${invoiceId}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (billingInvoiceCloseBtn && billingInvoiceId) {
    billingInvoiceCloseBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      const invoiceId = (billingInvoiceId.value || "").trim();
      if (!invoiceId) {
        showResult("warn", "必须填写账单 ID。");
        return;
      }
      await withBusyButton(billingInvoiceCloseBtn, "关闭中...", async () => {
        try {
          const row = await request(`/api/billing/invoices/${invoiceId}:close`, "POST", {
            note: "控制台关闭账单",
          });
          if (billingInvoiceBox) {
            billingInvoiceBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `账单已关闭: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (billingInvoiceVoidBtn && billingInvoiceId) {
    billingInvoiceVoidBtn.addEventListener("click", async () => {
      if (!canBillingWrite) {
        showResult("warn", "需要 billing.write 权限。");
        return;
      }
      const invoiceId = (billingInvoiceId.value || "").trim();
      if (!invoiceId) {
        showResult("warn", "必须填写账单 ID。");
        return;
      }
      await withBusyButton(billingInvoiceVoidBtn, "作废中...", async () => {
        try {
          const row = await request(`/api/billing/invoices/${invoiceId}:void`, "POST", {
            reason: "控制台作废账单",
          });
          if (billingInvoiceBox) {
            billingInvoiceBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `账单已作废: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
