/**
 * ToolRunner
 *
 * Implements the agentic tool-execution loop: the LLM can call tools,
 * we execute them, feed results back, and loop until the model stops
 * requesting tool calls.
 *
 * Built-in tools:
 *   run_js        – execute a JS snippet in an isolated VM context
 *   read_file     – read a file from the workspace
 *   write_file    – write/overwrite a file in the workspace
 *   list_files    – list files in the workspace directory
 *   append_memory – append a note to memory.md via MemoryManager
 *   web_search    – placeholder (implement with your preferred search API)
 */

import vm from "node:vm";
import fs from "node:fs/promises";
import path from "node:path";

// ── Tool definitions (passed to the LLM in the tools array) ──────────────

export const TOOL_DEFINITIONS = [
  {
    name: "run_js",
    description:
      "Execute a JavaScript snippet and return stdout + the return value. Use for calculations, data transformation, or any logic that benefits from code.",
    input_schema: {
      type: "object",
      properties: {
        code: { type: "string", description: "JavaScript code to run." },
        timeout_ms: {
          type: "integer",
          description: "Max execution time in ms (default 5000).",
          default: 5000,
        },
      },
      required: ["code"],
    },
  },
  {
    name: "read_file",
    description: "Read a file from the agent workspace.",
    input_schema: {
      type: "object",
      properties: {
        filepath: { type: "string", description: "Relative path within the workspace." },
      },
      required: ["filepath"],
    },
  },
  {
    name: "write_file",
    description: "Write or overwrite a file in the agent workspace.",
    input_schema: {
      type: "object",
      properties: {
        filepath: { type: "string", description: "Relative path within the workspace." },
        content: { type: "string", description: "File content to write." },
      },
      required: ["filepath", "content"],
    },
  },
  {
    name: "list_files",
    description: "List files in a workspace directory.",
    input_schema: {
      type: "object",
      properties: {
        dir: {
          type: "string",
          description: "Relative directory path. Defaults to workspace root.",
          default: ".",
        },
      },
    },
  },
  {
    name: "append_memory",
    description:
      "Persist an important note or fact to long-term memory so it is available in future conversations.",
    input_schema: {
      type: "object",
      properties: {
        note: { type: "string", description: "The memory note to persist." },
      },
      required: ["note"],
    },
  },
];

// ── ToolRunner class ──────────────────────────────────────────────────────

export class ToolRunner {
  /**
   * @param {object} config
   * @param {string} config.workspaceDir   – agent file workspace root
   * @param {object} memoryManager        – MemoryManager instance
   * @param {object} logger
   */
  constructor(config, memoryManager, logger) {
    this.workspaceDir = config.workspaceDir;
    this.memoryManager = memoryManager;
    this.logger = logger;
  }

  /**
   * Execute a single tool call requested by the LLM.
   * Returns a string result to be fed back as a tool_result.
   */
  async execute(toolName, toolInput) {
    this.logger.info({ toolName, toolInput }, "executing tool");
    try {
      switch (toolName) {
        case "run_js":
          return await this._runJs(toolInput);
        case "read_file":
          return await this._readFile(toolInput);
        case "write_file":
          return await this._writeFile(toolInput);
        case "list_files":
          return await this._listFiles(toolInput);
        case "append_memory":
          return await this._appendMemory(toolInput);
        default:
          return `Error: unknown tool "${toolName}"`;
      }
    } catch (error) {
      this.logger.warn({ toolName, error }, "tool execution error");
      return `Error: ${String(error?.message ?? error)}`;
    }
  }

  // ── Tool implementations ──────────────────────────────────────────────

  async _runJs({ code, timeout_ms = 5000 }) {
    const logs = [];
    const sandbox = {
      console: {
        log: (...args) => logs.push(args.map(String).join(" ")),
        error: (...args) => logs.push("[err] " + args.map(String).join(" ")),
        warn: (...args) => logs.push("[warn] " + args.map(String).join(" ")),
      },
      Math,
      JSON,
      Date,
      Array,
      Object,
      String,
      Number,
      Boolean,
      parseInt,
      parseFloat,
      isNaN,
      isFinite,
    };

    vm.createContext(sandbox);
    let returnValue;
    try {
      returnValue = vm.runInContext(code, sandbox, {
        timeout: timeout_ms,
        breakOnSigint: true,
      });
    } catch (err) {
      logs.push(`Runtime error: ${err.message}`);
    }

    const output = logs.join("\n");
    const result = returnValue !== undefined ? JSON.stringify(returnValue, null, 2) : "";
    return [output, result].filter(Boolean).join("\n").trim() || "(no output)";
  }

  async _readFile({ filepath }) {
    const safe = this._safePath(filepath);
    try {
      const content = await fs.readFile(safe, "utf8");
      return content.length > 8000
        ? content.slice(0, 8000) + "\n… (truncated)"
        : content;
    } catch {
      return `Error: could not read "${filepath}"`;
    }
  }

  async _writeFile({ filepath, content }) {
    const safe = this._safePath(filepath);
    await fs.mkdir(path.dirname(safe), { recursive: true });
    await fs.writeFile(safe, content, "utf8");
    return `Written ${content.length} bytes to "${filepath}"`;
  }

  async _listFiles({ dir = "." } = {}) {
    const safe = this._safePath(dir);
    try {
      const entries = await fs.readdir(safe, { withFileTypes: true });
      return entries
        .map((e) => (e.isDirectory() ? `${e.name}/` : e.name))
        .join("\n");
    } catch {
      return `Error: could not list "${dir}"`;
    }
  }

  async _appendMemory({ note }) {
    await this.memoryManager.appendMemory(note);
    return "Memory updated.";
  }

  /** Prevent path traversal outside the workspace */
  _safePath(rel) {
    const resolved = path.resolve(this.workspaceDir, rel);
    if (!resolved.startsWith(path.resolve(this.workspaceDir))) {
      throw new Error("path traversal detected");
    }
    return resolved;
  }
}
