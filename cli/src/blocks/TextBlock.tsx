// Final assistant answer. Streamed blocks show a trailing cursor while still
// in progress; finalized blocks render as plain text.
import React from 'react';
import { Box, Text } from 'ink';
import type { TextBlock as TextBlockData } from '../state/sessionReducer.js';

export const TextBlock = React.memo(function TextBlock({ block }: { block: TextBlockData }) {
  return (
    <Box>
      <Text>
        {block.content}
        {block.streaming ? <Text dimColor>▋</Text> : null}
      </Text>
    </Box>
  );
});
