const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const backend = path.join(root, "backend");
const pythonDependencies = path.join(root, ".python-deps");
const releaseRoot = path.join(root, "release");
const output = path.join(releaseRoot, "backend");
const work = path.join(releaseRoot, ".pyinstaller-work");
const spec = path.join(releaseRoot, ".pyinstaller-spec");
const candidates = [
  process.env.MEMWEAVE_PYTHON,
  path.join(backend, ".venv", "Scripts", "python.exe"),
  process.platform === "win32" ? "python" : "python3",
].filter(Boolean);
const python = candidates.find((candidate) => !path.isAbsolute(candidate) || fs.existsSync(candidate));

if (!python) {
  throw new Error("No Python interpreter was found. Set MEMWEAVE_PYTHON or install Python 3.11+.");
}
if (!fs.existsSync(path.join(pythonDependencies, "PyInstaller"))) {
  throw new Error("Packaging dependencies are missing. Run npm run package:setup first.");
}

fs.rmSync(output, { recursive: true, force: true });
fs.rmSync(work, { recursive: true, force: true });
fs.rmSync(spec, { recursive: true, force: true });
fs.mkdirSync(releaseRoot, { recursive: true });

const pythonPath = [pythonDependencies, backend, process.env.PYTHONPATH].filter(Boolean).join(path.delimiter);
const result = spawnSync(
  python,
  [
    "-m",
    "PyInstaller",
    "--noconfirm",
    "--clean",
    "--onedir",
    "--name",
    "memweave-backend",
    "--paths",
    backend,
    "--collect-all",
    "fastapi",
    "--collect-all",
    "pydantic",
    "--collect-all",
    "pydantic_settings",
    "--distpath",
    output,
    "--workpath",
    work,
    "--specpath",
    spec,
    path.join(backend, "app", "packaged_entry.py"),
  ],
  {
    cwd: root,
    env: { ...process.env, PYTHONPATH: pythonPath },
    stdio: "inherit",
  },
);

process.exit(result.status ?? 1);
