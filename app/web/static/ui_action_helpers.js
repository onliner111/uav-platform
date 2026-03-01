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
    button.textContent = pendingLabel || "Processing...";
    try {
      await action();
    } finally {
      button.disabled = false;
      button.textContent = originalText;
    }
  }

  function toMessage(error) {
    if (!error) {
      return "request failed";
    }
    if (typeof error === "string") {
      return error;
    }
    if (error instanceof Error) {
      return error.message || "request failed";
    }
    return String(error);
  }

  window.UIActionUtils = {
    setResult,
    toMessage,
    withBusyButton,
  };
})();
