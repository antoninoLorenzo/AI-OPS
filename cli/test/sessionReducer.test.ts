import test from 'node:test';
import assert from 'node:assert/strict';

import {
  sessionReducer,
  initialState,
  isRunning,
  canSubmitPrompt,
  activeConfirmation,
  settledCount,
  type SessionState,
  type Action,
  type Block,
  type ToolBlock,
  type TextBlock,
} from '../src/state/sessionReducer.ts';
import type { AnyEvent } from '../src/api/events.ts';

// --- helpers ----------------------------------------------------------------

function run(state: SessionState, ...actions: Action[]): SessionState {
  return actions.reduce(sessionReducer, state);
}

function ev(event: AnyEvent): Action {
  return { type: 'EVENT', event };
}

const text = (chunk: string, stream = false, stream_done = false): AnyEvent => ({
  kind: 'text', chunk, stream, stream_done,
});
const reasoning = (chunk: string): AnyEvent => ({ kind: 'reasoning', chunk });
const toolCall = (call_id: string, name: string, args: Record<string, unknown>, requires = false): AnyEvent => ({
  kind: 'tool_call', call_id, name, args, requires_confirmation: requires,
});
const toolResult = (call_id: string, name: string, result: Record<string, unknown>): AnyEvent => ({
  kind: 'tool_result', call_id, name, args: {}, result,
});
const toolError = (tool_call_id: string, name: string, failure: 'validation_error' | 'execution_error', error: string): AnyEvent => ({
  kind: 'tool_error', tool_call_id, name, failure, error,
});
const stop = (issuer: 'agent' | 'user', extra: Partial<{ reason: string; error: string; max_iteration: boolean }> = {}): AnyEvent => ({
  kind: 'stop', issuer, reason: extra.reason ?? null, error: extra.error ?? null, max_iteration: extra.max_iteration ?? false,
});

function tools(state: SessionState): ToolBlock[] {
  return state.blocks.filter((b): b is ToolBlock => b.type === 'tool');
}

// --- status bar / model / usage -------------------------------------------------

test('SET_MODEL and SET_SESSION populate status bar fields', () => {
  const s = run(initialState('unsupervised'),
    { type: 'SET_MODEL', model: { provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8192 } },
    { type: 'SET_SESSION', shortId: 3, mode: 'unsupervised' },
  );
  assert.equal(s.model?.modelId, 'gpt-4o');
  assert.equal(s.shortId, 3);
  assert.equal(s.mode, 'unsupervised');
});

test('SET_USAGE updates total tokens', () => {
  const s = run(initialState(), { type: 'SET_USAGE', totalTokens: 1234 });
  assert.equal(s.totalTokens, 1234);
});

// --- status transitions -----------------------------------------------------

test('STREAM_START moves idle -> running and clears prior error', () => {
  const s = run(initialState(), { type: 'STREAM_START' });
  assert.equal(s.status, 'running');
  assert.equal(s.error, null);
  assert.ok(isRunning(s));
});

test('StopEvent moves running -> stopped', () => {
  const s = run(initialState(), { type: 'STREAM_START' }, ev(stop('agent')));
  assert.equal(s.status, 'stopped');
  assert.equal(isRunning(s), false);
});

test('StopEvent with fatal error moves to error status', () => {
  const s = run(initialState(), { type: 'STREAM_START' }, ev(stop('agent', { error: 'boom' })));
  assert.equal(s.status, 'error');
  assert.equal(s.error, 'boom');
});

test('STREAM_ERROR appends an error block and resets transient state', () => {
  const s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
    { type: 'STREAM_ERROR', message: 'connection lost' },
  );
  assert.equal(s.status, 'error');
  assert.equal(s.pendingToolCalls, 0);
  assert.equal(s.enqueuedMessage, false);
  const last = s.blocks[s.blocks.length - 1];
  assert.equal(last.type, 'error');
  assert.equal(last.type === 'error' && last.message, 'connection lost');
});

// --- text accumulation ------------------------------------------------------

test('non-streamed text renders as one finalized block', () => {
  const s = run(initialState(), ev(text('hello world')));
  const b = s.blocks[0] as TextBlock;
  assert.equal(b.type, 'text');
  assert.equal(b.content, 'hello world');
  assert.equal(b.streaming, false);
  assert.equal(s.openTextId, null);
});

test('streamed text chunks append to a single block and finalize on stream_done', () => {
  let s = run(initialState(), ev(text('he', true)));
  assert.equal(s.openTextId, (s.blocks[0] as TextBlock).id);
  assert.equal((s.blocks[0] as TextBlock).streaming, true);
  s = run(s, ev(text('llo', true)));
  s = run(s, ev(text('!', true, true)));
  assert.equal(s.blocks.length, 1);
  const b = s.blocks[0] as TextBlock;
  assert.equal(b.content, 'hello!');
  assert.equal(b.streaming, false);
  assert.equal(s.openTextId, null);
});

test('a reasoning event finalizes an open streaming text block', () => {
  let s = run(initialState(), ev(text('partial', true)));
  s = run(s, ev(reasoning('hmm')));
  assert.equal((s.blocks[0] as TextBlock).streaming, false);
  assert.equal(s.openTextId, null);
  assert.equal(s.blocks[1].type, 'reasoning');
});

// --- reasoning accumulation -------------------------------------------------

test('consecutive reasoning events accumulate into one block', () => {
  let s = run(initialState(), ev(reasoning('step 1. ')), ev(reasoning('step 2.')));
  const reasoningBlocks = s.blocks.filter((b) => b.type === 'reasoning');
  assert.equal(reasoningBlocks.length, 1);
  assert.equal((reasoningBlocks[0] as { content: string }).content, 'step 1. step 2.');
});

test('a text event ends reasoning accumulation', () => {
  let s = run(initialState(), ev(reasoning('thinking')), ev(text('answer')));
  assert.equal(s.openReasoningId, null);
  assert.equal(s.blocks.length, 2);
  assert.equal(s.blocks[0].type, 'reasoning');
  assert.equal(s.blocks[1].type, 'text');
});

// --- tool call / result correlation -----------------------------------------

test('tool_result attaches to the matching tool_call by call_id', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
  );
  assert.equal(s.pendingToolCalls, 1);
  assert.equal(tools(s)[0].status, 'pending');

  s = run(s, ev(toolResult('c1', 'terminal', { session_id: 's', command: 'ls', allowed: true, status: 0, output: 'f' })));
  assert.equal(s.pendingToolCalls, 0);
  const t = tools(s)[0];
  assert.equal(t.status, 'done');
  assert.equal((t.result as { output: string }).output, 'f');
});

test('tool_error attaches error to the matching tool_call', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
    ev(toolError('c1', 'terminal', 'execution_error', 'exploded')),
  );
  const t = tools(s)[0];
  assert.equal(t.status, 'error');
  assert.equal(t.error?.failure, 'execution_error');
  assert.equal(t.error?.message, 'exploded');
  assert.equal(s.pendingToolCalls, 0);
});

test('two tool calls track pending count independently', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
    ev(toolCall('c2', 'terminal', { command: 'pwd' })),
  );
  assert.equal(s.pendingToolCalls, 2);
  s = run(s, ev(toolResult('c1', 'terminal', { session_id: 's', command: 'ls', allowed: true, status: 0 })));
  assert.equal(s.pendingToolCalls, 1);
  s = run(s, ev(toolResult('c2', 'terminal', { session_id: 's', command: 'pwd', allowed: true, status: 0 })));
  assert.equal(s.pendingToolCalls, 0);
});

// --- confirmation flow ------------------------------------------------------

test('a confirmation-required tool_call enters awaiting-confirmation and grabs focus', () => {
  const s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm -rf /' }, true)),
  );
  assert.equal(s.status, 'awaiting-confirmation');
  assert.equal(s.inputMode, 'confirmation');
  assert.equal(activeConfirmation(s), 'c1');
  assert.equal(tools(s)[0].status, 'awaiting-confirmation');
});

test('CONFIRMATION_SENT returns focus to input and resumes running', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm -rf /' }, true)),
    { type: 'CONFIRMATION_SENT', callId: 'c1', approved: true },
  );
  assert.equal(s.status, 'running');
  assert.equal(s.inputMode, 'input');
  assert.equal(activeConfirmation(s), null);
  assert.equal(tools(s)[0].status, 'pending');
  assert.equal(s.acknowledged['c1'], true);
});

test('acknowledged confirmation result is marked done, not timed out', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'nmap x' }, true)),
    { type: 'CONFIRMATION_SENT', callId: 'c1', approved: true },
    ev(toolResult('c1', 'terminal', { session_id: 's', command: 'nmap x', allowed: true, status: 0 })),
  );
  assert.equal(tools(s)[0].status, 'done');
});

test('unacknowledged confirmation result is labeled rejected-timeout', () => {
  // A result arrives for a confirmation-required call the user never answered.
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm -rf /' }, true)),
    ev(toolResult('c1', 'terminal', { session_id: 's', command: 'rm -rf /', allowed: false })),
  );
  assert.equal(tools(s)[0].status, 'rejected-timeout');
});

test('a non-confirmation result is never labeled rejected-timeout', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' }, false)),
    ev(toolResult('c1', 'terminal', { session_id: 's', command: 'ls', allowed: true, status: 0 })),
  );
  assert.equal(tools(s)[0].status, 'done');
});

// --- multiple confirmations (queue) -----------------------------------------

test('two confirmation-required calls queue in order of arrival', () => {
  const s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm a' }, true)),
    ev(toolCall('c2', 'terminal', { command: 'rm b' }, true)),
  );
  assert.equal(s.status, 'awaiting-confirmation');
  assert.equal(s.inputMode, 'confirmation');
  assert.deepEqual(s.confirmationQueue, ['c1', 'c2']);
  // The head (first to arrive) is shown; both tool blocks are awaiting.
  assert.equal(activeConfirmation(s), 'c1');
  assert.equal(tools(s)[0].status, 'awaiting-confirmation');
  assert.equal(tools(s)[1].status, 'awaiting-confirmation');
});

test('answering the head advances to the next queued confirmation', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm a' }, true)),
    ev(toolCall('c2', 'terminal', { command: 'rm b' }, true)),
    { type: 'CONFIRMATION_SENT', callId: 'c1', approved: true },
  );
  // Still blocked on the user for the second one.
  assert.equal(s.status, 'awaiting-confirmation');
  assert.equal(s.inputMode, 'confirmation');
  assert.equal(activeConfirmation(s), 'c2');
  assert.equal(tools(s)[0].status, 'pending'); // c1 proceeding
  assert.equal(tools(s)[1].status, 'awaiting-confirmation'); // c2 still waiting

  s = run(s, { type: 'CONFIRMATION_SENT', callId: 'c2', approved: false });
  assert.equal(s.status, 'running');
  assert.equal(s.inputMode, 'input');
  assert.equal(activeConfirmation(s), null);
  assert.deepEqual(s.confirmationQueue, []);
});

test('a backend-timeout result for the head advances the queue without user input', () => {
  // c1 times out server-side: its result arrives while c1 is the active form.
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm a' }, true)),
    ev(toolCall('c2', 'terminal', { command: 'rm b' }, true)),
    ev(toolResult('c1', 'terminal', { session_id: 's', command: 'rm a', allowed: false })),
  );
  // c1 is dropped from the queue and labeled rejected-timeout; c2 now shown.
  assert.equal(tools(s)[0].status, 'rejected-timeout');
  assert.equal(activeConfirmation(s), 'c2');
  assert.equal(s.status, 'awaiting-confirmation');
  assert.equal(s.inputMode, 'confirmation');

  // Then c2 also times out: queue empties, focus returns to the input.
  s = run(s, ev(toolResult('c2', 'terminal', { session_id: 's', command: 'rm b', allowed: false })));
  assert.equal(tools(s)[1].status, 'rejected-timeout');
  assert.equal(activeConfirmation(s), null);
  assert.equal(s.status, 'running');
  assert.equal(s.inputMode, 'input');
});

test('a result for the head clears the form even without a second queued call', () => {
  // Regression: a lone confirmation that times out server-side must not leave
  // the UI stuck in confirmation mode.
  const s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm a' }, true)),
    ev(toolResult('c1', 'terminal', { session_id: 's', command: 'rm a', allowed: false })),
  );
  assert.equal(tools(s)[0].status, 'rejected-timeout');
  assert.equal(s.inputMode, 'input');
  assert.equal(s.status, 'running');
  assert.deepEqual(s.confirmationQueue, []);
});

test('a tool_error for a queued confirmation also advances the queue', () => {
  const s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm a' }, true)),
    ev(toolCall('c2', 'terminal', { command: 'rm b' }, true)),
    ev(toolError('c1', 'terminal', 'execution_error', 'died')),
  );
  assert.equal(tools(s)[0].status, 'error');
  assert.equal(activeConfirmation(s), 'c2');
  assert.equal(s.inputMode, 'confirmation');
});

test('answering out of order removes the specific call from the queue', () => {
  // Defensive: if a confirmation for a non-head call arrives, that call is
  // removed and the remaining head stays active.
  const s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm a' }, true)),
    ev(toolCall('c2', 'terminal', { command: 'rm b' }, true)),
    { type: 'CONFIRMATION_SENT', callId: 'c2', approved: true },
  );
  assert.deepEqual(s.confirmationQueue, ['c1']);
  assert.equal(activeConfirmation(s), 'c1');
  assert.equal(s.inputMode, 'confirmation');
});

test('SET_INPUT_MODE cannot steal focus from a pending confirmation', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'rm -rf /' }, true)),
    { type: 'SET_INPUT_MODE', mode: 'completion' },
  );
  assert.equal(s.inputMode, 'confirmation');
});

test('SET_INPUT_MODE toggles completion when no confirmation is pending', () => {
  const s = run(initialState(), { type: 'SET_INPUT_MODE', mode: 'completion' });
  assert.equal(s.inputMode, 'completion');
});

// --- enqueue / drain --------------------------------------------------------

test('ENQUEUE_MESSAGE blocks new prompts and renders the user block', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
    { type: 'ENQUEUE_MESSAGE', content: 'also check ports' },
  );
  assert.equal(s.enqueuedMessage, true);
  assert.equal(canSubmitPrompt(s), false);
  const last = s.blocks[s.blocks.length - 1];
  assert.equal(last.type, 'user');
  assert.equal(last.type === 'user' && last.content, 'also check ports');
});

test('enqueued message clears once pending tool calls drain to zero', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
    { type: 'ENQUEUE_MESSAGE', content: 'next' },
  );
  assert.equal(s.enqueuedMessage, true);
  s = run(s, ev(toolResult('c1', 'terminal', { session_id: 's', command: 'ls', allowed: true, status: 0 })));
  assert.equal(s.enqueuedMessage, false);
  assert.equal(canSubmitPrompt(s), true);
});

test('enqueued message clears on stop even with no pending tool calls', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(text('working', false)),
    { type: 'ENQUEUE_MESSAGE', content: 'next' },
    ev(stop('agent')),
  );
  assert.equal(s.enqueuedMessage, false);
});

test('SUBMIT_PROMPT renders a user block without blocking further prompts', () => {
  const s = run(initialState(), { type: 'SUBMIT_PROMPT', content: 'scan the host' });
  assert.equal(s.blocks[0].type, 'user');
  assert.equal(s.enqueuedMessage, false);
  assert.equal(canSubmitPrompt(s), true);
});

// --- stop block rendering ---------------------------------------------------

test('a plain agent stop adds no visible block', () => {
  const s = run(initialState(), { type: 'STREAM_START' }, ev(stop('agent')));
  assert.equal(s.blocks.filter((b) => b.type === 'stop').length, 0);
});

test('a user stop and a stop with reason/max_iteration add a stop block', () => {
  const userStop = run(initialState(), { type: 'STREAM_START' }, ev(stop('user')));
  assert.equal(userStop.blocks.filter((b) => b.type === 'stop').length, 1);

  const maxIter = run(initialState(), { type: 'STREAM_START' }, ev(stop('agent', { max_iteration: true })));
  const sb = maxIter.blocks.find((b) => b.type === 'stop');
  assert.ok(sb && sb.type === 'stop' && sb.maxIteration);
});

// --- resume (LOAD_EVENTS) ---------------------------------------------------

test('LOAD_EVENTS renders historical events and settles into idle', () => {
  const s = run(initialState(), {
    type: 'LOAD_EVENTS',
    events: [
      { kind: 'user_message', content: 'hi' },
      text('the answer'),
      stop('agent'),
    ],
  });
  assert.equal(s.status, 'idle');
  assert.equal(s.inputMode, 'input');
  assert.equal(s.blocks[0].type, 'user');
  assert.equal(s.blocks[1].type, 'text');
});

test('LOAD_EVENTS does not enter confirmation for a historical confirmation call', () => {
  const s = run(initialState(), {
    type: 'LOAD_EVENTS',
    events: [
      { kind: 'user_message', content: 'do it' },
      toolCall('c1', 'terminal', { command: 'rm -rf /' }, true),
      toolResult('c1', 'terminal', { session_id: 's', command: 'rm -rf /', allowed: false }),
      stop('agent'),
    ],
  });
  assert.equal(s.status, 'idle');
  assert.equal(s.inputMode, 'input');
  assert.equal(activeConfirmation(s), null);
  // Historical replay does not apply timeout labeling.
  assert.equal(tools(s)[0].status, 'done');
});

// --- memoization: identity preservation -------------------------------------

test('appending a block preserves identity of prior blocks', () => {
  const s1 = run(initialState(), ev(text('first')));
  const first = s1.blocks[0];
  const s2 = run(s1, ev(text('second')));
  assert.equal(s2.blocks[0], first, 'unchanged block must keep the same reference');
  assert.notEqual(s2.blocks, s1.blocks, 'blocks array is a new reference');
});

test('updating one block does not change references of others', () => {
  let s = run(initialState(),
    { type: 'STREAM_START' },
    ev(text('answer')),
    ev(toolCall('c1', 'terminal', { command: 'ls' })),
  );
  const textBlockBefore = s.blocks.find((b) => b.type === 'text')!;
  const toolBefore = s.blocks.find((b) => b.type === 'tool')!;
  s = run(s, ev(toolResult('c1', 'terminal', { session_id: 's', command: 'ls', allowed: true, status: 0 })));
  const textBlockAfter = s.blocks.find((b) => b.type === 'text')!;
  const toolAfter = s.blocks.find((b) => b.type === 'tool')!;
  assert.equal(textBlockAfter, textBlockBefore, 'unrelated text block keeps identity');
  assert.notEqual(toolAfter, toolBefore, 'the affected tool block is a new reference');
});

test('reducer never mutates the input state object', () => {
  const s0 = initialState();
  const frozen = Object.freeze({ ...s0, blocks: Object.freeze([...s0.blocks]) as Block[] });
  // Freezing would throw on mutation; a pure reducer returns a new object.
  const s1 = sessionReducer(frozen, ev(text('x')));
  assert.notEqual(s1, frozen);
  assert.equal(frozen.blocks.length, 0);
});

// --- full happy-path sequence ----------------------------------------------

test('a full run: prompt -> reasoning -> tool -> result -> text -> stop', () => {
  let s = initialState();
  s = run(s, { type: 'SET_MODEL', model: { provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8000 } });
  s = run(s, { type: 'SET_SESSION', shortId: 1, mode: 'supervised' });
  s = run(s, { type: 'SUBMIT_PROMPT', content: 'enumerate the host' });
  s = run(s, { type: 'STREAM_START' });
  s = run(s, ev(reasoning('I should scan')));
  s = run(s, ev(toolCall('c1', 'terminal', { command: 'nmap -sV host' })));
  s = run(s, ev(toolResult('c1', 'terminal', { session_id: 's', command: 'nmap -sV host', allowed: true, status: 0, output: '80/tcp open' })));
  s = run(s, ev(text('Found an open web port.')));
  s = run(s, ev(stop('agent')));

  assert.equal(s.status, 'stopped');
  const kinds = s.blocks.map((b) => b.type);
  assert.deepEqual(kinds, ['user', 'reasoning', 'tool', 'text']);
  assert.equal(s.pendingToolCalls, 0);
  assert.equal(canSubmitPrompt(s), true);
});

// --- settled / live split ---------------------------------------------------

test('settledCount excludes the block still accumulating text', () => {
  let s = initialState();
  s = run(s, { type: 'SUBMIT_PROMPT', content: 'hi' }, { type: 'STREAM_START' });
  s = run(s, ev(text('partial', true, false)));
  assert.equal(settledCount(s), 1, 'the open text block is still live');

  s = run(s, ev(text('', true, true)));
  assert.equal(settledCount(s), 2, 'a finalized text block is settled');
});

test('settledCount excludes a tool call awaiting confirmation', () => {
  let s = initialState();
  s = run(s, { type: 'STREAM_START' });
  s = run(s, ev(toolCall('c1', 'terminal', { command: 'rm -rf /' }, true)));
  assert.equal(settledCount(s), 0);
});

test('settledCount is a prefix: a settled block behind a pending one stays live', () => {
  let s = initialState();
  s = run(s, { type: 'STREAM_START' });
  s = run(s, ev(toolCall('c1', 'terminal', { command: 'slow' })));
  s = run(s, ev(toolCall('c2', 'terminal', { command: 'fast' })));
  s = run(s, ev(toolResult('c2', 'terminal', { session_id: 's', command: 'fast', allowed: true, status: 0, output: 'ok' })));

  // c2 is final, but c1 ahead of it is not, so nothing may be written yet:
  // static output is ordered and append-only.
  assert.equal(s.blocks.length, 2);
  assert.equal(settledCount(s), 0);

  s = run(s, ev(toolResult('c1', 'terminal', { session_id: 's', command: 'slow', allowed: true, status: 0, output: 'ok' })));
  assert.equal(settledCount(s), 2, 'both settle once the blocker resolves');
});
