// Fallback tool renderer: shows the tool name and its JSON args/result. Used
// for any tool without a dedicated renderer.
import React from 'react';
import { Box, Text } from 'ink';
import type { ToolBlock } from '../state/sessionReducer.js';

function pretty(value: unknown): string {
  try {
    return JSON.stringify(value, null, 2);
  } catch {
    return String(value);
  }
}

export const GenericToolBlock = React.memo(function GenericToolBlock({ block }: { block: ToolBlock }) {
  return (
    <Box flexDirection="column">
      <Text bold>{block.name}</Text>
      <Text dimColor>args: {pretty(block.args)}</Text>
      {block.result !== undefined ? <Text>result: {pretty(block.result)}</Text> : null}
    </Box>
  );
});
