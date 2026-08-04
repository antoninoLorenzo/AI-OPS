// Dispatches a tool block to its dedicated renderer by tool name. Tool errors
// are rendered uniformly across tools; a confirmation still awaiting the user
// shows a marker until the form is answered.
import React from 'react';
import { Box, Text } from 'ink';
import { z } from 'zod';
import type { ToolBlock } from '../state/sessionReducer.js';
import { TerminalBlock } from './TerminalBlock.js';
import { LoadSkillBlock } from './LoadSkillBlock.js';
import { WriteFileBlock } from './WriteFileBlock.js';
import { WhiteboardBlock } from './WhiteboardBlock.js';
import { GenericToolBlock } from './GenericToolBlock.js';
import { ReasoningBlock } from './ReasoningBlock.js';

export const ToolName = {
  Terminal: 'terminal',
  LoadSkill: 'load_skill',
  Think: 'think',
  WriteFile: 'write_file',
  WriteWhiteboard: 'write_whiteboard',
  ReadWhiteboard: 'read_whiteboard',
} as const;

const ThinkArgsSchema = z.object({ thought: z.string() });

// Common error rendering shared by every tool.
function ToolError({ block }: { block: ToolBlock }) {
  return (
    <Box>
      <Text color="red">
        ✗ {block.name} {block.error?.failure}: {block.error?.message}
      </Text>
    </Box>
  );
}

export const ToolBlockView = React.memo(function ToolBlockView({
  block,
  reasoningRevealed,
  whiteboardExpanded = false,
}: {
  block: ToolBlock;
  reasoningRevealed: boolean;
  whiteboardExpanded?: boolean;
}) {
  if (block.status === 'error') {
    return <ToolError block={block} />;
  }

  switch (block.name) {
    case ToolName.Terminal:
      return <TerminalBlock block={block} />;
    case ToolName.LoadSkill:
      return <LoadSkillBlock block={block} />;
    case ToolName.WriteFile:
      return <WriteFileBlock block={block} />;
    case ToolName.WriteWhiteboard:
    case ToolName.ReadWhiteboard:
      return <WhiteboardBlock block={block} expanded={whiteboardExpanded} />;
    case ToolName.Think: {
      // Think renders its thought exactly like agent reasoning.
      const parsed = ThinkArgsSchema.safeParse(block.args);
      const thought = parsed.success ? parsed.data.thought : JSON.stringify(block.args);
      return <ReasoningBlock content={thought} revealed={reasoningRevealed} />;
    }
    default:
      return <GenericToolBlock block={block} />;
  }
});
