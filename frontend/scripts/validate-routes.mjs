import fs from "node:fs";
import path from "node:path";

const frontendDir = path.resolve(import.meta.dirname, "..");
const routesFile = path.join(frontendDir, "src", "lib", "routes.ts");
const appDir = path.join(frontendDir, "src", "app");
const srcDir = path.join(frontendDir, "src");

const routesContent = fs.readFileSync(routesFile, "utf-8");
const entryRegex =
  /\{\s*id:\s*"([^"]+)",\s*href:\s*"([^"]+)",\s*label:\s*"([^"]+)",\s*sublabel:\s*"([^"]+)",\s*screenTitle:\s*"([^"]+)",\s*componentName:\s*"([^"]+)"/gs;

const routes = [];
let match;
while ((match = entryRegex.exec(routesContent)) !== null) {
  routes.push({
    id: match[1],
    href: match[2],
    label: match[3],
    sublabel: match[4],
    screenTitle: match[5],
    componentName: match[6],
  });
}

if (routes.length === 0) {
  console.error("Route validator error: No routes parsed from src/lib/routes.ts");
  process.exit(1);
}

const seenIds = new Set();
const seenHrefs = new Set();
const errors = [];

for (const route of routes) {
  if (seenIds.has(route.id)) {
    errors.push(`Duplicate route id detected: ${route.id}`);
  }
  seenIds.add(route.id);

  if (seenHrefs.has(route.href)) {
    errors.push(`Duplicate route href detected: ${route.href}`);
  }
  seenHrefs.add(route.href);

  const pageFile =
    route.href === "/"
      ? path.join(appDir, "page.tsx")
      : path.join(appDir, route.href.replace(/^\//, ""), "page.tsx");

  if (!fs.existsSync(pageFile)) {
    errors.push(`Missing page.tsx for route ${route.href} (${pageFile})`);
    continue;
  }

  const pageSource = fs.readFileSync(pageFile, "utf-8");
  if (pageSource.trim().length < 40 || !pageSource.includes("export default")) {
    errors.push(`Blank or incomplete page component at ${pageFile}`);
  }
  if (!pageSource.includes(`routeId="${route.id}"`)) {
    errors.push(
      `Screen mapping mismatch in ${pageFile}: expected routeId="${route.id}"`
    );
  }
}

// Discover all actual page.tsx files in src/app to catch unregistered routes
function walk(dir, results = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) {
      walk(full, results);
    } else if (entry.isFile() && entry.name === "page.tsx") {
      results.push(full);
    }
  }
  return results;
}

for (const pageFile of walk(appDir)) {
  const rel = path.relative(appDir, path.dirname(pageFile)).replace(/\\/g, "/");
  const expectedHref = rel === "" ? "/" : `/${rel}`;
  if (!seenHrefs.has(expectedHref)) {
    errors.push(`Unregistered App Router page found: ${expectedHref} (${pageFile})`);
  }
}

// Validate every internal <Link href="/..."> and router.push("/...") across src/
function walkTsx(dir, results = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) walkTsx(full, results);
    else if (/\.(ts|tsx)$/.test(entry.name)) results.push(full);
  }
  return results;
}

const hrefPattern = /(?:href|router\.push)\s*[=(]\s*["'](\/[^"'#?]*)/g;
for (const file of walkTsx(srcDir)) {
  const src = fs.readFileSync(file, "utf-8");
  let m;
  while ((m = hrefPattern.exec(src)) !== null) {
    const target = m[1];
    if (target.startsWith("/brand/") || target.startsWith("/api/") || target === "/favicon.ico") {
      continue;
    }
    if (!seenHrefs.has(target)) {
      errors.push(`Broken navigation href="${target}" in ${path.relative(frontendDir, file)}`);
    }
  }
}

if (errors.length > 0) {
  console.error("Route validation FAILED:\n" + errors.map((e) => ` - ${e}`).join("\n"));
  process.exit(1);
}

console.log(
  `ROUTE_VALIDATION_OK verified ${routes.length} routes and screen mappings with zero duplicates or broken links.`
);
