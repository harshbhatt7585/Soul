import { spawn } from "node:child_process";

export class SoulBridge {
  constructor(config, logger) {
    this.config = config;
    this.logger = logger;
  }

  async handleInbound(message) {
    const payload = JSON.stringify(message);
    const timeoutMs = this.config.bridgeTimeoutMs ?? 120_000;

    return await new Promise((resolve, reject) => {
      const child = spawn(this.config.pythonBin, [this.config.soulBridgeScript], {
        cwd: this.config.rootDir,
        stdio: ["pipe", "pipe", "pipe"],
      });
      const timeout = setTimeout(() => {
        child.kill("SIGKILL");
        reject(new Error(`Soul bridge timed out after ${timeoutMs}ms`));
      }, timeoutMs);

      let stdout = "";
      let stderr = "";

      child.stdout.on("data", (chunk) => {
        stdout += chunk.toString("utf-8");
      });
      child.stderr.on("data", (chunk) => {
        stderr += chunk.toString("utf-8");
      });
      child.on("error", (error) => {
        clearTimeout(timeout);
        reject(error);
      });
      child.on("close", (code) => {
        clearTimeout(timeout);
        if (code !== 0) {
          reject(new Error(`Soul bridge exited with code ${code}: ${stderr.trim() || stdout.trim()}`));
          return;
        }

        try {
          const parsed = JSON.parse(stdout);
          resolve(parsed);
        } catch (error) {
          reject(new Error(`Soul bridge returned invalid JSON: ${stdout.trim()}`));
        }
      });

      child.stdin.write(payload);
      child.stdin.end();
    });
  }
}
