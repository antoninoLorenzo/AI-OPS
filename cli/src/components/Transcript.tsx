// The scrolling conversation pane: a dynamic list of block components, one per
// reducer block. Each block is rendered through the memoized BlockView, so a
// block whose identity the reducer preserved is not re-rendered when an
// unrelated block changes.
import React from 'react';
import { Box } from 'ink';
import type { Block } from '../state/sessionReducer.js';
import { BlockView } from '../blocks/BlockView.js';

export const Transcript = React.memo(function Transcript({
  blocks,
  reasoningRevealed,
}: {
  blocks: Block[];
  reasoningRevealed: boolean;
}) {
  return (
    <Box flexDirection="column">
      {blocks.map((block) => (
        <Box key={block.id} marginBottom={1}>
          <BlockView block={block} reasoningRevealed={reasoningRevealed} />
        </Box>
      ))}
    </Box>
  );
});
