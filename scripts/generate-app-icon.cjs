const fs = require("node:fs");
const path = require("node:path");

const root = path.resolve(__dirname, "..");
const sharp = require(path.join(root, "frontend", "node_modules", "sharp"));
const source = path.join(root, "build", "icon.svg");
const output = path.join(root, "build", "icon.ico");
const sizes = [16, 24, 32, 48, 64, 128, 256];

async function main() {
  const svg = fs.readFileSync(source);
  const images = await Promise.all(
    sizes.map((size) => sharp(svg).resize(size, size).png().toBuffer()),
  );
  const header = Buffer.alloc(6 + images.length * 16);
  header.writeUInt16LE(0, 0);
  header.writeUInt16LE(1, 2);
  header.writeUInt16LE(images.length, 4);

  let offset = header.length;
  images.forEach((image, index) => {
    const size = sizes[index];
    const entry = 6 + index * 16;
    header.writeUInt8(size === 256 ? 0 : size, entry);
    header.writeUInt8(size === 256 ? 0 : size, entry + 1);
    header.writeUInt8(0, entry + 2);
    header.writeUInt8(0, entry + 3);
    header.writeUInt16LE(1, entry + 4);
    header.writeUInt16LE(32, entry + 6);
    header.writeUInt32LE(image.length, entry + 8);
    header.writeUInt32LE(offset, entry + 12);
    offset += image.length;
  });

  fs.writeFileSync(output, Buffer.concat([header, ...images]));
  console.log(`Generated Windows icon: ${output}`);
}

main().catch((error) => {
  console.error(error);
  process.exit(1);
});
