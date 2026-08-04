// WriteWhiteboard / ReadWhiteboard tool. Collapsible:
//   header: `<name>: <description>`
//   body (when expanded): the finding content.
// Expansion is per-block; the toggle is wired by the transcript in a later
// stage. Collapsed by default.
import React from 'react';
import { Box, Text } from 'ink';
import { z } from 'zod';
import type { ToolBlock } from '../state/sessionReducer.js';

export const WhiteboardEntrySchema = z.object({
  name: z.string(),
  description: z.string(),
  content: z.string(),
});
export const WhiteboardWriteArgsSchema = z.object({
  name: z.string(),
  description: z.string(),
  content: z.string(),
});
export const WhiteboardResultSchema = z.object({
  status: z.boolean(),
  result: z.union([z.string(), WhiteboardEntrySchema]),
});

// Prefers the write args (they carry name/description/content); otherwise falls
// back to an entry returned in the result (read case).
function resolveEntry(block: ToolBlock): { name: string; description: string; content: string } | null {
  const args = WhiteboardWriteArgsSchema.safeParse(block.args);
  if (args.success) return args.data;

  if (block.result !== undefined) {
    const res = WhiteboardResultSchema.safeParse(block.result);
    if (res.success && typeof res.data.result !== 'string') return res.data.result;
  }
  return null;
}

export const WhiteboardBlock = React.memo(function WhiteboardBlock({
  block,
  expanded = false,
}: {
  block: ToolBlock;
  expanded?: boolean;
}) {
  const entry = resolveEntry(block);
  if (entry === null) {
    return (
      <Box>
        <Text dimColor>whiteboard</Text>
      </Box>
    );
  }

  return (
    <Box flexDirection="column">
      <Text>
        <Text dimColor>{expanded ? '▼' : '▶'} </Text>
        <Text bold>{entry.name}</Text>: {entry.description}
      </Text>
      {expanded ? (
        <Box paddingLeft={2}>
          <Text>{entry.content}</Text>
        </Box>
      ) : null}
    </Box>
  );
});
