// Terminal tool. Renders a shell-like block:
//   issued:    ○ $ <command>
//   completed: ● $ <command>  (green status 0, red status >0, empty -1, yellow timed_out)
//              <output>
//   blocked:   ● [BLOCKED] $ <command>   (yellow)
// Output is never truncated; it lives in a height-capped, scrollable box.
import React from 'react';
import { Box, Text } from 'ink';
import { ScrollView } from 'ink-scroll-view';
import { z } from 'zod';
import type { ToolBlock } from '../state/sessionReducer.js';

export const TerminalArgsSchema = z.object({
  command: z.string(),
  session_id: z.string().nullish(),
  interactive: z.boolean().nullish(),
  timeout: z.number().nullish(),
});

// CommandStatus serializes to its int value (-1, 0, 1, 126, 127, 130, 137) or null.
export const TerminalResultSchema = z.object({
  session_id: z.string(),
  command: z.string(),
  allowed: z.boolean(),
  output: z.string().nullish(),
  status: z.number().nullish(),
  timed_out: z.boolean().default(false),
});

export type TerminalResult = z.infer<typeof TerminalResultSchema>;

const MAX_OUTPUT_HEIGHT = 12;

export type CircleColor = 'green' | 'red' | 'yellow' | 'empty';

export function statusCircle(result: TerminalResult): CircleColor {
  if (result.timed_out) return 'yellow';
  if (result.status === 0) return 'green';
  if (typeof result.status === 'number' && result.status > 0) return 'red';
  return 'empty'; // -1 (unknown) or null
}

function Circle({ color }: { color: CircleColor }) {
  if (color === 'empty') return <Text dimColor>{'○'}</Text>;
  return <Text color={color}>{'●'}</Text>;
}

export const TerminalBlock = React.memo(function TerminalBlock({ block }: { block: ToolBlock }) {
  const parsedArgs = TerminalArgsSchema.safeParse(block.args);
  const command = parsedArgs.success ? parsedArgs.data.command : JSON.stringify(block.args);

  // Issued (no result yet): empty circle, command only.
  if (block.result === undefined) {
    return (
      <Box>
        <Circle color="empty" />
        <Text> $ {command}</Text>
      </Box>
    );
  }

  const parsedResult = TerminalResultSchema.safeParse(block.result);
  // Malformed result: fall back to showing the command with an empty marker.
  if (!parsedResult.success) {
    return (
      <Box>
        <Circle color="empty" />
        <Text> $ {command}</Text>
      </Box>
    );
  }
  const result = parsedResult.data;

  // Blocked by policy (or a confirmation the user rejected / that timed out).
  if (!result.allowed) {
    return (
      <Box>
        <Circle color="yellow" />
        <Text> [BLOCKED] $ {command}</Text>
      </Box>
    );
  }

  const output = result.output ?? '';
  const lineCount = output.length === 0 ? 0 : output.split('\n').length;

  return (
    <Box flexDirection="column">
      <Box>
        <Circle color={statusCircle(result)} />
        <Text> $ {command}</Text>
      </Box>
      {output.length > 0 ? (
        <Box
          borderStyle="round"
          borderDimColor
          paddingX={1}
          height={Math.min(lineCount, MAX_OUTPUT_HEIGHT) + 2}
        >
          <ScrollView>
            <Text>{output}</Text>
          </ScrollView>
        </Box>
      ) : null}
    </Box>
  );
});
