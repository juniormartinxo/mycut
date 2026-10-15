// Regenerates backend/mycut/flow_icons from the lucide-react package used by the web app.
// Usage: node scripts/extract-flow-icons.mjs <path to node_modules/lucide-react>
import { readFileSync, writeFileSync } from "node:fs";
import { join } from "node:path";

const NAMES = ["user", "users", "bot", "brain", "cpu", "wrench", "database", "server", "cloud", "file-text", "files",
  "message-square", "mail", "search", "globe", "code", "terminal", "settings", "key", "lock", "shield-check", "zap",
  "sparkles", "image", "video", "mic", "smartphone", "laptop", "monitor", "chart-column", "trending-up", "dollar-sign",
  "shopping-cart", "package", "truck", "clock", "calendar", "circle-check", "triangle-alert", "circle-x", "lightbulb",
  "book-open", "layers", "git-branch", "workflow", "network", "link", "upload", "download", "send", "inbox", "folder",
  "camera", "music", "heart", "star", "building", "landmark", "wallet", "credit-card", "bell", "eye", "funnel",
  "list-checks", "puzzle", "rocket", "target", "flag", "hand-coins", "gauge", "cog", "receipt", "scan-text",
  "languages", "headphones", "store", "factory"];
const root = process.argv[2];
const pkg = JSON.parse(readFileSync(join(root, "package.json"), "utf8"));
const icons = {};
for (const name of NAMES) {
  const { __iconData } = await import(join(root, "dist/esm/icons", `${name}.mjs`));
  icons[name] = __iconData.node.map(([tag, attrs]) => [tag, Object.fromEntries(Object.entries(attrs).filter(([key]) => key !== "key"))]);
}
const target = new URL("../backend/mycut/flow_icons/", import.meta.url);
writeFileSync(new URL("icons.json", target), JSON.stringify(icons) + "\n");
writeFileSync(new URL("LICENSE", target), readFileSync(join(root, "LICENSE"), "utf8"));
writeFileSync(new URL("source.json", target), JSON.stringify({
  package: "lucide-react", version: pkg.version, license: pkg.license, url: "https://lucide.dev",
  note: "Curated subset for animated flow nodes; viewBox 0 0 24 24, stroke-based.", icons: NAMES.length,
}, null, 2) + "\n");
