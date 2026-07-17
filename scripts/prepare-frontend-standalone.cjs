const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const frontend = path.join(root, "frontend");
const next = path.join(frontend, ".next");
const source = path.join(next, "standalone");
const destination = path.join(root, "release", "frontend");

if (!fs.existsSync(path.join(source, "server.js"))) {
  throw new Error("Next standalone output is missing. Run the frontend production build first.");
}

fs.rmSync(destination, { recursive: true, force: true });
fs.mkdirSync(destination, { recursive: true });
fs.cpSync(source, destination, { recursive: true });
fs.cpSync(path.join(next, "static"), path.join(destination, ".next", "static"), { recursive: true });
const publicDirectory = path.join(frontend, "public");
if (fs.existsSync(publicDirectory)) {
  fs.cpSync(publicDirectory, path.join(destination, "public"), { recursive: true });
}

console.log(`Prepared Next standalone runtime: ${destination}`);
