// Dispatches any transcript block to its renderer by `block.type`. User, stop
// and client-error blocks are small enough to render inline here; the richer
// tool and content blocks live in their own files. Wrapped in React.memo so a
// block whose reference did not change is not re-rendered.
import React from 'react';
import { Box, Text } from 'ink';
import type { Block } from '../state/sessionReducer.js';
import { TextBlock } from './TextBlock.js';
import { ReasoningBlock } from './ReasoningBlock.js';
import { ToolBlockView } from './ToolBlockView.js';

function UserBlockView({ content }: { content: string }) {
  return (
    <Box>
      <Text color="cyan">{'> '}</Text>
      <Text>{content}</Text>
    </Box>
  );
}

function StopBlockView({
  issuer,
  reason,
  error,
  maxIteration,
}: {
  issuer: 'agent' | 'user';
  reason: string | null;
  error: string | null;
  maxIteration: boolean;
}) {
  if (error) {
    return <Text color="red">■ stopped: {error}</Text>;
  }
  const parts: string[] = [];
  if (issuer === 'user') parts.push('stopped by user');
  else parts.push('done');
  if (maxIteration) parts.push('max iterations reached');
  if (reason) parts.push(reason);
  return <Text dimColor>■ {parts.join(' · ')}</Text>;
}

function ErrorBlockView({ message }: { message: string }) {
  return <Text color="red">✗ {message}</Text>;
}

export const BlockView = React.memo(function BlockView({
  block,
  reasoningRevealed,
}: {
  block: Block;
  reasoningRevealed: boolean;
}) {
  switch (block.type) {
    case 'user':
      return <UserBlockView content={block.content} />;
    case 'text':
      return <TextBlock block={block} />;
    case 'reasoning':
      return <ReasoningBlock content={block.content} revealed={reasoningRevealed} />;
    case 'tool':
      return <ToolBlockView block={block} reasoningRevealed={reasoningRevealed} />;
    case 'stop':
      return (
        <StopBlockView
          issuer={block.issuer}
          reason={block.reason}
          error={block.error}
          maxIteration={block.maxIteration}
        />
      );
    case 'error':
      return <ErrorBlockView message={block.message} />;
    default: {
      const _never: never = block;
      return _never;
    }
  }
});
