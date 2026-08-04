// y/n confirmation form shown in place of the input while a tool call awaits
// the user's decision. Hand-rolled with useInput (the reducer arbitrates focus
// via inputMode==='confirmation', so only this receives keys while shown).
import React from 'react';
import { Box, Text, useInput } from 'ink';

export function ConfirmationForm({
  active,
  label,
  pendingCount = 1,
  onApprove,
  onReject,
}: {
  active: boolean;
  label: string;
  pendingCount?: number;
  onApprove: () => void;
  onReject: () => void;
}) {
  useInput(
    (input) => {
      const ch = input.toLowerCase();
      if (ch === 'y') onApprove();
      else if (ch === 'n') onReject();
    },
    { isActive: active },
  );

  return (
    <Box flexDirection="column" borderStyle="round" borderColor="yellow" paddingX={1}>
      <Text>
        <Text color="yellow" bold>
          confirm
        </Text>{' '}
        {label}
      </Text>
      <Text>
        <Text bold>y</Text>
        <Text dimColor> approve · </Text>
        <Text bold>n</Text>
        <Text dimColor> reject</Text>
        {pendingCount > 1 ? <Text dimColor>{`  (+${pendingCount - 1} more queued)`}</Text> : null}
      </Text>
    </Box>
  );
}
