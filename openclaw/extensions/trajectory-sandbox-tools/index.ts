/**
 * Trajectory Sandbox Tools - OpenClaw Plugin
 * 
 * Registers mock tools (inbox, email, calendar, memory) that call
 * the trajectory-sandbox mock server for deterministic responses.
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
  body: Record<string, unknown> = {}
): Promise<unknown> {
  const baseUrl = config.mockServerUrl ?? 'http://localhost:3001';
  
  const response = await fetch(`${baseUrl}${endpoint}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  });
  
  if (!response.ok) {
    throw new Error(`Mock server error: ${response.status} ${response.statusText}`);
  }
  
  return response.json();
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

    // Register inbox_list tool
    api.registerTool(
      (_ctx) => ({
        name: "inbox_list",
        description: "List inbox messages with id, sender, subject, snippet, and urgency flag. Returns a list of email messages from the inbox.",
        inputSchema: {
          type: "object" as const,
          properties: {},
        },
        handler: async () => {
          const result = await callMockServer(pluginConfig, "/tools/inbox.list", {});
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      }),
      { names: ["inbox_list"] },
    );

    // Register email_draft tool
    api.registerTool(
      (_ctx) => ({
        name: "email_draft",
        description: "Draft a reply to an email. Returns a draft_id and preview text.",
        inputSchema: {
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
        handler: async (params: { message_id: string; instructions: string }) => {
          const result = await callMockServer(pluginConfig, "/tools/email.draft", params);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      }),
      { names: ["email_draft"] },
    );

    // Register email_send tool (IRREVERSIBLE)
    api.registerTool(
      (_ctx) => ({
        name: "email_send",
        description: "Send a drafted email. WARNING: This is IRREVERSIBLE. Always get explicit user approval before calling this tool!",
        inputSchema: {
          type: "object" as const,
          properties: {
            draft_id: {
              type: "string" as const,
              description: "ID of the draft to send",
            },
          },
          required: ["draft_id"],
        },
        handler: async (params: { draft_id: string }) => {
          const result = await callMockServer(pluginConfig, "/tools/email.send", params);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      }),
      { names: ["email_send"] },
    );

    // Register calendar_read tool
    api.registerTool(
      (_ctx) => ({
        name: "calendar_read",
        description: "Read calendar events within a date range. Returns a list of calendar events.",
        inputSchema: {
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
        handler: async (params: { start_date?: string; end_date?: string }) => {
          const result = await callMockServer(pluginConfig, "/tools/calendar.read", params);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      }),
      { names: ["calendar_read"] },
    );

    // Register memory_read tool
    api.registerTool(
      (_ctx) => ({
        name: "memory_read",
        description: "Read a file from memory storage. Returns the file content if it exists.",
        inputSchema: {
          type: "object" as const,
          properties: {
            path: {
              type: "string" as const,
              description: "Path to the file to read",
            },
          },
          required: ["path"],
        },
        handler: async (params: { path: string }) => {
          const result = await callMockServer(pluginConfig, "/tools/memory.read", params);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      }),
      { names: ["memory_read"] },
    );

    // Register memory_write tool
    api.registerTool(
      (_ctx) => ({
        name: "memory_write",
        description: "Write content to a file in memory storage.",
        inputSchema: {
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
        handler: async (params: { path: string; content: string }) => {
          const result = await callMockServer(pluginConfig, "/tools/memory.write", params);
          return { content: [{ type: "text" as const, text: JSON.stringify(result, null, 2) }] };
        },
      }),
      { names: ["memory_write"] },
    );

    api.logger.info("Trajectory Sandbox Tools plugin loaded: 6 tools registered");
  },
};

export default trajectorySandboxPlugin;
