import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { Transcript } from '../src/components/Transcript.tsx';
import {
  sessionReducer,
  initialState,
  settledCount,
  type SessionState,
  type Action,
} from '../src/state/sessionReducer.ts';
import type { AnyEvent } from '../src/api/events.ts';

function build(...actions: Action[]): SessionState {
  return actions.reduce(sessionReducer, initialState());
}

// Renders a state the way App does: settled prefix to <Static>, rest live.
// ink-testing-library renders in debug mode, where each frame is written as
// `fullStaticOutput + output`, so a frame covers both regions.
function frame(state: SessionState, reasoningRevealed = false): string {
  return (
    render(
      <Transcript
        blocks={state.blocks}
        settled={settledCount(state)}
        reasoningRevealed={reasoningRevealed}
        replayKey={reasoningRevealed ? 'revealed' : 'hidden'}
      />,
    ).lastFrame() ?? ''
  );
}

const ev = (event: AnyEvent): Action => ({ type: 'EVENT', event });

test('transcript renders a full conversation in order', () => {
  const state = build(
    { type: 'SUBMIT_PROMPT', content: 'enumerate the host' },
    { type: 'STREAM_START' },
    ev({ kind: 'reasoning', chunk: 'let me scan' }),
    ev({ kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'nmap host' }, requires_confirmation: false }),
    ev({ kind: 'tool_result', call_id: 'c1', name: 'terminal', args: { command: 'nmap host' }, result: { session_id: 's', command: 'nmap host', allowed: true, status: 0, output: '80/tcp open' } }),
    ev({ kind: 'text', chunk: 'Found a web server.', stream: false, stream_done: false }),
  );

  const f = frame(state);
  assert.match(f, /enumerate the host/);
  assert.match(f, /reasoning hidden/);
  assert.match(f, /\$ nmap host/);
  assert.match(f, /80\/tcp open/);
  assert.match(f, /Found a web server\./);
});

test('transcript reveals reasoning when toggled', () => {
  const state = build(ev({ kind: 'reasoning', chunk: 'the secret plan' }));
  assert.doesNotMatch(frame(state, false), /the secret plan/);
  assert.match(frame(state, true), /the secret plan/);
});

test('transcript renders an empty conversation without crashing', () => {
  assert.equal(typeof frame(build()), 'string');
});

test('transcript renders a client error block', () => {
  assert.match(frame(build({ type: 'STREAM_ERROR', message: 'connection lost' })), /connection lost/);
});

// The split itself: a block still in the live region must keep rendering its
// updates, and a block handed to <Static> must already be in its final form.
test('a settled block and a live block both render', () => {
  const state = build(
    { type: 'SUBMIT_PROMPT', content: 'first' },
    { type: 'STREAM_START' },
    ev({ kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'sleep 30' }, requires_confirmation: false }),
  );
  // The user block is settled; the tool call is still pending, so it is live.
  assert.equal(settledCount(state), 1);
  const f = frame(state);
  assert.match(f, /first/);
  assert.match(f, /\$ sleep 30/);
});

test('a tool block moves into the settled region once its result arrives', () => {
  const pending = build(
    { type: 'STREAM_START' },
    ev({ kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'id' }, requires_confirmation: false }),
  );
  assert.equal(settledCount(pending), 0, 'a pending tool call can still change');

  const done = sessionReducer(
    pending,
    ev({ kind: 'tool_result', call_id: 'c1', name: 'terminal', args: { command: 'id' }, result: { session_id: 's', command: 'id', allowed: true, status: 0, output: 'uid=0' } }),
  );
  assert.equal(settledCount(done), 1, 'a completed tool call is final');
  assert.match(frame(done), /uid=0/);
});
