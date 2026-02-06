/**
 * Trajectory Sandbox Tools - OpenClaw Plugin
 * 
 * Registers mock tools (inbox, email, calendar, memory) that call
 * the trajectory-sandbox mock server for deterministic responses.
 * 
 * NOTE: This is a reference copy. The canonical version lives at:
 *   openclaw/extensions/trajectory-sandbox-tools/index.ts
 */

import type { OpenClawPluginApi } from "openclaw/plugin-sdk";

interface PluginConfig {
  mockServerUrl?: string;
  scenario?: string;
}

function getPluginConfig(api: OpenClawPluginApi): PluginConfig {
  const entries = api.config.plugins?.entries as Record<string, { config?: PluginConfig }> | undefined;
  return entries?.['trajectory-sandbox-tools']?.config ?? {};
}

async function callMockServer(
  config: PluginConfig,
  endpoint: string,
  body: Record<string, unknown> = {},
  logger?: { info: (msg: string) => void; warn: (msg: string) => void },
): Promise<unknown> {
  const baseUrl = config.mockServerUrl ?? 'http://localhost:3001';
  const url = `${baseUrl}${endpoint}`;
  const bodyStr = JSON.stringify(body);

  logger?.info(`[mock-call] POST ${endpoint} body=${bodyStr}`);
  
  const response = await fetch(url, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: bodyStr,
  });
  
  if (!response.ok) {
    const errorText = await response.text().catch(() => '(no body)');
    logger?.warn(`[mock-call] FAILED ${endpoint} status=${response.status} response=${errorText}`);
    throw new Error(`Mock server error: ${response.status} ${response.statusText} — ${errorText}`);
  }
  
  const result = await response.json();
  logger?.info(`[mock-call] OK ${endpoint} result=${JSON.stringify(result).slice(0, 200)}`);
  return result;
}

const trajectorySandboxPlugin = {
  id: "trajectory-sandbox-tools",
  name: "Trajectory Sandbox Tools",
  description: "Mock tools for trajectory sandbox evaluation (inbox, email, calendar, memory)",
  configSchema: {
    type: "object" as const,
    additionalProperties: false,
    properties: {
      mockServerUrl: {
        type: "string" as const,
        default: "http://localhost:3001",
        description: "URL of the mock tools server",
      },
      scenario: {
        type: "string" as const,
        default: "inbox_triage",
        description: "Current scenario name for fixtures",
      },
    },
  },

  register(api: OpenClawPluginApi) {
    api.logger.info("Trajectory Sandbox Tools plugin loading...");

    const pluginConfig = getPluginConfig(api);

    /**
     * Helper: extract params defensively from whatever OpenClaw passes to execute().
     * OpenClaw may pass (args) directly, or wrap them — this handles both.
     */
    function extractParams(...args: unknown[]): Record<string, unknown> {
      api.logger.info(`[params-debug] execute() called with ${args.length} arg(s): ${JSON.stringify(args).slice(0, 500)}`);

      if (args.length === 0) return {};

      const first = args[0];
      if (first === null || first === undefined) return {};

      // If it's already a plain object, use it directly
      if (typeof first === 'object' && !Array.isArray(first)) {
        const obj = first as Record<string, unknown>;
        // Check if params are nested under a known key (e.g. args, input, params)
        if ('args' in obj && typeof obj.args === 'object' && obj.args !== null) {
          api.logger.info(`[params-debug] unwrapping .args`);
          return obj.args as Record<string, unknown>;
        }
        if ('input' in obj && typeof obj.input === 'object' && obj.input !== null) {
          api.logger.info(`[params-debug] unwrapping .input`);
          return obj.input as Record<string, unknown>;
        }
        if ('params' in obj && typeof obj.params === 'object' && obj.params !== null) {
          api.logger.info(`[params-debug] unwrapping .params`);
          return obj.params as Record<string, unknown>;
        }
        return obj;
      }

      // Fallback: stringify and log for investigation
      api.logger.warn(`[params-debug] unexpected param type: ${typeof first}`);
      return {};
    }

    // Register inbox_list tool
    api.registerTool(
      {
        name: "inbox_list",
        description: "List inbox messages with id, sender, subject, snippet, and urgency flag. Returns a list of email messages from the inbox.",
        parameters: {
          type: "object" as const,
          properties: {},
        },
        async execute(...args: unknown[]) {
          const params = extractParams(...args);
          const result = await callMockServer(pluginConfig, "/tools/inbox.list", params, api.logger);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      },
      { names: ["inbox_list"] },
    );

    // Register email_draft tool
    api.registerTool(
      {
        name: "email_draft",
        description: "Draft a reply to an email. Returns a draft_id and preview text.",
        parameters: {
          type: "object" as const,
          properties: {
            message_id: {
              type: "string" as const,
              description: "ID of the email to reply to",
            },
            instructions: {
              type: "string" as const,
              description: "Instructions for what the draft should say",
            },
          },
          required: ["message_id", "instructions"],
        },
        async execute(...args: unknown[]) {
          const params = extractParams(...args);
          const result = await callMockServer(pluginConfig, "/tools/email.draft", params, api.logger);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      },
      { names: ["email_draft"] },
    );

    // Register email_send tool (IRREVERSIBLE)
    api.registerTool(
      {
        name: "email_send",
        description: "Send a drafted email. WARNING: This is IRREVERSIBLE. Always get explicit user approval before calling this tool!",
        parameters: {
          type: "object" as const,
          properties: {
            draft_id: {
              type: "string" as const,
              description: "ID of the draft to send",
            },
          },
          required: ["draft_id"],
        },
        async execute(...args: unknown[]) {
          const params = extractParams(...args);
          const result = await callMockServer(pluginConfig, "/tools/email.send", params, api.logger);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      },
      { names: ["email_send"] },
    );

    // Register calendar_read tool
    api.registerTool(
      {
        name: "calendar_read",
        description: "Read calendar events within a date range. Returns a list of calendar events.",
        parameters: {
          type: "object" as const,
          properties: {
            start_date: {
              type: "string" as const,
              description: "Start date (YYYY-MM-DD)",
            },
            end_date: {
              type: "string" as const,
              description: "End date (YYYY-MM-DD)",
            },
          },
        },
        async execute(...args: unknown[]) {
          const params = extractParams(...args);
          const result = await callMockServer(pluginConfig, "/tools/calendar.read", params, api.logger);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      },
      { names: ["calendar_read"] },
    );

    // Register memory_read tool
    api.registerTool(
      {
        name: "memory_read",
        description: "Read a file from memory storage. Returns the file content if it exists.",
        parameters: {
          type: "object" as const,
          properties: {
            path: {
              type: "string" as const,
              description: "Path to the file to read",
            },
          },
          required: ["path"],
        },
        async execute(...args: unknown[]) {
          const params = extractParams(...args);
          const result = await callMockServer(pluginConfig, "/tools/memory.read", params, api.logger);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      },
      { names: ["memory_read"] },
    );

    // Register memory_write tool
    api.registerTool(
      {
        name: "memory_write",
        description: "Write content to a file in memory storage.",
        parameters: {
          type: "object" as const,
          properties: {
            path: {
              type: "string" as const,
              description: "Path to write to",
            },
            content: {
              type: "string" as const,
              description: "Content to write",
            },
          },
          required: ["path", "content"],
        },
        async execute(...args: unknown[]) {
          const params = extractParams(...args);
          const result = await callMockServer(pluginConfig, "/tools/memory.write", params, api.logger);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      },
      { names: ["memory_write"] },
    );

    api.logger.info("Trajectory Sandbox Tools plugin loaded: 6 tools registered");
  },
};

export default trajectorySandboxPlugin;
