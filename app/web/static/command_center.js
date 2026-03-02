(function () {
  const auth = window.__CONSOLE_AUTH || {};
  const token = window.__TOKEN || auth.token;
  if (!token) {
    return;
  }

  const map = L.map("live-map").setView([30.5928, 114.3055], 11);
  L.tileLayer("https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png", {
    attribution: "&copy; OpenStreetMap contributors",
  }).addTo(map);

  const modeConfig = {
    ops: {
      title: "当前模式：值守模式",
      desc: "优先关注实时态势、活跃告警和当前高风险对象，适合日常值班与联动处置。",
      audience: "值守席位",
      priority: "实时告警与高风险对象",
      window: "近 15 分钟动态",
      rhythm: [
        "优先确认实时告警是否形成积压。",
        "再查看任务和现场事件是否存在阻塞。",
        "最后复核成果与空域限制是否影响后续排班。",
      ],
    },
    executive: {
      title: "当前模式：领导模式",
      desc: "压缩细节，只保留全局态势、重点风险和关键结果，适合汇报和快速问询。",
      audience: "领导与汇报对象",
      priority: "关键风险、任务进展、结果闭环",
      window: "近 1 小时概览",
      rhythm: [
        "先看全局告警和重点任务进展。",
        "再确认异常区域是否持续扩大。",
        "最后查看结果输出和闭环状态。",
      ],
    },
    demo: {
      title: "当前模式：演示模式",
      desc: "突出地图对象和联动能力，适合对外展示平台的统一态势与跨模块协同。",
      audience: "客户演示与外部访客",
      priority: "多图层联动与跨页面跳转",
      window: "典型场景回放",
      rhythm: [
        "优先展示多图层联动能力。",
        "再点击典型对象说明进入路径。",
        "最后用轨迹回放和视频槽位补充演示。",
      ],
    },
  };

  const layerConfig = {
    resources: { id: "layer-resources", group: L.layerGroup().addTo(map) },
    tasks: { id: "layer-tasks", group: L.layerGroup().addTo(map) },
    airspace: { id: "layer-airspace", group: L.layerGroup().addTo(map) },
    alerts: { id: "layer-alerts", group: L.layerGroup().addTo(map) },
    events: { id: "layer-events", group: L.layerGroup() },
    outcomes: { id: "layer-outcomes", group: L.layerGroup().addTo(map) },
  };

  const replayState = {
    points: [],
    cursor: 0,
    timer: null,
    marker: null,
    line: null,
  };

  const replayDroneSelect = document.getElementById("replay-drone");
  const replayStepInput = document.getElementById("replay-step");
  const replayStatusNode = document.getElementById("replay-status");
  const alertListNode = document.getElementById("alert-list");
  const alertCardNode = document.getElementById("card-alert");
  const videoSlotsNode = document.getElementById("video-slots");
  const modeTitleNode = document.getElementById("command-mode-title");
  const modeDescNode = document.getElementById("command-mode-desc");
  const modeAudienceNode = document.getElementById("command-mode-audience");
  const modePriorityNode = document.getElementById("command-mode-priority");
  const modeWindowNode = document.getElementById("command-mode-window");
  const rhythmListNode = document.getElementById("command-rhythm-list");
  const focusEmptyNode = document.getElementById("command-focus-empty");
  const focusCardNode = document.getElementById("command-focus-card");
  const focusTitleNode = document.getElementById("command-focus-title");
  const focusStatusNode = document.getElementById("command-focus-status");
  const focusMetaNode = document.getElementById("command-focus-meta");
  const focusExplainNode = document.getElementById("command-focus-explain");
  const focusLinkNode = document.getElementById("command-focus-link");
  const focusSecondaryNode = document.getElementById("command-focus-secondary");
  const timelineNode = document.getElementById("command-timeline");

  let hasFittedBounds = false;
  let currentMode = "ops";
  const markerRegistry = new Map();

  function authHeaders() {
    return {
      Authorization: `Bearer ${token}`,
    };
  }

  function setStat(id, value) {
    const node = document.getElementById(id);
    if (node) {
      node.textContent = String(value);
    }
  }

  function setReplayStatus(text) {
    if (replayStatusNode) {
      replayStatusNode.textContent = text;
    }
  }

  function iconStyleFor(item) {
    if (item.category === "alert") {
      return { radius: 8, color: "#bc4749", fillColor: "#bc4749", fillOpacity: 0.95 };
    }
    if (item.category === "airspace") {
      return { radius: 7, color: "#6a4c93", fillColor: "#cdb4db", fillOpacity: 0.9 };
    }
    if (item.category === "outcome") {
      return { radius: 6, color: "#1d3557", fillColor: "#a8dadc", fillOpacity: 0.9 };
    }
    if (item.category === "event") {
      return { radius: 5, color: "#495057", fillColor: "#adb5bd", fillOpacity: 0.8 };
    }
    if (item.category === "mission" || item.category === "inspection_task" || item.category === "incident") {
      return { radius: 6, color: "#7f5539", fillColor: "#ddbea9", fillOpacity: 0.85 };
    }
    return { radius: 6, color: "#2d6a4f", fillColor: "#95d5b2", fillOpacity: 0.9 };
  }

  function localizedCategory(category) {
    const mapping = {
      drone: "设备",
      asset: "资产",
      mission: "任务",
      inspection_task: "巡检任务",
      incident: "事件单",
      airspace: "空域规则",
      alert: "告警",
      event: "事件流水",
      outcome: "成果点位",
    };
    return mapping[category] || "对象";
  }

  function statusTone(statusText) {
    const value = String(statusText || "").toUpperCase();
    if (!value || value === "-") {
      return "muted";
    }
    if (value.includes("OPEN") || value.includes("P1") || value.includes("BLOCK") || value.includes("DENY")) {
      return "danger";
    }
    if (value.includes("ACK") || value.includes("RUN") || value.includes("PENDING")) {
      return "warn";
    }
    if (value.includes("VERIFIED") || value.includes("ONLINE") || value.includes("SUCCEEDED") || value.includes("启用")) {
      return "success";
    }
    return "info";
  }

  function popupHtml(item) {
    const detail = item.detail || {};
    const lines = [
      `<strong>${item.label || item.id}</strong>`,
      `类型：${localizedCategory(item.category)}`,
      item.status ? `状态：${statusDisplayText(item.status)}` : null,
      detail.alert_type ? `告警类型：${detail.alert_type}` : null,
      detail.severity ? `严重级别：${detail.severity}` : null,
      detail.drone_id ? `关联设备：${detail.drone_id}` : null,
      detail.policy_effect ? `规则效果：${detail.policy_effect}` : null,
      detail.outcome_type ? `成果类型：${detail.outcome_type}` : null,
    ].filter(Boolean);
    return lines.join("<br/>");
  }

  function statusDisplayText(statusText) {
    const value = String(statusText || "").toUpperCase();
    const mapping = {
      ONLINE: "在线",
      UNKNOWN: "待确认",
      OPEN: "待处理",
      ACKED: "处理中",
      CLOSED: "已关闭",
      RUNNING: "执行中",
      PENDING: "待处理",
      VERIFIED: "已核验",
      SUCCEEDED: "已完成",
      FAILED: "失败",
      NEW: "新建",
      DRAFT: "草稿",
    };
    return mapping[value] || statusText || "待关注";
  }

  function actionTargetsFor(item) {
    const mapping = {
      drone: [
        { href: "/ui/assets", label: "处理资产状态" },
        { href: "/ui/task-center", label: "查看关联任务" },
      ],
      asset: [
        { href: "/ui/assets", label: "处理资产状态" },
        { href: "/ui/task-center", label: "查看关联任务" },
      ],
      mission: [
        { href: "/ui/task-center", label: "进入任务中心" },
        { href: "/ui/reports", label: "查看执行结果" },
      ],
      inspection_task: [
        { href: "/ui/inspection", label: "进入巡检任务" },
        { href: "/ui/defects", label: "查看缺陷闭环" },
      ],
      incident: [
        { href: "/ui/emergency", label: "进入应急处置" },
        { href: "/ui/task-center", label: "查看关联任务" },
      ],
      airspace: [
        { href: "/ui/compliance", label: "进入合规工作台" },
        { href: "/ui/task-center", label: "查看受影响任务" },
      ],
      alert: [
        { href: "/ui/alerts", label: "进入告警中心" },
        { href: "/ui/assets", label: "查看关联设备" },
      ],
      event: [
        { href: "/ui/command-center", label: "保持当前页面" },
        { href: "/ui/alerts", label: "进入告警中心" },
      ],
      outcome: [
        { href: "/ui/reports", label: "进入成果工作区" },
        { href: "/ui/task-center", label: "回看关联任务" },
      ],
    };
    return mapping[item.category] || [{ href: "/ui/command-center", label: "保持当前页面" }];
  }

  function actionTargetFor(item) {
    return actionTargetsFor(item)[0];
  }

  function statusExplanationFor(item) {
    const detail = item.detail || {};
    const status = String(item.status || "").toUpperCase();
    if (item.category === "alert") {
      return status === "ACKED"
        ? "该告警已被接手，建议继续跟踪处置进度并确认是否需要升级。"
        : "该告警仍处于待处理链路，建议优先确认来源设备、严重级别与责任人。";
    }
    if (item.category === "airspace") {
      return detail.policy_effect === "DENY"
        ? "该空域规则会直接限制任务进入，建议先核对范围和策略层级。"
        : "该空域规则当前处于提示或允许模式，可在合规工作台继续核验。";
    }
    if (item.category === "mission" || item.category === "inspection_task") {
      return status.includes("RUN")
        ? "该任务正在执行，建议继续查看进度、阻塞项和结果回传。"
        : "该任务尚未闭环，建议进入任务工作区继续处理当前状态。";
    }
    if (item.category === "incident") {
      return "该事件单属于现场处置对象，建议确认位置、等级和联动任务状态。";
    }
    if (item.category === "outcome") {
      return "该成果已形成点位记录，建议进入成果工作区完成复核、导出或闭环。";
    }
    if (item.category === "event") {
      return "这是系统事件流水，可继续留在一张图联看，或跳转到关联业务页跟进。";
    }
    return "该对象已进入地图焦点，可从下方快捷动作继续进入相关工作区。";
  }

  function focusMetaText(item) {
    const detail = item.detail || {};
    const parts = [
      `类型：${localizedCategory(item.category)}`,
      item.status ? `状态：${statusDisplayText(item.status)}` : null,
      detail.drone_id ? `设备：${detail.drone_id}` : null,
      detail.area_code ? `区域：${detail.area_code}` : null,
      detail.policy_effect ? `规则：${detail.policy_effect}` : null,
      detail.outcome_type ? `成果：${detail.outcome_type}` : null,
    ].filter(Boolean);
    return parts.join(" / ");
  }

  function setFocusItem(item) {
    if (
      !focusCardNode ||
      !focusTitleNode ||
      !focusStatusNode ||
      !focusMetaNode ||
      !focusLinkNode ||
      !focusExplainNode
    ) {
      return;
    }
    if (focusEmptyNode) {
      focusEmptyNode.hidden = true;
    }
    const targets = actionTargetsFor(item);
    const target = targets[0];
    const secondary = targets[1] || null;
    focusCardNode.hidden = false;
    focusTitleNode.textContent = item.label || item.id;
    focusStatusNode.textContent = statusDisplayText(item.status);
    focusStatusNode.className = `status-pill ${statusTone(item.status)}`;
    focusMetaNode.textContent = focusMetaText(item);
    focusExplainNode.textContent = statusExplanationFor(item);
    focusLinkNode.href = target.href;
    focusLinkNode.textContent = target.label;
    if (focusSecondaryNode) {
      if (secondary) {
        focusSecondaryNode.hidden = false;
        focusSecondaryNode.href = secondary.href;
        focusSecondaryNode.textContent = secondary.label;
      } else {
        focusSecondaryNode.hidden = true;
        focusSecondaryNode.href = "/ui/command-center";
        focusSecondaryNode.textContent = "保持当前页面";
      }
    }
  }

  function clearLayerRegistry(layerName) {
    Array.from(markerRegistry.keys()).forEach((key) => {
      if (key.startsWith(`${layerName}:`)) {
        markerRegistry.delete(key);
      }
    });
  }

  function focusMapItem(item) {
    if (!item) {
      return;
    }
    const layerName = item._layerName;
    if (layerName && layerConfig[layerName]) {
      const toggle = document.getElementById(layerConfig[layerName].id);
      if (toggle && !toggle.checked) {
        toggle.checked = true;
        applyLayerVisibility();
      }
    }
    setFocusItem(item);
    const marker = item._commandKey ? markerRegistry.get(item._commandKey) : null;
    if (marker && typeof marker.getLatLng === "function") {
      map.panTo(marker.getLatLng(), { animate: true });
      if (typeof marker.openPopup === "function") {
        marker.openPopup();
      }
      return;
    }
    if (item.point && typeof item.point.lat === "number" && typeof item.point.lon === "number") {
      map.panTo([item.point.lat, item.point.lon], { animate: true });
    }
  }

  function applyMode(modeKey) {
    const nextMode = modeConfig[modeKey] ? modeKey : "ops";
    currentMode = nextMode;
    const config = modeConfig[nextMode];
    document.querySelectorAll("[data-command-mode]").forEach((button) => {
      button.classList.toggle("active", button.getAttribute("data-command-mode") === nextMode);
    });
    if (modeTitleNode) {
      modeTitleNode.textContent = config.title;
    }
    if (modeDescNode) {
      modeDescNode.textContent = config.desc;
    }
    if (modeAudienceNode) {
      modeAudienceNode.textContent = config.audience;
    }
    if (modePriorityNode) {
      modePriorityNode.textContent = config.priority;
    }
    if (modeWindowNode) {
      modeWindowNode.textContent = config.window;
    }
    if (rhythmListNode) {
      rhythmListNode.innerHTML = "";
      config.rhythm.forEach((text) => {
        const item = document.createElement("li");
        item.className = "hint-list-item";
        item.textContent = text;
        rhythmListNode.appendChild(item);
      });
    }
    const shell = document.querySelector(".command-mode-shell");
    if (shell) {
      shell.setAttribute("data-command-mode", nextMode);
    }
  }

  function applyLayerVisibility() {
    Object.keys(layerConfig).forEach((key) => {
      const cfg = layerConfig[key];
      const toggle = document.getElementById(cfg.id);
      if (!toggle) {
        return;
      }
      if (toggle.checked) {
        cfg.group.addTo(map);
      } else {
        map.removeLayer(cfg.group);
      }
    });
  }

  function parseTimelineDate(rawValue) {
    if (!rawValue) {
      return null;
    }
    const parsed = rawValue instanceof Date ? rawValue : new Date(rawValue);
    return Number.isNaN(parsed.valueOf()) ? null : parsed;
  }

  function timelineStampFor(item) {
    const detail = item.detail || {};
    const direct = parseTimelineDate(
      detail.last_seen_at || detail.updated_at || detail.created_at || detail.ts,
    );
    if (direct) {
      return direct;
    }
    return parseTimelineDate(item.point && item.point.ts ? item.point.ts : null);
  }

  function formatTimelineTime(value) {
    const parsed = parseTimelineDate(value);
    if (!parsed) {
      return "时间待补充";
    }
    return parsed.toLocaleString("zh-CN", { hour12: false });
  }

  function timelineTitleFor(item) {
    if (item.category === "event") {
      if (String(item.label || "").startsWith("alert.")) {
        return "告警事件";
      }
      if (String(item.label || "").startsWith("incident.")) {
        return "事件单变更";
      }
      if (String(item.label || "").startsWith("mission.")) {
        return "任务状态变更";
      }
      return "事件流水";
    }
    return item.label || item.id;
  }

  function timelineMetaText(item) {
    const detail = item.detail || {};
    const parts = [localizedCategory(item.category)];
    if (item.status) {
      parts.push(statusDisplayText(item.status));
    }
    if (item.category === "event" && item.label) {
      parts.push(item.label);
    } else if (detail.alert_type) {
      parts.push(detail.alert_type);
    } else if (detail.outcome_type) {
      parts.push(detail.outcome_type);
    } else if (detail.policy_effect) {
      parts.push(detail.policy_effect);
    } else if (detail.level) {
      parts.push(`等级 ${detail.level}`);
    }
    return parts.join(" / ");
  }

  function renderTimeline(layerByName) {
    if (!timelineNode) {
      return;
    }
    const ordered = [];
    ["alerts", "events", "outcomes", "tasks"].forEach((layerName) => {
      const rows = (layerByName[layerName] && layerByName[layerName].items) || [];
      rows.forEach((item) => {
        const stamp = timelineStampFor(item);
        if (!stamp) {
          return;
        }
        ordered.push({ item, stamp });
      });
    });
    ordered.sort((left, right) => right.stamp.valueOf() - left.stamp.valueOf());
    timelineNode.innerHTML = "";
    if (ordered.length === 0) {
      timelineNode.innerHTML = '<li class="hint">当前没有可展示的时间轴记录。</li>';
      return;
    }
    ordered.slice(0, 10).forEach((entry) => {
      const item = entry.item;
      const li = document.createElement("li");
      const button = document.createElement("button");
      const top = document.createElement("div");
      const main = document.createElement("span");
      const time = document.createElement("span");
      const meta = document.createElement("div");
      button.type = "button";
      button.className = "command-timeline-item";
      top.className = "command-timeline-top";
      main.className = "command-timeline-main";
      time.className = "command-timeline-time";
      meta.className = "command-timeline-meta";
      main.textContent = timelineTitleFor(item);
      time.textContent = formatTimelineTime(entry.stamp);
      meta.textContent = timelineMetaText(item);
      top.appendChild(main);
      top.appendChild(time);
      button.appendChild(top);
      button.appendChild(meta);
      button.addEventListener("click", () => focusMapItem(item));
      li.appendChild(button);
      timelineNode.appendChild(li);
    });
  }

  function clearReplay() {
    if (replayState.timer) {
      clearInterval(replayState.timer);
      replayState.timer = null;
    }
    if (replayState.marker) {
      map.removeLayer(replayState.marker);
      replayState.marker = null;
    }
    if (replayState.line) {
      map.removeLayer(replayState.line);
      replayState.line = null;
    }
    replayState.points = [];
    replayState.cursor = 0;
  }

  function renderLayerItems(layerName, items, allBounds) {
    const cfg = layerConfig[layerName];
    if (!cfg) {
      return;
    }
    clearLayerRegistry(layerName);
    cfg.group.clearLayers();
    items.forEach((item) => {
      item._layerName = layerName;
      item._commandKey = `${layerName}:${item.id}`;
      if (!item.point || typeof item.point.lat !== "number" || typeof item.point.lon !== "number") {
        return;
      }
      const style = iconStyleFor(item);
      const marker = L.circleMarker([item.point.lat, item.point.lon], style);
      marker.bindPopup(popupHtml(item));
      marker.on("click", () => focusMapItem(item));
      marker.addTo(cfg.group);
      markerRegistry.set(item._commandKey, marker);
      allBounds.push([item.point.lat, item.point.lon]);
    });
  }

  function updateReplayDroneOptions(resourceItems) {
    if (!replayDroneSelect) {
      return;
    }
    const current = replayDroneSelect.value;
    const drones = resourceItems.filter((item) => item.category === "drone");
    replayDroneSelect.innerHTML = '<option value="">请选择设备</option>';
    drones.forEach((drone) => {
      const option = document.createElement("option");
      option.value = drone.id;
      option.textContent = drone.label || drone.id;
      replayDroneSelect.appendChild(option);
    });
    if (current && drones.some((item) => item.id === current)) {
      replayDroneSelect.value = current;
    }
  }

  function updateAlertList(alertItems) {
    if (!alertListNode) {
      return;
    }
    alertListNode.innerHTML = "";
    if (!Array.isArray(alertItems) || alertItems.length === 0) {
      alertListNode.innerHTML = '<li class="hint">当前没有活跃告警。</li>';
      if (alertCardNode) {
        alertCardNode.classList.remove("alert-hot");
      }
      return;
    }
    if (alertCardNode) {
      alertCardNode.classList.add("alert-hot");
    }
    alertItems.slice(0, 6).forEach((item) => {
      const detail = item.detail || {};
      const li = document.createElement("li");
      li.className = "command-alert-item";
      li.innerHTML = `${item.label || "告警"}<small>${detail.alert_type || "-"} / ${detail.severity || "-"} / ${detail.drone_id || "-"}</small>`;
      li.addEventListener("click", () => focusMapItem(item));
      alertListNode.appendChild(li);
    });
  }

  function formatLinkedTelemetry(point) {
    if (!point || typeof point.lat !== "number" || typeof point.lon !== "number") {
      return "未绑定遥测位置";
    }
    return `${point.lat.toFixed(5)}, ${point.lon.toFixed(5)}`;
  }

  function renderVideoSlots(streams, errorText = null) {
    if (!videoSlotsNode) {
      return;
    }
    videoSlotsNode.innerHTML = "";
    if (errorText) {
      videoSlotsNode.innerHTML = `<div class="hint">${errorText}</div>`;
      return;
    }
    if (!Array.isArray(streams) || streams.length === 0) {
      videoSlotsNode.innerHTML = '<div class="hint">当前没有已配置的视频流。</div>';
      return;
    }
    streams.slice(0, 6).forEach((stream) => {
      const status = String(stream.status || "STANDBY").toUpperCase();
      const protocol = String(stream.protocol || "-");
      const label = stream.label || stream.stream_key || stream.stream_id || "stream";
      const detail = stream.detail || {};
      const container = document.createElement("div");
      container.className = "command-video-slot";
      container.innerHTML = `
        <div class="command-video-title"><span>${label}</span><span class="status-pill ${statusTone(status)}">${status}</span></div>
        <div class="command-video-meta">${protocol} / ${stream.endpoint || "-"}</div>
        <div class="command-video-meta">设备：${stream.drone_id || "-"}</div>
        <div class="command-video-meta">联动位置：${formatLinkedTelemetry(stream.linked_telemetry)}</div>
        <div class="command-video-meta">启用：${stream.enabled ? "是" : "否"}${detail.last_error ? ` / 异常：${detail.last_error}` : ""}</div>
      `;
      videoSlotsNode.appendChild(container);
    });
  }

  async function fetchVideoStreams() {
    const response = await fetch("/api/integration/video-streams", {
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`视频流刷新失败：${response.status}`);
    }
    return response.json();
  }

  async function refreshVideoSlots() {
    try {
      const rows = await fetchVideoStreams();
      renderVideoSlots(rows);
    } catch (err) {
      renderVideoSlots([], String(err));
    }
  }

  function updateDashboardStats(payload) {
    const stats = payload.stats || {};
    setStat("stat-online", stats.online_devices || 0);
    setStat("stat-inspection", stats.today_inspections || 0);
    setStat("stat-defect", stats.defects_total || 0);
    setStat("stat-alert", stats.realtime_alerts || 0);
  }

  async function fetchMapOverview() {
    const response = await fetch("/api/map/overview?limit_per_layer=200", {
      headers: authHeaders(),
    });
    if (!response.ok) {
      throw new Error(`地图态势刷新失败：${response.status}`);
    }
    return response.json();
  }

  async function refreshMapLayers() {
    try {
      const overview = await fetchMapOverview();
      const layers = Array.isArray(overview.layers) ? overview.layers : [];
      const layerByName = {};
      const bounds = [];
      setStat("stat-airspace", overview.airspace_total || 0);
      setStat("stat-outcome", overview.outcomes_total || 0);
      layers.forEach((layer) => {
        layerByName[layer.layer] = layer;
        renderLayerItems(layer.layer, Array.isArray(layer.items) ? layer.items : [], bounds);
      });
      renderTimeline(layerByName);
      updateReplayDroneOptions((layerByName.resources && layerByName.resources.items) || []);
      updateAlertList((layerByName.alerts && layerByName.alerts.items) || []);
      applyLayerVisibility();
      if (!hasFittedBounds && bounds.length > 0) {
        map.fitBounds(bounds, { padding: [22, 22] });
        hasFittedBounds = true;
      }
      if ((layerByName.alerts && layerByName.alerts.items && layerByName.alerts.items.length) === 0 && focusCardNode && focusCardNode.hidden) {
        if (focusEmptyNode) {
          focusEmptyNode.hidden = false;
        }
      }
    } catch (err) {
      setReplayStatus(String(err));
    }
  }

  function startReplayAnimation(points) {
    clearReplay();
    replayState.points = points;
    replayState.cursor = 0;
    const latLngs = points.map((item) => [item.lat, item.lon]);
    replayState.line = L.polyline(latLngs, { color: "#1d3557", weight: 3, opacity: 0.85 }).addTo(map);
    replayState.marker = L.circleMarker(latLngs[0], {
      radius: 7,
      color: "#1d3557",
      fillColor: "#a8dadc",
      fillOpacity: 0.95,
    }).addTo(map);
    map.fitBounds(replayState.line.getBounds(), { padding: [18, 18] });

    replayState.timer = setInterval(() => {
      if (!replayState.marker || replayState.cursor >= replayState.points.length) {
        clearReplay();
        setReplayStatus("轨迹回放已完成。");
        return;
      }
      const point = replayState.points[replayState.cursor];
      replayState.marker.setLatLng([point.lat, point.lon]);
      replayState.cursor += 1;
      setReplayStatus(`轨迹回放进行中：${replayState.cursor}/${replayState.points.length}`);
    }, 500);
  }

  async function loadReplayAndPlay() {
    if (!replayDroneSelect || !replayDroneSelect.value) {
      setReplayStatus("请先选择设备。");
      return;
    }
    const step = Number(replayStepInput && replayStepInput.value ? replayStepInput.value : 1);
    const droneId = encodeURIComponent(replayDroneSelect.value);
    const response = await fetch(`/api/map/tracks/replay?drone_id=${droneId}&sample_step=${step}`, {
      headers: authHeaders(),
    });
    if (!response.ok) {
      setReplayStatus(`轨迹回放加载失败：${response.status}`);
      return;
    }
    const payload = await response.json();
    const points = Array.isArray(payload.points) ? payload.points : [];
    if (!points.length) {
      setReplayStatus("当前设备暂无可回放轨迹。");
      return;
    }
    startReplayAnimation(points);
  }

  Object.keys(layerConfig).forEach((key) => {
    const cfg = layerConfig[key];
    const toggle = document.getElementById(cfg.id);
    if (toggle) {
      toggle.addEventListener("change", applyLayerVisibility);
    }
  });

  document.querySelectorAll("[data-command-mode]").forEach((button) => {
    button.addEventListener("click", () => {
      applyMode(button.getAttribute("data-command-mode") || "ops");
    });
  });

  const replayPlayBtn = document.getElementById("replay-play");
  const replayStopBtn = document.getElementById("replay-stop");
  const replayRefreshBtn = document.getElementById("replay-refresh");
  if (replayPlayBtn) {
    replayPlayBtn.addEventListener("click", () => {
      loadReplayAndPlay().catch((err) => setReplayStatus(String(err)));
    });
  }
  if (replayRefreshBtn) {
    replayRefreshBtn.addEventListener("click", () => {
      refreshMapLayers();
      setReplayStatus("图层数据已刷新。");
    });
  }
  if (replayStopBtn) {
    replayStopBtn.addEventListener("click", () => {
      clearReplay();
      setReplayStatus("轨迹回放已停止。");
    });
  }

  applyMode(currentMode);
  refreshVideoSlots();
  refreshMapLayers();
  setInterval(() => {
    refreshMapLayers();
    refreshVideoSlots();
  }, 15000);

  const scheme = window.location.protocol === "https:" ? "wss" : "ws";
  const ws = new WebSocket(`${scheme}://${window.location.host}/ws/dashboard?token=${encodeURIComponent(token)}`);
  ws.onmessage = (event) => {
    try {
      updateDashboardStats(JSON.parse(event.data));
    } catch (_err) {
      // Ignore invalid payload.
    }
  };
})();
