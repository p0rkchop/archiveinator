/* archiveinator — archive form submission and WebSocket progress */

(function () {
  const form = document.getElementById("archive-form");
  if (!form) return;

  const progressArea = document.getElementById("progress-area");
  const progressFill = document.getElementById("progress-fill");
  const progressMessages = document.getElementById("progress-messages");
  const resultArea = document.getElementById("result-area");
  const profileIndicator = document.getElementById("profile-indicator");

  form.addEventListener("submit", async function (e) {
    e.preventDefault();
    const urlInput = form.querySelector('input[name="url"]');
    const url = urlInput.value.trim();
    if (!url) return;

    // Show progress area, hide old results
    progressArea.style.display = "block";
    resultArea.innerHTML = "";
    progressMessages.innerHTML = "";
    progressFill.style.width = "0%";
    addMessage("info", "Submitting archive request...");

    try {
      // Submit the job
      const resp = await fetch("/archive", {
        method: "POST",
        headers: { "Content-Type": "application/x-www-form-urlencoded" },
        body: "url=" + encodeURIComponent(url),
      });

      if (!resp.ok) {
        const text = await resp.text();
        addMessage("error", "Failed to submit: " + text);
        return;
      }

      const data = await resp.json();
      const jobId = data.job_id;

      addMessage("success", `Job #${jobId} created. Connecting to progress stream...`);

      // Open WebSocket for progress
      const protocol = window.location.protocol === "https:" ? "wss:" : "ws:";
      const ws = new WebSocket(
        `${protocol}//${window.location.host}/archive/${jobId}/ws`
      );

      ws.onmessage = function (event) {
        const msg = JSON.parse(event.data);

        switch (msg.type) {
          case "step":
            addMessage("step", `[${msg.step}] ${msg.message}`);
            break;
          case "bypass":
            const result = msg.result === "success" ? "✓" : "✗";
            addMessage(
              msg.result === "success" ? "success" : "step",
              `${result} Bypass "${msg.strategy}": ${msg.result}`
            );
            break;
          case "complete":
            addMessage("success", `✓ Complete in ${msg.duration_seconds}s`);
            progressFill.style.width = "100%";
            ws.close();

            // Show result card
            resultArea.innerHTML = `
              <div class="result-card">
                <h2>${escHtml(msg.title || "Untitled")}</h2>
                <p class="meta">
                  <span>⏱ ${msg.duration_seconds}s</span>
                  <span>📄 <a href="/download/${msg.job_id}" target="_blank">Download HTML</a></span>
                  <span><a href="/download/${msg.job_id}?view=1" target="_blank">View preview</a></span>
                </p>
              </div>`;
            break;
          case "error":
            addMessage("error", `✗ ${msg.message}`);
            break;
        }
      };

      ws.onerror = function () {
        addMessage("error", "WebSocket connection error");
      };
    } catch (err) {
      addMessage("error", "Error: " + err.message);
    }
  });

  function addMessage(type, text) {
    const div = document.createElement("div");
    div.className = "msg-" + type;
    div.textContent = text;
    progressMessages.appendChild(div);
    progressMessages.scrollTop = progressMessages.scrollHeight;

    // Update progress bar based on message count
    const count = progressMessages.children.length;
    const pct = Math.min(count * 5, 95);
    progressFill.style.width = pct + "%";
  }

  function escHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
})();
