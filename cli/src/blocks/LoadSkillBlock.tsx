// LoadSkill tool. Renders a single line: `loaded skill: <name|not found>`.
import React from 'react';
import { Box, Text } from 'ink';
import { z } from 'zod';
import type { ToolBlock } from '../state/sessionReducer.js';

export const SkillSchema = z.object({
  name: z.string(),
  description: z.string(),
  content: z.string(),
  requirements: z.array(z.string()).nullish(),
});

export const LoadSkillResultSchema = z.object({ skill: SkillSchema.nullable() });

export const LoadSkillBlock = React.memo(function LoadSkillBlock({ block }: { block: ToolBlock }) {
  const parsed = block.result !== undefined ? LoadSkillResultSchema.safeParse(block.result) : null;

  let label: string;
  if (parsed === null) {
    label = '…'; // call issued, awaiting result
  } else if (!parsed.success || parsed.data.skill === null) {
    label = 'not found';
  } else {
    label = parsed.data.skill.name;
  }

  return (
    <Box>
      <Text>
        loaded skill: <Text bold>{label}</Text>
      </Text>
    </Box>
  );
});
