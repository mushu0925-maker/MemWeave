const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const backend = path.join(root, "backend");
const target = path.join(root, ".python-deps");
const candidates = [
  process.env.MEMWEAVE_PYTHON,
  path.join(backend, ".venv", "Scripts", "python.exe"),
  process.platform === "win32" ? "python" : "python3",
].filter(Boolean);
const python = candidates.find((candidate) => {
  if (path.isAbsolute(candidate) && !fs.existsSync(candidate)) {
    return false;
  }
  return spawnSync(candidate, ["-m", "pip", "--version"], { stdio: "ignore" }).status === 0;
});

if (!python) {
  throw new Error("No Python interpreter with pip was found. Set MEMWEAVE_PYTHON or install Python 3.11+.");
}

fs.mkdirSync(target, { recursive: true });
const result = spawnSync(
  python,
  [
    "-m",
    "pip",
    "install",
    "--upgrade",
    "--target",
    target,
    "-r",
    path.join(backend, "requirements.txt"),
    "-r",
    path.join(backend, "packaging-requirements.txt"),
  ],
  { cwd: root, stdio: "inherit" },
);

process.exit(result.status ?? 1);
