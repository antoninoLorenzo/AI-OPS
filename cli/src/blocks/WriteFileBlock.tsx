// WriteFile tool.
//   issued: `Writing to <path>` followed by the content being written.
//   result: the workspace tree view, or the error.
import React from 'react';
import { Box, Text } from 'ink';
import { z } from 'zod';
import type { ToolBlock } from '../state/sessionReducer.js';

export const WriteFileArgsSchema = z.object({ path: z.string(), content: z.string() });
export const WriteFileResultSchema = z.object({
  tree_view: z.string().nullish(),
  error: z.string().nullish(),
});

const MAX_CONTENT_LINES = 20;

function clip(text: string, maxLines: number): string {
  const lines = text.split('\n');
  if (lines.length <= maxLines) return text;
  return lines.slice(0, maxLines).join('\n') + `\n… (${lines.length - maxLines} more lines)`;
}

export const WriteFileBlock = React.memo(function WriteFileBlock({ block }: { block: ToolBlock }) {
  const parsedArgs = WriteFileArgsSchema.safeParse(block.args);
  const path = parsedArgs.success ? parsedArgs.data.path : JSON.stringify(block.args);
  const content = parsedArgs.success ? parsedArgs.data.content : '';

  const parsedResult =
    block.result !== undefined ? WriteFileResultSchema.safeParse(block.result) : null;
  const result = parsedResult?.success ? parsedResult.data : null;

  return (
    <Box flexDirection="column">
      <Text>
        Writing to <Text bold>{path}</Text>
      </Text>
      {content.length > 0 ? (
        <Box borderStyle="round" borderDimColor paddingX={1} flexDirection="column">
          <Text dimColor>{clip(content, MAX_CONTENT_LINES)}</Text>
        </Box>
      ) : null}
      {result?.error ? <Text color="red">write_file error: {result.error}</Text> : null}
      {result && !result.error && result.tree_view ? <Text>{result.tree_view}</Text> : null}
    </Box>
  );
});
