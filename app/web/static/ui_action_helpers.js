(function () {
  function setResult(node, type, message) {
    if (!node) {
      return;
    }
    node.classList.remove("success", "warn", "danger");
    if (type) {
      node.classList.add(type);
    }
    node.textContent = message || "";
  }

  async function withBusyButton(button, pendingLabel, action) {
    if (!button) {
      await action();
      return;
    }
    const originalText = button.textContent || "";
    button.disabled = true;
    button.textContent = pendingLabel || "处理中...";
    try {
      await action();
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  function toMessage(error) {
    if (!error) {
      return "请求失败，请稍后重试。";
    }
    if (typeof error === "string") {
      return error;
    }
    if (error instanceof Error) {
      return error.message || "请求失败，请稍后重试。";
    }
    return String(error);
  }

  window.UIActionUtils = {
    setResult,
    toMessage,
    withBusyButton,
  };
})();
