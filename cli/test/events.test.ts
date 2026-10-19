import test from 'node:test';
import assert from 'node:assert/strict';

import { parseEventLine, EventParseError } from '../src/api/events.ts';

test('parses a user_message event', () => {
  const ev = parseEventLine(JSON.stringify({ kind: 'user_message', content: 'hi' }));
  assert.equal(ev.kind, 'user_message');
  if (ev.kind === 'user_message') assert.equal(ev.content, 'hi');
});

test('parses a chat_completion event with content only', () => {
  const ev = parseEventLine(
    JSON.stringify({ kind: 'chat_completion', response_id: 'r1', message: { role: 'assistant', content: 'hello' } }),
  );
  assert.equal(ev.kind, 'chat_completion');
  if (ev.kind === 'chat_completion') {
    assert.equal(ev.message.content, 'hello');
    assert.equal(ev.message.reasoning_content ?? null, null);
  }
});

test('parses a chat_completion event with reasoning_content and tolerates extra message keys', () => {
  const ev = parseEventLine(
    JSON.stringify({
      kind: 'chat_completion',
      response_id: 'r1',
      message: { role: 'assistant', content: 'answer', reasoning_content: 'thinking', tool_calls: [] },
    }),
  );
  assert.equal(ev.kind, 'chat_completion');
  if (ev.kind === 'chat_completion') {
    assert.equal(ev.message.reasoning_content, 'thinking');
    assert.equal(ev.message.content, 'answer');
  }
});

test('parses a chat_completion event with null content and usage', () => {
  const ev = parseEventLine(
    JSON.stringify({
      kind: 'chat_completion',
      response_id: 'r1',
      message: { role: 'assistant', content: null },
      usage: { prompt_tokens: 10, completion_tokens: 5 },
    }),
  );
  assert.equal(ev.kind, 'chat_completion');
  if (ev.kind === 'chat_completion') {
    assert.equal(ev.message.content ?? null, null);
    assert.equal(ev.usage?.prompt_tokens, 10);
    assert.equal(ev.usage?.reasoning_tokens, 0);
  }
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
    JSON.stringify({ kind: 'tool_error', failure: 'execution_error', call_id: 'c1', name: 'terminal', error: 'boom' }),
  );
  assert.equal(ev.kind, 'tool_error');
  if (ev.kind === 'tool_error') {
    assert.equal(ev.failure, 'execution_error');
    assert.equal(ev.call_id, 'c1');
  }
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
  assert.throws(
    () => parseEventLine(JSON.stringify({ kind: 'chat_completion', message: { content: 'x' } })),
    EventParseError,
  );
});

test('throws EventParseError on a dropped legacy event kind', () => {
  assert.throws(() => parseEventLine(JSON.stringify({ kind: 'text', chunk: 'x' })), EventParseError);
});

test('throws EventParseError on invalid tool_error failure enum', () => {
  assert.throws(
    () => parseEventLine(JSON.stringify({ kind: 'tool_error', failure: 'weird', call_id: 'c', name: 'n', error: 'e' })),
    EventParseError,
  );
});
