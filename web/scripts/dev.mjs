import { existsSync } from "node:fs";
import { createConnection } from "node:net";
import { dirname, delimiter, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { spawn } from "node:child_process";

const webRoot = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const projectRoot = resolve(webRoot, "..");
const nextBin = join(webRoot, "node_modules", "next", "dist", "bin", "next");
const virtualPython = join(projectRoot, ".venv", "bin", "python");
const python = process.env.TI_ORACLE_PYTHON ?? (existsSync(virtualPython) ? virtualPython : "python3");
const children = new Set();

function portIsOpen(port) {
  return new Promise((resolvePort) => {
    const socket = createConnection({ host: "127.0.0.1", port });
    socket.setTimeout(350);
    socket.once("connect", () => { socket.destroy(); resolvePort(true); });
    socket.once("timeout", () => { socket.destroy(); resolvePort(false); });
    socket.once("error", () => resolvePort(false));
  });
}

function launch(command, args, options) {
  const child = spawn(command, args, { stdio: "inherit", ...options });
  children.add(child);
  child.once("exit", () => children.delete(child));
  return child;
}

const apiAlreadyRunning = await portIsOpen(8000);
const frontendAlreadyRunning = await portIsOpen(3000);

if (apiAlreadyRunning) {
  console.log("[TI Oracle] Using the data API already running on http://127.0.0.1:8000");
} else {
  console.log("[TI Oracle] Starting FastAPI data engine on http://127.0.0.1:8000");
  const pythonPath = [join(projectRoot, "src"), process.env.PYTHONPATH].filter(Boolean).join(delimiter);
  const api = launch(
    python,
    ["-m", "uvicorn", "ti_oracle_data.webapp:app", "--host", "127.0.0.1", "--port", "8000"],
    { cwd: projectRoot, env: { ...process.env, PYTHONPATH: pythonPath } },
  );
  api.once("exit", (code) => {
    if (code) console.error("[TI Oracle] FastAPI stopped. Install backend packages with: pip install -e '.[web]'");
  });
}

let frontend = null;
if (frontendAlreadyRunning) {
  console.log("[TI Oracle] Using Next.js already running on http://127.0.0.1:3000");
} else {
  console.log("[TI Oracle] Starting Next.js on http://127.0.0.1:3000");
  frontend = launch(process.execPath, [nextBin, "dev"], { cwd: webRoot, env: process.env });
}

function shutdown(signal) {
  for (const child of children) child.kill(signal);
}

// Terminal Ctrl+C reaches the whole foreground process group, including the
// children, so forwarding SIGINT would deliver it twice to Uvicorn.
process.on("SIGINT", () => { process.exitCode = 130; });
process.on("SIGTERM", () => shutdown("SIGTERM"));
frontend?.once("exit", (code) => {
  shutdown("SIGTERM");
  process.exitCode = code ?? 0;
});
