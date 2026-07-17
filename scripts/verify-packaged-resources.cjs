const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const packageJson = JSON.parse(fs.readFileSync(path.join(root, "package.json"), "utf8"));
const installers = path.join(root, "release", "installers");
const unpacked = path.join(installers, "win-unpacked");
const resources = path.join(unpacked, "resources");

const requiredFiles = [
  path.join(root, "build", "icon.ico"),
  path.join(unpacked, "MemWeave.exe"),
  path.join(resources, "app.asar"),
  path.join(resources, "voice-setup.ps1"),
  path.join(resources, "frontend", "server.js"),
  path.join(resources, "frontend", "node_modules", "next", "package.json"),
  path.join(resources, "backend", "memweave-backend", "memweave-backend.exe"),
  path.join(installers, `MemWeave-${packageJson.version}-Setup.exe`),
  path.join(installers, `MemWeave-${packageJson.version}-Setup.exe.blockmap`),
];

const requiredDirectories = [
  path.join(resources, "frontend", ".next", "static"),
];

const missing = requiredFiles.filter((file) => !fs.existsSync(file) || !fs.statSync(file).isFile());
for (const directory of requiredDirectories) {
  if (!fs.existsSync(directory) || !fs.statSync(directory).isDirectory() || fs.readdirSync(directory).length === 0) {
    missing.push(directory);
  }
}

if (missing.length > 0) {
  throw new Error(`Packaged runtime is incomplete:\n${missing.map((file) => `- ${file}`).join("\n")}`);
}

if (packageJson.build?.win?.icon !== "build/icon.ico") {
  throw new Error("Windows packaging must use build/icon.ico.");
}

const icon = fs.readFileSync(path.join(root, "build", "icon.ico"));
if (icon.readUInt16LE(0) !== 0 || icon.readUInt16LE(2) !== 1 || icon.readUInt16LE(4) !== 7) {
  throw new Error("build/icon.ico must contain the seven generated Windows icon frames.");
}

console.log(`Verified packaged runtime and installer for MemWeave ${packageJson.version}.`);
