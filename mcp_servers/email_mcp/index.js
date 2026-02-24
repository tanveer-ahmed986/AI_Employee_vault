/**
 * Email MCP Server — provides send_email and draft_email tools via Gmail API.
 * Uses @modelcontextprotocol/sdk for the MCP protocol layer.
 */

import { McpServer } from "@modelcontextprotocol/sdk/server/mcp.js";
import { StdioServerTransport } from "@modelcontextprotocol/sdk/server/stdio.js";
import { google } from "googleapis";
import { readFileSync, writeFileSync, existsSync } from "fs";
import { resolve, dirname } from "path";
import { fileURLToPath } from "url";
import { z } from "zod";

const __dirname = dirname(fileURLToPath(import.meta.url));
const VAULT_PATH = resolve(__dirname, "..", "..");
const SECRETS_DIR = resolve(VAULT_PATH, "Secrets");
const CREDENTIALS_FILE = resolve(SECRETS_DIR, "gmail_credentials.json");
const TOKEN_FILE = resolve(SECRETS_DIR, "token.json");

const SCOPES = [
  "https://www.googleapis.com/auth/gmail.send",
  "https://www.googleapis.com/auth/gmail.compose",
];

// ── Gmail auth ──────────────────────────────────────────────────────────

async function getGmailService() {
  if (!existsSync(CREDENTIALS_FILE)) {
    throw new Error(`Gmail credentials not found at ${CREDENTIALS_FILE}`);
  }

  const credentials = JSON.parse(readFileSync(CREDENTIALS_FILE, "utf-8"));
  const { client_id, client_secret, redirect_uris } =
    credentials.installed || credentials.web;

  const oAuth2Client = new google.auth.OAuth2(
    client_id,
    client_secret,
    redirect_uris?.[0] || "http://localhost"
  );

  if (existsSync(TOKEN_FILE)) {
    const token = JSON.parse(readFileSync(TOKEN_FILE, "utf-8"));
    oAuth2Client.setCredentials(token);

    // Refresh if expired
    if (token.expiry_date && Date.now() >= token.expiry_date) {
      const { credentials: refreshed } = await oAuth2Client.refreshAccessToken();
      oAuth2Client.setCredentials(refreshed);
      writeFileSync(TOKEN_FILE, JSON.stringify(refreshed), "utf-8");
    }
  } else {
    throw new Error(
      "Gmail token not found. Run the Gmail watcher first to complete OAuth flow."
    );
  }

  return google.gmail({ version: "v1", auth: oAuth2Client });
}

function buildRawEmail(to, subject, body) {
  const lines = [
    `To: ${to}`,
    `Subject: ${subject}`,
    "MIME-Version: 1.0",
    "Content-Type: text/plain; charset=UTF-8",
    "",
    body,
  ];
  const raw = lines.join("\r\n");
  return Buffer.from(raw).toString("base64url");
}

// ── MCP Server ──────────────────────────────────────────────────────────

const server = new McpServer({
  name: "email-mcp",
  version: "1.0.0",
});

server.tool(
  "send_email",
  "Send an email via Gmail. Requires human approval for unknown recipients.",
  {
    to: z.string().describe("Recipient email address"),
    subject: z.string().describe("Email subject line"),
    body: z.string().describe("Email body (plain text)"),
  },
  async ({ to, subject, body }) => {
    const gmail = await getGmailService();
    const raw = buildRawEmail(to, subject, body);

    const result = await gmail.users.messages.send({
      userId: "me",
      requestBody: { raw },
    });

    return {
      content: [
        {
          type: "text",
          text: `Email sent successfully.\nMessage ID: ${result.data.id}\nTo: ${to}\nSubject: ${subject}`,
        },
      ],
    };
  }
);

server.tool(
  "draft_email",
  "Create a Gmail draft (does not send). Safe for review before sending.",
  {
    to: z.string().describe("Recipient email address"),
    subject: z.string().describe("Email subject line"),
    body: z.string().describe("Email body (plain text)"),
  },
  async ({ to, subject, body }) => {
    const gmail = await getGmailService();
    const raw = buildRawEmail(to, subject, body);

    const result = await gmail.users.drafts.create({
      userId: "me",
      requestBody: {
        message: { raw },
      },
    });

    return {
      content: [
        {
          type: "text",
          text: `Draft created successfully.\nDraft ID: ${result.data.id}\nTo: ${to}\nSubject: ${subject}`,
        },
      ],
    };
  }
);

// ── Start ───────────────────────────────────────────────────────────────

const transport = new StdioServerTransport();
await server.connect(transport);
