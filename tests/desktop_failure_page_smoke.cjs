const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const { statusHtml } = require(path.join(root, "desktop", "status-page.cjs"));

const loadingHtml = statusHtml(["Preparing services..."]);
assert.doesNotMatch(loadingHtml, /id="close-client"/);

const failureHtml = statusHtml(["Failed backend: <unsafe>"], {
  failed: true,
  detail: 'Port 8000 says "no" <script>alert(1)</script>',
});
assert.match(failureHtml, /id="close-client"/);
assert.match(failureHtml, /window\.desktopShell\.closeClient\(\)/);
assert.match(failureHtml, /正在关闭客户端/);
assert.doesNotMatch(failureHtml, /<unsafe>/);
assert.doesNotMatch(failureHtml, /<script>alert\(1\)<\/script>/);
assert.match(failureHtml, /&lt;script&gt;alert\(1\)&lt;\/script&gt;/);

const mainSource = fs.readFileSync(path.join(root, "desktop", "main.cjs"), "utf8");
const preloadSource = fs.readFileSync(path.join(root, "desktop", "preload.cjs"), "utf8");
assert.doesNotMatch(mainSource, /showErrorBox/);
assert.match(mainSource, /ipcMain\.on\("desktop-close"/);
assert.match(mainSource, /await stopStartedServices\(\);\s*app\.quit\(\);/);
assert.match(preloadSource, /closeClient:\s*\(\)\s*=>\s*ipcRenderer\.send\("desktop-close"\)/);

console.log("DESKTOP_FAILURE_PAGE_SMOKE_OK");
