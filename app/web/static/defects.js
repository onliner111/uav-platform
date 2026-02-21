(function () {
  const token = window.__TOKEN;
  const defectIdInput = document.getElementById("defect-id");
  const assignedToInput = document.getElementById("assigned-to");
  const statusSelect = document.getElementById("next-status");
  const resultNode = document.getElementById("defect-result");
  const assignBtn = document.getElementById("assign-btn");
  const statusBtn = document.getElementById("status-btn");

  async function callApi(path, payload) {
    const resp = await fetch(path, {
      method: "POST",
      headers: {
        Authorization: `Bearer ${token}`,
        "Content-Type": "application/json",
      },
      body: JSON.stringify(payload),
    });
    const body = await resp.json();
    if (!resp.ok) {
      throw new Error(body.detail || "Request failed");
    }
    return body;
  }

  assignBtn.addEventListener("click", async () => {
    const defectId = defectIdInput.value.trim();
    const assignedTo = assignedToInput.value.trim();
    if (!defectId || !assignedTo) {
      resultNode.textContent = "Defect ID and assignee are required.";
      return;
    }
    try {
      const body = await callApi(`/api/defects/${defectId}/assign`, { assigned_to: assignedTo });
      resultNode.textContent = `Assigned. Current status: ${body.status}`;
    } catch (err) {
      resultNode.textContent = err.message;
    }
  });

  statusBtn.addEventListener("click", async () => {
    const defectId = defectIdInput.value.trim();
    const nextStatus = statusSelect.value;
    if (!defectId || !nextStatus) {
      resultNode.textContent = "Defect ID and status are required.";
      return;
    }
    try {
      const body = await callApi(`/api/defects/${defectId}/status`, { status: nextStatus });
      resultNode.textContent = `Status updated: ${body.status}`;
    } catch (err) {
      resultNode.textContent = err.message;
    }
  });
})();
