(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const ui = window.UIActionUtils || null;
  const token = window.__TOKEN || auth.token;
  const csrfToken = auth.csrfToken || "";
  const taskId = window.__TASK_ID || "";
  const canInspectionWrite = Boolean(window.__CAN_INSPECTION_WRITE);
  const canDefectWrite = Boolean(window.__CAN_DEFECT_WRITE);
  const observations = Array.isArray(window.__OBS) ? window.__OBS : [];
  const map = L.map("map");
  const center = observations.length ? [observations[0].position_lat, observations[0].position_lon] : [30.5928, 114.3055];
  map.setView(center, 12);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const exportBtn = document.getElementById("export-btn");
  const exportResult = document.getElementById("export-result");
  const resultNode = document.getElementById("inspection-task-result");
  const networkText = document.getElementById("inspection-network-text");
  const lastCaptureText = document.getElementById("inspection-last-capture-text");

  const obsLat = document.getElementById("observation-lat");
  const obsLon = document.getElementById("observation-lon");
  const obsAlt = document.getElementById("observation-alt");
  const obsItemCode = document.getElementById("observation-item-code");
  const obsSeverity = document.getElementById("observation-severity");
  const obsNote = document.getElementById("observation-note");
  const obsCreateBtn = document.getElementById("observation-create-btn");
  const obsRetryBtn = document.getElementById("observation-retry-btn");
  const obsRetryHint = document.getElementById("observation-retry-hint");

  const defectObservationId = document.getElementById("defect-observation-id");
  const defectCreateBtn = document.getElementById("defect-create-btn");
  const fieldMediaNote = document.getElementById("field-media-note");
  const fieldMediaPhotoUrl = document.getElementById("field-media-photo-url");
  const fieldMediaSaveBtn = document.getElementById("field-media-save-btn");
  const fieldMediaResult = document.getElementById("field-media-result");
  let lastObservationPayload = null;

  function showResult(type, message) {
    if (!resultNode) {
      return;
    }
    if (ui && typeof ui.setResult === "function") {
      ui.setResult(resultNode, type, message);
      return;
    }
    resultNode.textContent = message;
  }

  function updateNetworkState() {
    if (!networkText) {
      return;
    }
    if (navigator.onLine) {
      networkText.textContent = "在线，可直接提交现场记录。";
      return;
    }
    networkText.textContent = "当前网络不稳定，建议优先记录后使用“重试上一笔”。";
  }

  function updateRetryHint(text) {
    if (obsRetryHint) {
      obsRetryHint.textContent = text;
    }
  }

  function updateLastCapture(text) {
    if (lastCaptureText) {
      lastCaptureText.textContent = text;
    }
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

  observations.forEach((item) => {
    const marker = L.circleMarker([item.position_lat, item.position_lon], {
      radius: 7,
      color: item.severity >= 3 ? "#bc4749" : "#2d6a4f",
      weight: 2,
      fillOpacity: 0.9,
    }).addTo(map);
    marker.bindPopup(
      "<strong>" + item.item_code + "</strong><br/>" +
      "严重级别: " + item.severity + "<br/>" +
      "说明: " + (item.note || "")
    );
  });

  updateNetworkState();
  window.addEventListener("online", updateNetworkState);
  window.addEventListener("offline", updateNetworkState);
  updateLastCapture("尚未提交新的观察记录。");
  updateRetryHint("当前没有待重试的观察记录。");

  if (!exportBtn || !exportResult) {
    return;
  }

  map.on("click", (event) => {
    if (obsLat) {
      obsLat.value = event.latlng.lat.toFixed(6);
    }
    if (obsLon) {
      obsLon.value = event.latlng.lng.toFixed(6);
    }
  });

  exportBtn.addEventListener("click", async () => {
    const exportTaskId = exportBtn.getAttribute("data-task-id");
    if (!exportTaskId || !token) {
      exportResult.textContent = "缺少任务标识或登录令牌。";
      return;
    }
    const resp = await fetch(`/api/inspection/tasks/${exportTaskId}/export?format=html`, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "X-CSRF-Token": csrfToken,
      },
    });
    try {
      const body = await resp.json();
      if (!resp.ok) {
        exportResult.textContent = body.detail || "导出失败，请稍后重试。";
        return;
      }
      const fileResp = await fetch(`/api/inspection/exports/${body.id}`, {
        headers: {
          Authorization: `Bearer ${token}`,
          "X-CSRF-Token": csrfToken,
        },
      });
      if (!fileResp.ok) {
        exportResult.textContent = "导出任务已创建，但获取文件失败。";
        return;
      }
      const blob = await fileResp.blob();
      const url = URL.createObjectURL(blob);
      window.open(url, "_blank", "noopener,noreferrer");
      exportResult.textContent = `导出文件已就绪：${body.id}`;
    } catch (err) {
      exportResult.textContent = toMessage(err);
    }
  });

  if (canInspectionWrite && obsCreateBtn && taskId) {
    async function submitObservation(payload, triggerBtn, isRetry) {
      await withBusyButton(triggerBtn, isRetry ? "重试中..." : "创建中...", async () => {
        try {
          const row = await post(`/api/inspection/tasks/${taskId}/observations`, payload);
          lastObservationPayload = payload;
          if (defectObservationId) {
            defectObservationId.value = row.id;
          }
          updateLastCapture(`最近记录 ${row.id} 已提交，可直接继续创建缺陷。`);
          updateRetryHint("如网络波动，可继续用当前内容再次重试提交。");
          showResult("success", `已创建观察记录：${row.id}`);
        } catch (err) {
          lastObservationPayload = payload;
          updateRetryHint("上一笔观察记录已保留，可在网络恢复后点击“重试上一笔”。");
          showResult("danger", toMessage(err));
        }
      });
    }

    obsCreateBtn.addEventListener("click", async () => {
      const lat = Number(obsLat && obsLat.value ? obsLat.value : "");
      const lon = Number(obsLon && obsLon.value ? obsLon.value : "");
      const alt = Number(obsAlt && obsAlt.value ? obsAlt.value : "50");
      const itemCode = (obsItemCode && obsItemCode.value ? obsItemCode.value : "").trim();
      const severity = Number.parseInt(String(obsSeverity && obsSeverity.value ? obsSeverity.value : "1"), 10) || 1;
      const note = (obsNote && obsNote.value ? obsNote.value : "").trim();

      if (!Number.isFinite(lat) || !Number.isFinite(lon) || !itemCode) {
        showResult("warn", "请填写经度、纬度和检查项编码。");
        return;
      }
      await submitObservation(
        {
          position_lat: lat,
          position_lon: lon,
          alt_m: Number.isFinite(alt) ? alt : 50,
          item_code: itemCode,
          severity,
          note,
        },
        obsCreateBtn,
        false,
      );
    });

    if (obsRetryBtn) {
      obsRetryBtn.addEventListener("click", async () => {
        if (!lastObservationPayload) {
          showResult("warn", "当前没有可重试的观察记录。");
          return;
        }
        await submitObservation(lastObservationPayload, obsRetryBtn, true);
      });
    }
  }

  async function createDefectFromObservation(observationId, triggerBtn) {
    const id = String(observationId || "").trim();
    if (!id) {
      showResult("warn", "请先选择观察记录。");
      return;
    }
    await withBusyButton(triggerBtn, "创建中...", async () => {
      try {
        const row = await post(`/api/defects/from-observation/${id}`, {});
        showResult("success", `已创建缺陷：${row.id}`);
      } catch (err) {
        showResult("danger", toMessage(err));
      }
    });
  }

  if (canDefectWrite && defectCreateBtn) {
    defectCreateBtn.addEventListener("click", async () => {
      await createDefectFromObservation(defectObservationId && defectObservationId.value, defectCreateBtn);
    });

    document.querySelectorAll(".js-create-defect-from-observation").forEach((button) => {
      button.addEventListener("click", async () => {
        const observationId = button.getAttribute("data-observation-id");
        if (defectObservationId && observationId) {
          defectObservationId.value = observationId;
        }
        await createDefectFromObservation(observationId, button);
      });
    });
  }

  if (fieldMediaSaveBtn && fieldMediaResult) {
    fieldMediaSaveBtn.addEventListener("click", () => {
      const note = (fieldMediaNote && fieldMediaNote.value ? fieldMediaNote.value : "").trim();
      const photo = (fieldMediaPhotoUrl && fieldMediaPhotoUrl.value ? fieldMediaPhotoUrl.value : "").trim();
      if (!note && !photo) {
        fieldMediaResult.textContent = "请至少填写现场备注或照片地址。";
        return;
      }
      fieldMediaResult.textContent = `已记录现场补充：${note || "无备注"}${photo ? ` / 照片：${photo}` : ""}`;
      showResult("success", "现场备注已暂存，可继续执行回传或缺陷上报。");
    });
  }
})();
