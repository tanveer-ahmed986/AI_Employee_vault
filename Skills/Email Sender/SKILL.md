# Skill: Email Sender (MCP)

## Description
Sends or drafts emails via Gmail using the Email MCP Server. Available as tools inside Claude Code sessions.

## Trigger
- Available as MCP tools: `send_email` and `draft_email`
- Used by the approval watcher when an email action is approved
- Can be invoked by Claude during reasoning

## Prerequisites
1. Email MCP server installed: `cd mcp_servers/email_mcp && npm install`
2. MCP server registered in `.claude/settings.json`
3. Gmail OAuth credentials and token in `Secrets/`

## Tools Available

### `send_email`
Send an email immediately via Gmail.
- **to**: Recipient email address
- **subject**: Email subject line
- **body**: Email body (plain text)

### `draft_email`
Create a Gmail draft (does not send). Safe for review.
- **to**: Recipient email address
- **subject**: Email subject line
- **body**: Email body (plain text)

## Safety
- Per Company Handbook: messages to unknown senders require human review
- The `draft_email` tool is preferred for safety — creates a draft for human review
- `send_email` should only be used for pre-approved recipients

## Starting the MCP Server
The server starts automatically when Claude Code loads (configured in `.claude/settings.json`).
Manual start: `node mcp_servers/email_mcp/index.js`
