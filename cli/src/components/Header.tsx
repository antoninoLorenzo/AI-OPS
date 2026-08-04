// Header line: `<model-id> (<provider>) · <MODE> · #<short_id> · <used>/<max>`.
// Before the agent starts, usage shows `0/<max>` (or `0/?` when the model's
// max context length is unknown).
import React from 'react';
import { Box, Text } from 'ink';
import type { ModelInfo, Mode } from '../state/sessionReducer.js';

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

export const Header = React.memo(function Header({
  model,
  mode,
  shortId,
  totalTokens,
}: {
  model: ModelInfo | null;
  mode: Mode;
  shortId: number | null;
  totalTokens: number;
}) {
  const modelLabel = model ? `${model.modelId} (${model.provider})` : '…';
  const usage = usageText(totalTokens, model ? model.maxContextLength : null);
  const shortIdLabel = shortId === null ? '#—' : `#${shortId}`;

  return (
    <Box borderStyle="single" borderDimColor paddingX={1}>
      <Text>
        <Text bold>{modelLabel}</Text>
        {SEP}
        <Text color="yellow">{mode.toUpperCase()}</Text>
        {SEP}
        {shortIdLabel}
        {SEP}
        <Text dimColor>{usage}</Text>
      </Text>
    </Box>
  );
});
