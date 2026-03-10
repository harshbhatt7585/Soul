/**
 * AgentRuntime
 *
 * The core agentic loop.  Given a session (with history) and user text,
 * it calls the LLM, processes any tool_use blocks by executing them via
 * ToolRunner, feeds results back, and loops until the model issues a
 * final text reply.
 *
 * Compatible with the Anthropic Messages API (claude-* models).
 */

import Anthropic from "@anthropic-ai/sdk";
import { TOOL_DEFINITIONS } from "./tool-runner.js";

const MAX_TOOL_ROUNDS = 10; // safety cap to prevent infinite loops

export class AgentRuntime {
  /**
   * @param {object} config
   * @param {string} config.model            – Anthropic model id
   * @param {number} config.maxTokens        – max tokens per LLM call (default 2048)
   * @param {object} memoryManager           – MemoryManager instance
   * @param {object} toolRunner              – ToolRunner instance
   * @param {object} logger
   */
  constructor(config, memoryManager, toolRunner, logger) {
    this.config = config;
    this.memoryManager = memoryManager;
    this.toolRunner = toolRunner;
    this.logger = logger;
    this.client = new Anthropic(); // reads ANTHROPIC_API_KEY from env
  }

  /**
   * Run the agentic loop for one inbound message.
   *
   * @param {object} params
   * @param {import('./session-manager.js').Session} params.session
   * @param {string} params.userText   – cleaned user message (mention stripped)
   * @param {string} params.senderJid
   * @param {string} params.pushName
   * @returns {Promise<string>}        – final text reply
   */
  async run({ session, userText, senderJid, pushName }) {
    // Add user turn to session history
    session.addTurn("user", userText);

    const systemPrompt = this.memoryManager.buildSystemPrompt(
      `Current conversation JID: ${session.jid}\nSender: ${pushName || senderJid}`,
    );

    const messages = session.toLLMHistory();

    let replyText = "";
    let rounds = 0;

    // ── Agentic tool loop ──────────────────────────────────────────────────
    let currentMessages = [...messages];

    while (rounds < MAX_TOOL_ROUNDS) {
      rounds += 1;

      const response = await this.client.messages.create({
        model: this.config.model ?? "claude-opus-4-5",
        max_tokens: this.config.maxTokens ?? 2048,
        system: systemPrompt,
        tools: TOOL_DEFINITIONS,
        messages: currentMessages,
      });

      this.logger.info(
        { stopReason: response.stop_reason, round: rounds },
        "LLM response received",
      );

      // Collect text blocks from this response
      const textBlocks = response.content
        .filter((b) => b.type === "text")
        .map((b) => b.text)
        .join("\n")
        .trim();

      const toolUseBlocks = response.content.filter((b) => b.type === "tool_use");

      if (response.stop_reason === "end_turn" || toolUseBlocks.length === 0) {
        // No more tool calls — we have our final answer
        replyText = textBlocks;
        break;
      }

      // ── Execute all requested tool calls in parallel ──────────────────
      const toolResults = await Promise.all(
        toolUseBlocks.map(async (block) => {
          const result = await this.toolRunner.execute(block.name, block.input);
          return {
            type: "tool_result",
            tool_use_id: block.id,
            content: String(result),
          };
        }),
      );

      // Append assistant turn + tool results to message history for next round
      currentMessages = [
        ...currentMessages,
        { role: "assistant", content: response.content },
        { role: "user", content: toolResults },
      ];
    }

    if (!replyText) {
      replyText = "(I was unable to produce a response — please try again.)";
    }

    // Persist assistant turn in session history
    session.addTurn("assistant", replyText);

    // Proactively extract memory note (non-blocking fire-and-forget)
    this._maybeUpdateMemory(userText, replyText).catch((err) =>
      this.logger.warn({ err }, "memory update failed"),
    );

    return replyText;
  }

  /**
   * After each conversation turn, ask the LLM (cheaply, small model)
   * whether anything is worth persisting to memory.
   */
  async _maybeUpdateMemory(userText, assistantText) {
    const prompt = `You are a memory archivist. Given the following exchange, decide if there is any important fact, preference, or context worth saving to long-term memory. If yes, call append_memory with a concise note. If nothing noteworthy, do nothing.

User: ${userText}
Assistant: ${assistantText}`;

    try {
      const response = await this.client.messages.create({
        model: "claude-haiku-4-5-20251001",
        max_tokens: 256,
        tools: [
          {
            name: "append_memory",
            description: "Persist an important note to long-term memory.",
            input_schema: {
              type: "object",
              properties: { note: { type: "string" } },
              required: ["note"],
            },
          },
        ],
        messages: [{ role: "user", content: prompt }],
      });

      for (const block of response.content) {
        if (block.type === "tool_use" && block.name === "append_memory") {
          await this.toolRunner.execute("append_memory", block.input);
        }
      }
    } catch {
      // Non-critical — swallow silently
    }
  }
}
