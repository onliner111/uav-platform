(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const canOpenPlatformWrite = Boolean(window.__CAN_OPEN_PLATFORM_WRITE);

  const resultNode = document.getElementById("open-platform-result");
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

  function renderLines(rows, formatter) {
    if (!Array.isArray(rows) || !rows.length) {
      return "暂无记录。";
    }
    return rows.map(formatter).join("\n");
  }

  async function hmacSha256Hex(secret, content) {
    const encoder = new TextEncoder();
    const keyBytes = encoder.encode(secret);
    const dataBytes = encoder.encode(content);
    const cryptoKey = await window.crypto.subtle.importKey(
      "raw",
      keyBytes,
      { name: "HMAC", hash: "SHA-256" },
      false,
      ["sign"],
    );
    const signature = await window.crypto.subtle.sign("HMAC", cryptoKey, dataBytes);
    const bytes = new Uint8Array(signature);
    return Array.from(bytes)
      .map((item) => item.toString(16).padStart(2, "0"))
      .join("");
  }

  const openCredentialKeyId = document.getElementById("open-credential-key-id");
  const openCredentialApiKey = document.getElementById("open-credential-api-key");
  const openCredentialSigningSecret = document.getElementById("open-credential-signing-secret");
  const openCredentialCreateBtn = document.getElementById("open-credential-create-btn");
  const openCredentialListBtn = document.getElementById("open-credential-list-btn");
  const openCredentialBox = document.getElementById("open-credential-box");

  if (openCredentialCreateBtn && openCredentialBox) {
    openCredentialCreateBtn.addEventListener("click", async () => {
      if (!canOpenPlatformWrite) {
        showResult("warn", "需要 reporting.write 权限。");
        return;
      }
      await withBusyButton(openCredentialCreateBtn, "创建中...", async () => {
        try {
          const payload = {};
          const keyId = (openCredentialKeyId && openCredentialKeyId.value ? openCredentialKeyId.value : "").trim();
          const apiKey = (openCredentialApiKey && openCredentialApiKey.value ? openCredentialApiKey.value : "").trim();
          const signingSecret = (
            openCredentialSigningSecret && openCredentialSigningSecret.value
              ? openCredentialSigningSecret.value
              : ""
          ).trim();
          if (keyId) {
            payload.key_id = keyId;
          }
          if (apiKey) {
            payload.api_key = apiKey;
          }
          if (signingSecret) {
            payload.signing_secret = signingSecret;
          }
          const row = await request("/api/open-platform/credentials", "POST", payload);
          openCredentialBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `访问凭据已创建: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (openCredentialListBtn && openCredentialBox) {
    openCredentialListBtn.addEventListener("click", async () => {
      await withBusyButton(openCredentialListBtn, "加载中...", async () => {
        try {
          const rows = await request("/api/open-platform/credentials", "GET");
          openCredentialBox.textContent = renderLines(
            rows,
            (item) => `${item.id} ${item.key_id} active=${item.is_active}`,
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条访问凭据。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const openWebhookName = document.getElementById("open-webhook-name");
  const openWebhookUrl = document.getElementById("open-webhook-url");
  const openWebhookEventType = document.getElementById("open-webhook-event-type");
  const openWebhookCredentialId = document.getElementById("open-webhook-credential-id");
  const openWebhookAuthType = document.getElementById("open-webhook-auth-type");
  const openWebhookCreateBtn = document.getElementById("open-webhook-create-btn");
  const openWebhookListBtn = document.getElementById("open-webhook-list-btn");
  const openWebhookBox = document.getElementById("open-webhook-box");

  if (openWebhookCreateBtn && openWebhookName && openWebhookUrl && openWebhookEventType) {
    openWebhookCreateBtn.addEventListener("click", async () => {
      if (!canOpenPlatformWrite) {
        showResult("warn", "需要 reporting.write 权限。");
        return;
      }
      const name = (openWebhookName.value || "").trim();
      const endpointUrl = (openWebhookUrl.value || "").trim();
      const eventType = (openWebhookEventType.value || "").trim();
      if (!name || !endpointUrl || !eventType) {
        showResult("warn", "必须填写名称、回调地址和事件类型。");
        return;
      }
      await withBusyButton(openWebhookCreateBtn, "创建中...", async () => {
        try {
          const payload = {
            name,
            endpoint_url: endpointUrl,
            event_type: eventType,
            auth_type: openWebhookAuthType && openWebhookAuthType.value ? openWebhookAuthType.value : "HMAC_SHA256",
          };
          const credentialId = (
            openWebhookCredentialId && openWebhookCredentialId.value ? openWebhookCredentialId.value : ""
          ).trim();
          if (credentialId) {
            payload.credential_id = credentialId;
          }
          const row = await request("/api/open-platform/webhooks", "POST", payload);
          if (openWebhookBox) {
            openWebhookBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `Webhook 已创建: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (openWebhookListBtn && openWebhookBox) {
    openWebhookListBtn.addEventListener("click", async () => {
      await withBusyButton(openWebhookListBtn, "加载中...", async () => {
        try {
          const rows = await request("/api/open-platform/webhooks", "GET");
          openWebhookBox.textContent = renderLines(
            rows,
            (item) => `${item.id} ${item.name} ${item.event_type} credential=${item.credential_id || "-"}`,
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条 Webhook 配置。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const openDispatchEndpointId = document.getElementById("open-dispatch-endpoint-id");
  const openDispatchPayload = document.getElementById("open-dispatch-payload");
  const openWebhookDispatchBtn = document.getElementById("open-webhook-dispatch-btn");
  const openDispatchBox = document.getElementById("open-dispatch-box");

  if (openWebhookDispatchBtn && openDispatchEndpointId && openDispatchBox) {
    openWebhookDispatchBtn.addEventListener("click", async () => {
      if (!canOpenPlatformWrite) {
        showResult("warn", "需要 reporting.write 权限。");
        return;
      }
      const endpointId = (openDispatchEndpointId.value || "").trim();
      if (!endpointId) {
        showResult("warn", "必须填写端点 ID。");
        return;
      }
      await withBusyButton(openWebhookDispatchBtn, "派发中...", async () => {
        try {
          const row = await request(`/api/open-platform/webhooks/${endpointId}/dispatch-test`, "POST", {
            payload: parseJsonOrDefault(openDispatchPayload && openDispatchPayload.value, {}),
          });
          openDispatchBox.textContent = JSON.stringify(row, null, 2);
          showResult("success", `测试派发状态: ${row.status}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  const openAdapterKeyId = document.getElementById("open-adapter-key-id");
  const openAdapterApiKey = document.getElementById("open-adapter-api-key");
  const openAdapterSigningSecret = document.getElementById("open-adapter-signing-secret");
  const openAdapterEventType = document.getElementById("open-adapter-event-type");
  const openAdapterPayload = document.getElementById("open-adapter-payload");
  const openAdapterIngestBtn = document.getElementById("open-adapter-ingest-btn");
  const openAdapterEventsBtn = document.getElementById("open-adapter-events-btn");
  const openAdapterBox = document.getElementById("open-adapter-box");

  if (openAdapterIngestBtn && openAdapterKeyId && openAdapterApiKey && openAdapterSigningSecret) {
    openAdapterIngestBtn.addEventListener("click", async () => {
      if (!canOpenPlatformWrite) {
        showResult("warn", "需要 reporting.write 权限。");
        return;
      }
      const keyId = (openAdapterKeyId.value || "").trim();
      const apiKey = (openAdapterApiKey.value || "").trim();
      const signingSecret = (openAdapterSigningSecret.value || "").trim();
      const eventType = (openAdapterEventType && openAdapterEventType.value ? openAdapterEventType.value : "").trim();
      if (!keyId || !apiKey || !signingSecret || !eventType) {
        showResult("warn", "必须填写 Key ID、API Key、签名密钥和事件类型。");
        return;
      }
      await withBusyButton(openAdapterIngestBtn, "写入中...", async () => {
        try {
          const body = JSON.stringify({
            event_type: eventType,
            payload: parseJsonOrDefault(openAdapterPayload && openAdapterPayload.value, {}),
          });
          const signature = await hmacSha256Hex(signingSecret, body);
          const response = await fetch("/api/open-platform/adapters/events/ingest", {
            method: "POST",
            headers: {
              "Content-Type": "application/json",
              "X-Open-Key-Id": keyId,
              "X-Open-Api-Key": apiKey,
              "X-Open-Signature": signature,
            },
            body,
          });
          const row = await response.json();
          if (!response.ok) {
            throw new Error(row.detail || "请求失败");
          }
          if (openAdapterBox) {
            openAdapterBox.textContent = JSON.stringify(row, null, 2);
          }
          showResult("success", `适配器事件已接收: ${row.id}`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }

  if (openAdapterEventsBtn && openAdapterBox) {
    openAdapterEventsBtn.addEventListener("click", async () => {
      await withBusyButton(openAdapterEventsBtn, "加载中...", async () => {
        try {
          const rows = await request("/api/open-platform/adapters/events", "GET");
          openAdapterBox.textContent = renderLines(
            rows,
            (item) => `${item.id} ${item.event_type} ${item.status} key=${item.key_id}`,
          );
          showResult("success", `已加载 ${Array.isArray(rows) ? rows.length : 0} 条适配器事件。`);
        } catch (err) {
          showResult("danger", toMessage(err));
        }
      });
    });
  }
})();
