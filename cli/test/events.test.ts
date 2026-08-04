import test from 'node:test';
import assert from 'node:assert/strict';

import { parseEventLine, EventParseError } from '../src/api/events.ts';

test('parses a user_message event', () => {
  const ev = parseEventLine(JSON.stringify({ kind: 'user_message', content: 'hi' }));
  assert.equal(ev.kind, 'user_message');
  if (ev.kind === 'user_message') assert.equal(ev.content, 'hi');
});

test('parses a text event and applies stream defaults', () => {
  const ev = parseEventLine(JSON.stringify({ kind: 'text', chunk: 'hello' }));
  assert.equal(ev.kind, 'text');
  if (ev.kind === 'text') {
    assert.equal(ev.chunk, 'hello');
    assert.equal(ev.stream, false);
    assert.equal(ev.stream_done, false);
  }
});

test('parses a streamed text event with flags', () => {
  const ev = parseEventLine(JSON.stringify({ kind: 'text', chunk: 'x', stream: true, stream_done: true }));
  assert.equal(ev.kind, 'text');
  if (ev.kind === 'text') {
    assert.equal(ev.stream, true);
    assert.equal(ev.stream_done, true);
  }
});

test('parses a reasoning event', () => {
  const ev = parseEventLine(JSON.stringify({ kind: 'reasoning', chunk: 'thinking' }));
  assert.equal(ev.kind, 'reasoning');
});

test('parses a tool_call event with confirmation default', () => {
  const ev = parseEventLine(
    JSON.stringify({ kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'ls' } }),
  );
  assert.equal(ev.kind, 'tool_call');
  if (ev.kind === 'tool_call') {
    assert.equal(ev.requires_confirmation, false);
    assert.equal((ev.args as { command: string }).command, 'ls');
  }
});

test('parses a tool_call event requiring confirmation', () => {
  const ev = parseEventLine(
    JSON.stringify({
      kind: 'tool_call', call_id: 'c1', name: 'terminal',
      args: { command: 'rm -rf /' }, requires_confirmation: true,
    }),
  );
  if (ev.kind === 'tool_call') assert.equal(ev.requires_confirmation, true);
});

test('parses a tool_result event', () => {
  const ev = parseEventLine(
    JSON.stringify({
      kind: 'tool_result', call_id: 'c1', name: 'terminal',
      args: { command: 'ls' }, result: { session_id: 's', command: 'ls', allowed: true, status: 0 },
    }),
  );
  assert.equal(ev.kind, 'tool_result');
});

test('parses a tool_error event', () => {
  const ev = parseEventLine(
    JSON.stringify({ kind: 'tool_error', failure: 'execution_error', tool_call_id: 'c1', name: 'terminal', error: 'boom' }),
  );
  assert.equal(ev.kind, 'tool_error');
  if (ev.kind === 'tool_error') assert.equal(ev.failure, 'execution_error');
});

test('parses a stop event with defaults', () => {
  const ev = parseEventLine(JSON.stringify({ kind: 'stop', issuer: 'agent' }));
  assert.equal(ev.kind, 'stop');
  if (ev.kind === 'stop') {
    assert.equal(ev.max_iteration, false);
    assert.equal(ev.reason ?? null, null);
  }
});

test('throws EventParseError on invalid JSON', () => {
  assert.throws(() => parseEventLine('{not json'), EventParseError);
});

test('throws EventParseError on unknown kind', () => {
  assert.throws(() => parseEventLine(JSON.stringify({ kind: 'nope' })), EventParseError);
});

test('throws EventParseError when a required field is missing', () => {
  assert.throws(() => parseEventLine(JSON.stringify({ kind: 'text' })), EventParseError);
});

test('throws EventParseError on invalid tool_error failure enum', () => {
  assert.throws(
    () => parseEventLine(JSON.stringify({ kind: 'tool_error', failure: 'weird', tool_call_id: 'c', name: 'n', error: 'e' })),
    EventParseError,
  );
});
