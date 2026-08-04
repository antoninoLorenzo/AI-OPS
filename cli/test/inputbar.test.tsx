import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import {
  handleInputKey,
  completionsFor,
  emptyInput,
  InputBar,
  type InputState,
  type KeyLike,
} from '../src/components/InputBar.tsx';
import { buildRegistry } from '../src/commands/index.ts';
import { waitFor, waitForFrame } from './helpers.ts';

const registry = buildRegistry();

function press(state: InputState, input: string, key: KeyLike = {}) {
  const completions = completionsFor(state.value, registry);
  return handleInputKey(state, input, key, completions);
}

function type(start: InputState, text: string): InputState {
  let s = start;
  for (const ch of text) s = press(s, ch).state;
  return s;
}

// --- pure key handling ------------------------------------------------------

test('typing inserts characters and advances the cursor', () => {
  const s = type(emptyInput(), 'hello');
  assert.equal(s.value, 'hello');
  assert.equal(s.cursor, 5);
});

test('Enter submits the buffer and clears it', () => {
  const s = type(emptyInput(), 'scan the host');
  const r = press(s, '', { return: true });
  assert.equal(r.submit, 'scan the host');
  assert.equal(r.state.value, '');
  assert.equal(r.state.cursor, 0);
});

test('Shift+Enter inserts a newline instead of submitting', () => {
  const s = type(emptyInput(), 'line1');
  const r = press(s, '', { return: true, shift: true });
  assert.equal(r.submit, undefined);
  assert.equal(r.state.value, 'line1\n');
});

test('Backspace removes the character before the cursor', () => {
  let s = type(emptyInput(), 'abc');
  s = press(s, '', { backspace: true }).state;
  assert.equal(s.value, 'ab');
  assert.equal(s.cursor, 2);
});

test('Left/Right arrows move the cursor and insert happens at the caret', () => {
  let s = type(emptyInput(), 'ac');
  s = press(s, '', { leftArrow: true }).state; // cursor between a and c
  s = press(s, 'b').state;
  assert.equal(s.value, 'abc');
});

test('cursor does not move past the buffer bounds', () => {
  let s = emptyInput();
  s = press(s, '', { leftArrow: true }).state;
  assert.equal(s.cursor, 0);
  s = type(s, 'x');
  s = press(s, '', { rightArrow: true }).state;
  assert.equal(s.cursor, 1);
});

// --- completion -------------------------------------------------------------

test('completionsFor offers commands only while typing the command name', () => {
  assert.deepEqual(completionsFor('/ex', registry).map((d) => d.spec.name), ['exit']);
  assert.deepEqual(completionsFor('/', registry).map((d) => d.spec.name), ['exit', 'stop']);
  assert.deepEqual(completionsFor('/exit ', registry), []); // past the name
  assert.deepEqual(completionsFor('scan', registry), []); // not a command
});

test('Tab completes the highlighted command', () => {
  const s = type(emptyInput(), '/ex');
  const r = press(s, '', { tab: true });
  assert.equal(r.state.value, '/exit ');
  assert.equal(r.state.cursor, 6);
});

test('Up/Down navigate completions within bounds', () => {
  let s = type(emptyInput(), '/'); // both commands offered
  assert.equal(s.selectedIndex, 0);
  s = press(s, '', { downArrow: true }).state;
  assert.equal(s.selectedIndex, 1);
  s = press(s, '', { downArrow: true }).state; // clamp at last
  assert.equal(s.selectedIndex, 1);
  s = press(s, '', { upArrow: true }).state;
  assert.equal(s.selectedIndex, 0);
  s = press(s, '', { upArrow: true }).state; // clamp at first
  assert.equal(s.selectedIndex, 0);
});

test('Enter runs the highlighted command when completing', () => {
  let s = type(emptyInput(), '/'); // offers exit, stop
  s = press(s, '', { downArrow: true }).state; // highlight stop
  const r = press(s, '', { return: true });
  assert.equal(r.submit, '/stop');
});

test('editing the buffer resets the completion highlight', () => {
  let s = type(emptyInput(), '/');
  s = press(s, '', { downArrow: true }).state;
  assert.equal(s.selectedIndex, 1);
  s = press(s, 's').state; // now "/s"
  assert.equal(s.selectedIndex, 0);
});

// --- component integration (printable + submit through stdin) ----------------

test('InputBar submits typed text on Enter via stdin', async () => {
  const submitted: string[] = [];
  const { stdin, lastFrame } = render(
    <InputBar active registry={registry} onSubmit={(v) => submitted.push(v)} />,
  );
  stdin.write('hi there');
  await waitForFrame(lastFrame, /hi there/);
  stdin.write('\r'); // Enter
  await waitFor(() => submitted.length === 1);
  assert.deepEqual(submitted, ['hi there']);
});

test('InputBar shows the completion list when a slash command is typed', async () => {
  const { stdin, lastFrame } = render(<InputBar active registry={registry} onSubmit={() => {}} />);
  stdin.write('/e');
  await waitForFrame(lastFrame, /\/exit/);
  assert.match(lastFrame() ?? '', /close the session/);
});

test('an inactive InputBar ignores keypresses', async () => {
  const submitted: string[] = [];
  const { stdin, lastFrame } = render(
    <InputBar active={false} registry={registry} onSubmit={(v) => submitted.push(v)} />,
  );
  stdin.write('ignored');
  stdin.write('\r');
  // Give any (erroneous) handler a chance to fire, then assert nothing happened.
  await new Promise((r) => setTimeout(r, 50));
  assert.equal(submitted.length, 0);
  assert.doesNotMatch(lastFrame() ?? '', /ignored/);
});
