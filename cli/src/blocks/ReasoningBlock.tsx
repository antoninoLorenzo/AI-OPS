// Agent reasoning: hidden by default, revealed by a global toggle. Styled
// dim/italic so it reads as distinct from the final answer. The ThinkTool
// renders its `thought` through this same component so there is no visible
// distinction between streamed reasoning and a think() call.
import React from 'react';
import { Box, Text } from 'ink';

export const ReasoningBlock = React.memo(function ReasoningBlock({
  content,
  revealed,
}: {
  content: string;
  revealed: boolean;
}) {
  if (!revealed) {
    return (
      <Box>
        <Text dimColor italic>
          {'›'} reasoning hidden
        </Text>
      </Box>
    );
  }
  return (
    <Box flexDirection="column">
      <Text dimColor italic>
        {content}
      </Text>
    </Box>
  );
});
