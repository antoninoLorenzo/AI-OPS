// Presentational command-completion list. Purely display: the InputBar owns all
// keypresses (typing, Tab, Up/Down, Enter). The first result is highlighted by
// default; `selectedIndex` marks the current highlight.
import React from 'react';
import { Box, Text } from 'ink';
import type { CommandDefinition } from '../commands/registry.js';

function usage(def: CommandDefinition): string {
  const params = def.spec.params.map((p) => (p.required ? `<${p.name}>` : `[${p.name}]`)).join(' ');
  return params ? `/${def.spec.name} ${params}` : `/${def.spec.name}`;
}

export const Completion = React.memo(function Completion({
  matches,
  selectedIndex,
}: {
  matches: CommandDefinition[];
  selectedIndex: number;
}) {
  return (
    <Box flexDirection="column" borderStyle="round" borderDimColor paddingX={1}>
      {matches.map((def, i) => {
        const selected = i === selectedIndex;
        return (
          <Text key={def.spec.name} inverse={selected}>
            {selected ? '▸ ' : '  '}
            <Text bold>{usage(def).padEnd(16)}</Text>
            <Text dimColor>{def.spec.description}</Text>
          </Text>
        );
      })}
    </Box>
  );
});
