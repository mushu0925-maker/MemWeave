const { spawnSync } = require("node:child_process");
const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const candidates = [
  process.env.MEMWEAVE_PYTHON,
  path.join(root, "backend", ".venv", "Scripts", "python.exe"),
  path.join(root, "backend", ".venv", "bin", "python"),
  process.platform === "win32" ? "python" : "python3",
].filter(Boolean);

function isPathCandidate(candidate) {
  return path.isAbsolute(candidate) || candidate.includes(path.sep);
}

const python = candidates.find((candidate) => !isPathCandidate(candidate) || fs.existsSync(candidate));
if (!python) {
  console.error("No Python interpreter was found. Run npm run setup or set MEMWEAVE_PYTHON.");
  process.exit(1);
}

const result = spawnSync(python, process.argv.slice(2), {
  cwd: root,
  env: process.env,
  stdio: "inherit",
});

if (result.error) {
  console.error(result.error.message);
  process.exit(1);
}
process.exit(result.status ?? 1);
