function escapeHtml(value) {
  return String(value).replace(/[&<>"']/g, (character) => ({
    "&": "&amp;",
    "<": "&lt;",
    ">": "&gt;",
    '"': "&quot;",
    "'": "&#39;",
  })[character]);
}

function statusHtml(lines, { failed = false, detail = "" } = {}) {
  const escapedLines = lines.map(escapeHtml);
  const failurePanel = failed
    ? `
      <section class="failure" aria-labelledby="failure-title">
        <h2 id="failure-title">启动失败</h2>
        <p>${escapeHtml(detail || "本地服务未能正常启动。")}</p>
        <button id="close-client" type="button">关闭客户端</button>
        <p id="close-status" class="close-status" aria-live="polite"></p>
      </section>`
    : "";
  const failureScript = failed
    ? `
  <script>
    (() => {
      const button = document.getElementById("close-client");
      const status = document.getElementById("close-status");
      button.addEventListener("click", () => {
        button.disabled = true;
        status.textContent = "正在关闭客户端...";
        if (window.desktopShell && typeof window.desktopShell.closeClient === "function") {
          window.desktopShell.closeClient();
          return;
        }
        window.close();
      });
    })();
  </script>`
    : "";

  return `<!doctype html>
<html lang="zh-CN">
<head>
  <meta charset="utf-8" />
  <meta http-equiv="Content-Security-Policy" content="default-src 'none'; style-src 'unsafe-inline'; script-src 'unsafe-inline'" />
  <title>MemWeave Desktop</title>
  <style>
    body { margin: 0; font-family: "Segoe UI", Arial, sans-serif; background: #f8fafc; color: #172033; }
    main { max-width: 760px; margin: 56px auto; padding: 0 24px; }
    h1 { font-size: 24px; margin: 0 0 12px; }
    h2 { font-size: 18px; margin: 0 0 8px; }
    p { color: #526071; line-height: 1.6; }
    pre { white-space: pre-wrap; background: #ffffff; border: 1px solid #d9e2ec; border-radius: 8px; padding: 16px; line-height: 1.55; }
    .failure { margin-top: 20px; border-top: 1px solid #d9e2ec; padding-top: 20px; }
    button { border: 0; border-radius: 6px; padding: 10px 16px; background: #0f766e; color: #ffffff; font: inherit; cursor: pointer; }
    button:hover { background: #115e59; }
    button:focus-visible { outline: 3px solid #99f6e4; outline-offset: 2px; }
    button:disabled { cursor: wait; opacity: 0.65; }
    .close-status { min-height: 24px; margin-bottom: 0; font-size: 13px; }
  </style>
</head>
<body>
  <main>
    <h1>MemWeave（忆织）</h1>
    <p>${failed ? "本地服务启动失败。请查看下面的错误并关闭客户端。" : "正在启动本地服务。这个窗口会在前端就绪后自动进入应用。"}</p>
    <pre>${escapedLines.join("\n")}</pre>${failurePanel}
  </main>${failureScript}
</body>
</html>`;
}

module.exports = { escapeHtml, statusHtml };
