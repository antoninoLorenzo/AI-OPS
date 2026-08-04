import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { ConfirmationForm } from '../src/components/ConfirmationForm.tsx';
import { Completion } from '../src/components/Completion.tsx';
import { buildRegistry } from '../src/commands/index.ts';
import { pressUntil } from './helpers.ts';

test('confirmation form renders the label and y/n hint', () => {
  const { lastFrame } = render(
    <ConfirmationForm active label="terminal $ rm -rf /etc" onApprove={() => {}} onReject={() => {}} />,
  );
  const f = lastFrame() ?? '';
  assert.match(f, /confirm/);
  assert.match(f, /terminal \$ rm -rf \/etc/);
  assert.match(f, /approve/);
  assert.match(f, /reject/);
});

test('pressing y approves and n rejects', async () => {
  let approved = 0;
  let rejected = 0;
  const { stdin, rerender } = render(
    <ConfirmationForm active label="x" onApprove={() => (approved += 1)} onReject={() => (rejected += 1)} />,
  );
  await pressUntil(stdin, 'y', () => approved === 1);

  rerender(
    <ConfirmationForm active label="x" onApprove={() => (approved += 1)} onReject={() => (rejected += 1)} />,
  );
  await pressUntil(stdin, 'n', () => rejected === 1);
});

test('an inactive confirmation form ignores keypresses', async () => {
  let approved = 0;
  const { stdin } = render(
    <ConfirmationForm active={false} label="x" onApprove={() => (approved += 1)} onReject={() => {}} />,
  );
  stdin.write('y');
  await new Promise((r) => setTimeout(r, 50));
  assert.equal(approved, 0);
});

test('confirmation form shows a queued-count hint when more are pending', () => {
  const { lastFrame } = render(
    <ConfirmationForm active label="x" pendingCount={3} onApprove={() => {}} onReject={() => {}} />,
  );
  assert.match(lastFrame() ?? '', /\+2 more queued/);
});

// --- Completion (presentational) --------------------------------------------

test('completion highlights the selected entry and lists descriptions', () => {
  const matches = buildRegistry().all();
  const { lastFrame } = render(<Completion matches={matches} selectedIndex={1} />);
  const f = lastFrame() ?? '';
  assert.match(f, /\/exit/);
  assert.match(f, /\/stop/);
  assert.match(f, /stop the running agent/);
  // The selected row (index 1 -> stop) carries the highlight marker.
  const stopLine = (f.split('\n').find((l) => l.includes('/stop')) ?? '');
  assert.match(stopLine, /▸/);
});
