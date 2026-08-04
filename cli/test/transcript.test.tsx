import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { Transcript } from '../src/components/Transcript.tsx';
import { sessionReducer, initialState, type Block, type Action } from '../src/state/sessionReducer.ts';
import type { AnyEvent } from '../src/api/events.ts';

function frame(node: React.ReactElement): string {
  return render(node).lastFrame() ?? '';
}

function build(...actions: Action[]): Block[] {
  return actions.reduce(sessionReducer, initialState()).blocks;
}

const ev = (event: AnyEvent): Action => ({ type: 'EVENT', event });

test('transcript renders a full conversation in order', () => {
  const blocks = build(
    { type: 'SUBMIT_PROMPT', content: 'enumerate the host' },
    { type: 'STREAM_START' },
    ev({ kind: 'reasoning', chunk: 'let me scan' }),
    ev({ kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'nmap host' }, requires_confirmation: false }),
    ev({ kind: 'tool_result', call_id: 'c1', name: 'terminal', args: { command: 'nmap host' }, result: { session_id: 's', command: 'nmap host', allowed: true, status: 0, output: '80/tcp open' } }),
    ev({ kind: 'text', chunk: 'Found a web server.', stream: false, stream_done: false }),
  );

  const f = frame(<Transcript blocks={blocks} reasoningRevealed={false} />);
  assert.match(f, /enumerate the host/);
  assert.match(f, /reasoning hidden/);
  assert.match(f, /\$ nmap host/);
  assert.match(f, /80\/tcp open/);
  assert.match(f, /Found a web server\./);
});

test('transcript reveals reasoning when toggled', () => {
  const blocks = build(ev({ kind: 'reasoning', chunk: 'the secret plan' }));
  assert.doesNotMatch(frame(<Transcript blocks={blocks} reasoningRevealed={false} />), /the secret plan/);
  assert.match(frame(<Transcript blocks={blocks} reasoningRevealed={true} />), /the secret plan/);
});

test('transcript renders an empty conversation without crashing', () => {
  const f = frame(<Transcript blocks={[]} reasoningRevealed={false} />);
  assert.equal(typeof f, 'string');
});

test('transcript renders a client error block', () => {
  const blocks = build({ type: 'STREAM_ERROR', message: 'connection lost' });
  assert.match(frame(<Transcript blocks={blocks} reasoningRevealed={false} />), /connection lost/);
});
