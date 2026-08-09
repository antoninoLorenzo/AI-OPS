// Bottom status bar: `<model-id> (<provider>) · <MODE> · #<short_id> · <used>/<max>`,
// followed by the global key hints. It renders as the last element of the app so
// that it stays pinned to the bottom of the viewport: the transcript is one
// ever-growing render block, and once it outgrows the terminal only the final
// lines of a frame remain on screen.
//
// Before the agent starts, usage shows `0/<max>` (or `0/?` when the model's
// max context length is unknown).
import React from 'react';
import { Box, Text } from 'ink';
import type { ModelInfo, Mode } from '../state/sessionReducer.js';
import { Spinner } from './Spinner.js';

// Humanizes a token count: 1234 -> "1.2k", 8000 -> "8k", 2_000_000 -> "2M".
export function humanizeTokens(n: number): string {
  if (n < 1000) return String(n);
  if (n < 1_000_000) return formatUnit(n / 1000, 'k');
  return formatUnit(n / 1_000_000, 'M');
}

function formatUnit(value: number, suffix: string): string {
  const rounded = Math.round(value * 10) / 10;
  const text = Number.isInteger(rounded) ? String(rounded) : rounded.toFixed(1);
  return `${text}${suffix}`;
}

function usageText(totalTokens: number, maxContextLength: number | null): string {
  const used = humanizeTokens(totalTokens);
  const max = maxContextLength === null ? '?' : humanizeTokens(maxContextLength);
  return `${used}/${max}`;
}

const SEP = ' · ';

// Global chords, shown inline so the bar is the only fixed chrome on screen.
const HINTS = 'ctrl+r reasoning';

export const StatusBar = React.memo(function StatusBar({
  model,
  mode,
  shortId,
  totalTokens,
  running = false,
}: {
  model: ModelInfo | null;
  mode: Mode;
  shortId: number | null;
  totalTokens: number;
  // The agent is working. False while it waits on a confirmation, where the
  // form already says so and nothing is progressing.
  running?: boolean;
}) {
  const modelLabel = model ? `${model.modelId} (${model.provider})` : '…';
  const usage = usageText(totalTokens, model ? model.maxContextLength : null);
  const shortIdLabel = shortId === null ? '#—' : `#${shortId}`;

  return (
    <Box>
      <Text>
        {running ? (
          <Text>
            <Spinner active />
            <Text dimColor> running</Text>
            {SEP}
          </Text>
        ) : null}
        <Text bold>{modelLabel}</Text>
        {SEP}
        <Text color="yellow">{mode.toUpperCase()}</Text>
        {SEP}
        {shortIdLabel}
        {SEP}
        <Text dimColor>{usage}</Text>
        <Text dimColor>{'   '}{HINTS}</Text>
      </Text>
    </Box>
  );
});
