// The conversation pane, split into two regions.
//
// Settled blocks go through Ink's <Static>: each is written to the terminal
// exactly once, as ordinary scrollback, and then drops out of the live frame
// entirely. Only the tail the reducer can still mutate stays live.
//
// This split is what keeps the client responsive. Ink repaints its whole frame
// into a string on every update and rewrites every line of it (log-update
// erases the previous frame and writes the new one), so a single live
// transcript makes the cost of every streamed chunk proportional to the entire
// session. Worse, once the frame is taller than the window Ink falls back to
// clearing the terminal (scrollback included) on each frame. With the settled
// region in <Static> the live frame stays a few lines tall and neither happens.
//
// The cost of that guarantee: written output cannot be changed. Toggling
// reasoning visibility therefore remounts <Static> via `replayKey`, which
// replays the transcript at the new visibility (App clears the screen first).
import React from 'react';
import { Box, Static } from 'ink';
import type { Block } from '../state/sessionReducer.js';
import { BlockView } from '../blocks/BlockView.js';

export const Transcript = React.memo(function Transcript({
  blocks,
  settled,
  reasoningRevealed,
  replayKey,
}: {
  blocks: Block[];
  // Number of leading blocks that can no longer change (see `settledCount`).
  settled: number;
  reasoningRevealed: boolean;
  // Changing this remounts <Static> and replays every settled block.
  replayKey: string;
}) {
  const settledBlocks = blocks.slice(0, settled);
  const liveBlocks = blocks.slice(settled);

  return (
    <>
      <Static key={replayKey} items={settledBlocks}>
        {(block) => (
          <Box key={block.id} marginBottom={1}>
            <BlockView block={block} reasoningRevealed={reasoningRevealed} />
          </Box>
        )}
      </Static>
      <Box flexDirection="column">
        {liveBlocks.map((block) => (
          <Box key={block.id} marginBottom={1}>
            <BlockView block={block} reasoningRevealed={reasoningRevealed} />
          </Box>
        ))}
      </Box>
    </>
  );
});
