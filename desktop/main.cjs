const { app, BrowserWindow, ipcMain, shell } = require("electron");
const { spawn } = require("node:child_process");
const fs = require("node:fs");
const http = require("node:http");
const net = require("node:net");
const os = require("node:os");
const path = require("node:path");

const { statusHtml } = require("./status-page.cjs");

const ROOT_DIR = path.resolve(__dirname, "..");
const FRONTEND_DIR = path.join(ROOT_DIR, "frontend");
const BACKEND_DIR = path.join(ROOT_DIR, "backend");
const INDEXTTS2_DIR = path.join(ROOT_DIR, "indextts2");
const INDEXTTS2_REPO_DIR = path.join(INDEXTTS2_DIR, "index-tts");
const LOG_DIR = path.join(ROOT_DIR, "logs");
const ASCII_LINK_DIR = path.join(os.tmpdir(), "memweave-indextts2-root");

const FRONTEND_PORT = Number(process.env.DESKTOP_FRONTEND_PORT || 3000);
const BACKEND_PORT = Number(process.env.DESKTOP_BACKEND_PORT || 8000);
const INDEXTTS2_PORT = Number(process.env.DESKTOP_INDEXTTS2_PORT || 7861);

const FRONTEND_URL = `http://127.0.0.1:${FRONTEND_PORT}`;
const BACKEND_HEALTH_URL = `http://127.0.0.1:${BACKEND_PORT}/health`;
const BACKEND_SELF_CHECK_URL = `http://127.0.0.1:${BACKEND_PORT}/api/v1/system/self-check`;
const INDEXTTS2_HEALTH_URL = `http://127.0.0.1:${INDEXTTS2_PORT}/health`;

const services = new Map();
let mainWindow = null;
let shuttingDown = false;
let quitting = false;

function ensureDir(dir) {
  fs.mkdirSync(dir, { recursive: true });
}

function pathExists(filePath) {
  try {
    fs.accessSync(filePath);
    return true;
  } catch {
    return false;
  }
}

function appendLog(name, line) {
  ensureDir(LOG_DIR);
  const stamp = new Date().toISOString();
  fs.appendFileSync(path.join(LOG_DIR, "desktop-shell.log"), `[${stamp}] [${name}] ${line}\n`, "utf8");
}

function request(url, timeoutMs = 2500) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      res.resume();
      res.on("end", () => resolve({ ok: res.statusCode >= 200 && res.statusCode < 400, statusCode: res.statusCode }));
    });
    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false, error: "timeout" });
    });
    req.on("error", (error) => resolve({ ok: false, error: error.message }));
  });
}

function requestText(url, timeoutMs = 3500) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => resolve({
        ok: res.statusCode >= 200 && res.statusCode < 400,
        statusCode: res.statusCode,
        body,
      }));
    });
    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false, error: "timeout" });
    });
    req.on("error", (error) => resolve({ ok: false, error: error.message }));
  });
}

function requestJson(url, timeoutMs = 2500) {
  return new Promise((resolve) => {
    const req = http.get(url, { timeout: timeoutMs }, (res) => {
      let body = "";
      res.setEncoding("utf8");
      res.on("data", (chunk) => {
        body += chunk;
      });
      res.on("end", () => {
        try {
          resolve({
            ok: res.statusCode >= 200 && res.statusCode < 400,
            statusCode: res.statusCode,
            body: body ? JSON.parse(body) : null,
          });
        } catch (error) {
          resolve({ ok: false, statusCode: res.statusCode, error: `invalid json: ${error.message}` });
        }
      });
    });
    req.on("timeout", () => {
      req.destroy();
      resolve({ ok: false, error: "timeout" });
    });
    req.on("error", (error) => resolve({ ok: false, error: error.message }));
  });
}

function backendSelfCheckReady(selfCheck) {
  if (!selfCheck.ok || !selfCheck.body) {
    return false;
  }
  const status = selfCheck.body.overall_status;
  const routes = selfCheck.body.required_routes || {};
  return status !== "blocked" && routes["/health"] === true && routes["/api/v1/raw-sources"] === true && routes["/api/v1/system/self-check"] === true;
}

function killProcessTree(name, child) {
  if (!child.pid) {
    appendLog(name, "stop skipped: child pid is missing");
    return Promise.resolve();
  }
  if (process.platform !== "win32") {
    appendLog(name, `stopping child process pid=${child.pid}`);
    try {
      child.kill("SIGTERM");
    } catch (error) {
      appendLog(name, `stop failed: ${error.message}`);
    }
    return Promise.resolve();
  }
  return new Promise((resolve) => {
    appendLog(name, `stopping child process tree pid=${child.pid}`);
    const killer = spawn("taskkill", ["/PID", String(child.pid), "/T", "/F"], {
      windowsHide: true,
      stdio: ["ignore", "ignore", "pipe"],
    });
    let stderr = "";
    killer.stderr.on("data", (chunk) => {
      stderr += chunk.toString();
    });
    killer.once("exit", (code) => {
      if (code === 0) {
        appendLog(name, "process tree stopped");
      } else {
        appendLog(name, `taskkill exited code=${code} ${stderr.trim()}`);
      }
      resolve();
    });
    killer.once("error", (error) => {
      appendLog(name, `taskkill failed: ${error.message}`);
      resolve();
    });
  });
}

function isPortOpen(port) {
  return new Promise((resolve) => {
    const socket = net.createConnection({ host: "127.0.0.1", port });
    socket.setTimeout(500);
    socket.on("connect", () => {
      socket.destroy();
      resolve(true);
    });
    socket.on("timeout", () => {
      socket.destroy();
      resolve(false);
    });
    socket.on("error", () => resolve(false));
  });
}

async function waitForHttp(url, seconds, label) {
  const deadline = Date.now() + seconds * 1000;
  let last = null;
  while (Date.now() < deadline) {
    last = await request(url, 3000);
    if (last.ok) {
      return { ok: true, statusCode: last.statusCode };
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  return { ok: false, error: `${label} did not become ready: ${last?.error || last?.statusCode || "no response"}` };
}

async function frontendReady() {
  const page = await requestText(FRONTEND_URL);
  if (!page.ok || !page.body) {
    return { ok: false, error: page.error || page.statusCode || "no HTML response" };
  }

  const assetPaths = [...page.body.matchAll(/\/_next\/static\/[^"'\s<>]+/g)]
    .map((match) => match[0].replaceAll("&amp;", "&"))
    .filter((value, index, values) => values.indexOf(value) === index)
    .slice(0, 8);
  if (assetPaths.length === 0) {
    return { ok: false, error: "HTML did not reference any Next.js static assets" };
  }

  for (const assetPath of assetPaths) {
    const asset = await request(new URL(assetPath, FRONTEND_URL).toString());
    if (!asset.ok) {
      return { ok: false, error: `static asset unavailable: ${assetPath} (${asset.error || asset.statusCode})` };
    }
  }
  return { ok: true, statusCode: page.statusCode, assetCount: assetPaths.length };
}

async function waitForFrontend(seconds) {
  const deadline = Date.now() + seconds * 1000;
  let last = null;
  while (Date.now() < deadline) {
    last = await frontendReady();
    if (last.ok) {
      return last;
    }
    await new Promise((resolve) => setTimeout(resolve, 800));
  }
  return { ok: false, error: `Frontend did not become ready: ${last?.error || "no response"}` };
}

function spawnService(name, command, args, options) {
  ensureDir(LOG_DIR);
  const out = fs.openSync(path.join(LOG_DIR, `${name}.out.log`), "a");
  const err = fs.openSync(path.join(LOG_DIR, `${name}.err.log`), "a");
  appendLog(name, `starting: ${command} ${args.join(" ")}`);
  const child = spawn(command, args, {
    cwd: options.cwd,
    env: options.env,
    windowsHide: true,
    stdio: ["ignore", out, err],
  });
  child.once("exit", (code, signal) => {
    appendLog(name, `exited code=${code ?? ""} signal=${signal ?? ""}`);
    try {
      fs.closeSync(out);
      fs.closeSync(err);
    } catch {
      // Ignore descriptor cleanup races during shutdown.
    }
  });
  child.once("error", (error) => appendLog(name, `spawn error: ${error.message}`));
  services.set(name, { child, startedByShell: true });
  return child;
}

async function ensureBackend() {
  const health = await request(BACKEND_HEALTH_URL);
  const selfCheck = await requestJson(BACKEND_SELF_CHECK_URL);
  if (health.ok && backendSelfCheckReady(selfCheck)) {
    services.set("backend", { startedByShell: false });
    return { ok: true, reused: true, url: BACKEND_SELF_CHECK_URL };
  }
  if (await isPortOpen(BACKEND_PORT)) {
    return {
      ok: false,
      service: "backend",
      error: `Port ${BACKEND_PORT} is occupied, but the current backend API is not ready.`,
    };
  }

  const env = {
    ...process.env,
    PYTHONPATH: BACKEND_DIR,
  };
  spawnService("desktop-backend", pythonPath(), ["-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", String(BACKEND_PORT)], {
    cwd: BACKEND_DIR,
    env,
  });
  const ready = await waitForHttp(BACKEND_HEALTH_URL, 45, "Backend");
  if (!ready.ok) {
    return { ok: false, service: "backend", error: ready.error };
  }
  const selfCheckReady = await requestJson(BACKEND_SELF_CHECK_URL);
  if (!backendSelfCheckReady(selfCheckReady)) {
    return { ok: false, service: "backend", error: "Backend is healthy, but system self-check did not confirm current API routes." };
  }
  return { ok: true, reused: false, url: BACKEND_SELF_CHECK_URL };
}

function pythonPath() {
  if (process.env.DESKTOP_PYTHON_PATH && pathExists(process.env.DESKTOP_PYTHON_PATH)) {
    return process.env.DESKTOP_PYTHON_PATH;
  }
  const venvPython = path.join(BACKEND_DIR, ".venv", "Scripts", "python.exe");
  if (pathExists(venvPython)) {
    return venvPython;
  }
  return process.platform === "win32" ? "python" : "python3";
}

function nodePath() {
  if (process.env.DESKTOP_NODE_PATH && pathExists(process.env.DESKTOP_NODE_PATH)) {
    return process.env.DESKTOP_NODE_PATH;
  }
  return process.execPath && process.execPath.toLowerCase().endsWith("electron.exe") ? "node" : process.execPath;
}

async function ensureFrontend() {
  const ready = await frontendReady();
  if (ready.ok) {
    services.set("frontend", { startedByShell: false });
    return { ok: true, reused: true, url: FRONTEND_URL };
  }
  if (await isPortOpen(FRONTEND_PORT)) {
    return {
      ok: false,
      service: "frontend",
      error: `Port ${FRONTEND_PORT} is occupied, but the frontend did not respond.`,
    };
  }

  const nextBin = path.join(FRONTEND_DIR, "node_modules", "next", "dist", "bin", "next");
  if (!pathExists(nextBin)) {
    return { ok: false, service: "frontend", error: `Missing Next.js binary: ${nextBin}. Run npm install in frontend.` };
  }

  spawnService("desktop-frontend", nodePath(), [nextBin, "dev", "--hostname", "127.0.0.1", "--port", String(FRONTEND_PORT)], {
    cwd: FRONTEND_DIR,
    env: { ...process.env, NEXT_PUBLIC_API_BASE_URL: `http://127.0.0.1:${BACKEND_PORT}` },
  });
  const status = await waitForFrontend(60);
  if (!status.ok) {
    return { ok: false, service: "frontend", error: status.error };
  }
  return { ok: true, reused: false, url: FRONTEND_URL };
}

function ensureAsciiJunction() {
  if (pathExists(ASCII_LINK_DIR)) {
    return ASCII_LINK_DIR;
  }
  fs.symlinkSync(ROOT_DIR, ASCII_LINK_DIR, "junction");
  return ASCII_LINK_DIR;
}

function indextts2Paths() {
  const asciiRoot = ensureAsciiJunction();
  const asciiIndexTts = path.join(asciiRoot, "indextts2", "index-tts");
  return {
    asciiRoot,
    asciiIndextts2: path.join(asciiRoot, "indextts2"),
    python: path.join(asciiIndexTts, ".venv", "Scripts", "python.exe"),
    repo: asciiIndexTts,
    modelDir: path.join(asciiIndexTts, "checkpoints"),
    cfgPath: path.join(asciiIndexTts, "checkpoints", "config.yaml"),
    mplConfigDir: path.join(asciiRoot, "indextts2", ".matplotlib"),
  };
}

async function ensureIndexTTS2() {
  const ready = await request(INDEXTTS2_HEALTH_URL);
  if (ready.ok) {
    services.set("indextts2", { startedByShell: false });
    return { ok: true, reused: true, url: INDEXTTS2_HEALTH_URL };
  }
  if (await isPortOpen(INDEXTTS2_PORT)) {
    return {
      ok: false,
      service: "indextts2",
      error: `Port ${INDEXTTS2_PORT} is occupied, but IndexTTS2 adapter did not respond.`,
    };
  }
  if (!pathExists(path.join(INDEXTTS2_REPO_DIR, "checkpoints", "config.yaml"))) {
    return {
      ok: false,
      service: "indextts2",
      optional: true,
      error: "IndexTTS2 checkpoints are not installed. The desktop shell can run, but voice generation will be unavailable.",
    };
  }

  const paths = indextts2Paths();
  if (!pathExists(paths.python)) {
    return { ok: false, service: "indextts2", optional: true, error: `Missing IndexTTS2 Python: ${paths.python}` };
  }
  ensureDir(paths.mplConfigDir);

  const cleanEnv = { ...process.env };
  for (const key of ["HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"]) {
    delete cleanEnv[key];
  }
  const env = {
    ...cleanEnv,
    MPLCONFIGDIR: paths.mplConfigDir,
    INDEXTTS2_REPO: paths.repo,
    INDEXTTS2_MODEL_DIR: paths.modelDir,
    INDEXTTS2_CFG_PATH: paths.cfgPath,
    INDEXTTS2_DEVICE: process.env.INDEXTTS2_DEVICE || "cuda",
    INDEXTTS2_USE_FP16: process.env.INDEXTTS2_USE_FP16 || "false",
    INDEXTTS2_USE_CUDA_KERNEL: process.env.INDEXTTS2_USE_CUDA_KERNEL || "false",
    INDEXTTS2_USE_DEEPSPEED: process.env.INDEXTTS2_USE_DEEPSPEED || "false",
  };
  spawnService("desktop-indextts2", paths.python, ["-m", "uvicorn", "server:app", "--host", "127.0.0.1", "--port", String(INDEXTTS2_PORT)], {
    cwd: paths.asciiIndextts2,
    env,
  });
  const status = await waitForHttp(INDEXTTS2_HEALTH_URL, 45, "IndexTTS2 adapter");
  if (!status.ok) {
    return { ok: false, service: "indextts2", optional: true, error: status.error };
  }
  return { ok: true, reused: false, url: INDEXTTS2_HEALTH_URL };
}

async function createWindow() {
  mainWindow = new BrowserWindow({
    width: 1280,
    height: 860,
    minWidth: 1024,
    minHeight: 720,
    title: "MemWeave（忆织）",
    backgroundColor: "#f8fafc",
    webPreferences: {
      preload: path.join(__dirname, "preload.cjs"),
      contextIsolation: true,
      nodeIntegration: false,
    },
  });

  mainWindow.webContents.setWindowOpenHandler(({ url }) => {
    shell.openExternal(url);
    return { action: "deny" };
  });
  mainWindow.once("closed", () => {
    mainWindow = null;
  });
  await mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(statusHtml(["Preparing services..."]))}`);

  const results = [];
  results.push(await ensureBackend());
  results.push(await ensureIndexTTS2());
  results.push(await ensureFrontend());

  const fatal = results.find((result) => !result.ok && !result.optional);
  const lines = results.map((result) => {
    if (result.ok) {
      return `${result.reused ? "Reused" : "Started"} ${result.url}`;
    }
    return `${result.optional ? "Optional warning" : "Failed"} ${result.service}: ${result.error}`;
  });
  appendLog("desktop", lines.join(" | "));
  if (fatal) {
    await mainWindow.loadURL(`data:text/html;charset=utf-8,${encodeURIComponent(statusHtml(
      lines.concat(["", "详细日志：logs/desktop-shell.log"]),
      { failed: true, detail: fatal.error },
    ))}`);
    return;
  }
  await mainWindow.loadURL(FRONTEND_URL);
}

async function stopStartedServices() {
  if (shuttingDown) {
    return;
  }
  shuttingDown = true;
  for (const [name, service] of services.entries()) {
    if (!service.startedByShell || !service.child || service.child.killed) {
      continue;
    }
    await killProcessTree(name, service.child);
  }
}

async function quitDesktop(reason) {
  if (quitting) {
    return;
  }
  quitting = true;
  appendLog("desktop", `quitting: ${reason}`);
  await stopStartedServices();
  app.quit();
}

ipcMain.handle("desktop-service-status", async () => ({
  frontend: await request(FRONTEND_URL),
  backend: await request(BACKEND_HEALTH_URL),
  indextts2: await request(INDEXTTS2_HEALTH_URL),
}));

ipcMain.on("desktop-close", () => {
  void quitDesktop("failure_page_close");
});

app.whenReady().then(createWindow);

app.on("window-all-closed", () => {
  void quitDesktop("all_windows_closed");
});

app.on("before-quit", (event) => {
  if (quitting) {
    return;
  }
  event.preventDefault();
  void quitDesktop("before_quit");
});
