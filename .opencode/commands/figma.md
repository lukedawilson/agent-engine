---
description: Access a Figma design file using the Claude CLI Figma MCP. Usage: /figma [file-url] [prompt]
argument-hint: [file-url] [prompt]
---

Access a Figma file through the Claude CLI's Figma MCP connection
(`https://mcp.figma.com/mcp`). The editable build path uses the `use_figma`
tool, invoked via `claude -p` — it is not available in OpenCode's own tool
list.

## Inputs

1. **Figma file URL** (`$1`) — e.g. `https://www.figma.com/design/XYmIeoYqAEFdPX1oeB7WRl?node-id=0-1`
2. **Prompt** (`$2`) — what the user wants to do. E.g. "read the design context of the landing page frame", "build a button component with auto layout", "check which libraries are enabled".

## Resolve the fileKey

Extract the `fileKey` from the URL — it is the path segment after `/design/`:

```
https://www.figma.com/design/:fileKey/...
```

## Available Figma MCP tools

These are invoked via `claude -p` with the Figma MCP connection. The tool names
are:

| Tool | Purpose |
|------|---------|
| `get_metadata` | Returns the XML node tree for a page or frame (structure, IDs, names, positions, sizes). Use for overview / navigation. |
| `get_design_context` | Returns React+Tailwind reference code for a selected node. Requires a specific node ID (not a page/canvas). Also returns a rendered screenshot. |
| `get_libraries` | Returns the libraries enabled on the file. Used to verify which design system kits are available. |
| `use_figma` | Executes JavaScript against the Figma Plugin API (`figma` global) to create/update editable frames. Inputs: `fileKey`, `code` (JS, max 50,000 chars), `description` (plain-English summary), `skillNames` (optional — pass `"figma-use,figma-generate-design"` on first call). |

## Invocation pattern

Run Claude CLI non-interactively, granting permission to the specific tools:

```bash
claude -p "<detailed prompt telling Claude what to do>" \
  --allowedTools 'mcp__claude_ai_Figma__get_metadata,mcp__claude_ai_Figma__get_design_context,mcp__claude_ai_Figma__get_libraries,mcp__claude_ai_Figma__use_figma'
```

### Crafting the prompt

The `claude -p` prompt must be self-contained — Claude has no access to your
conversation context. Include:

- The exact `fileKey`
- The specific node ID(s) to operate on (from `get_metadata` or the URL's `node-id` parameter)
- The exact operation(s) to perform and which tools to use
- If using `use_figma`, provide the JavaScript code inline (or instruct Claude
  to generate it based on a description)
- Any constraints (viewport width, color tokens, type styles, fill discipline)

### `use_figma` specifics

- The `code` parameter is JavaScript that runs against the Figma Plugin API
  (`figma.createFrame()`, `figma.createText()`, etc.).
- **Fill discipline**: Only frames that explicitly carry a theme class get a
  background fill. Intermediate structural wrappers MUST have null/empty fills
  — they are TRANSPARENT.
- Wrap code in an async IIFE and use `figma.notify()` / `console.log()` to
  report results.
- For large pages, chunk into one `use_figma` call per section per viewport.

## Common workflows

### Read a page's structure

```
claude -p "Use get_metadata on fileKey XYmIeoYqAEFdPX1oeB7WRl, nodeId '0:1'. Return the full node tree." \
  --allowedTools 'mcp__claude_ai_Figma__get_metadata'
```

### Get design context for a specific frame

First use `get_metadata` to find the frame's node ID, then:

```
claude -p "Use get_design_context on fileKey XYmIeoYqAEFdPX1oeB7WRl, nodeId '3:234'. Return the full output." \
  --allowedTools 'mcp__claude_ai_Figma__get_design_context'
```

### Check enabled libraries

```
claude -p "Use get_libraries on fileKey XYmIeoYqAEFdPX1oeB7WRl. Report which libraries are enabled." \
  --allowedTools 'mcp__claude_ai_Figma__get_libraries'
```

### Build editable frames

```
claude -p "Use the use_figma tool on fileKey XYmIeoYqAEFdPX1oeB7WRl. Pass skillNames 'figma-use,figma-generate-design'. Build a frame named 'MyFrame — 1280' at 1280x800 with auto layout. <JavaScript code or description of what to build>" \
  --allowedTools 'mcp__claude_ai_Figma__use_figma'
```

## Never use screenshots for editable builds

The entire point of Figma export is an EDITABLE file a designer can work on —
real frames with Auto Layout, real text nodes with type styles, real
fills/strokes. A flat bitmap (screenshot, image fill, rasterized capture) is
worthless. Never produce, upload, or place screenshots as part of an editable
build — not even as a "reference" alongside the editable frames.

## After each call

Read the tool output and report results to the user. If a tool call fails,
read the error message and adjust — common issues include wrong node IDs,
permission denials, or missing libraries.
