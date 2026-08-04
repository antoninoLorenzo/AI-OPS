import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { App } from '../src/components/App.tsx';
import type { ApiClient } from '../src/api/client.ts';
import type { AnyEvent } from '../src/api/events.ts';
import type { ModelInfo } from '../src/state/sessionReducer.ts';
import { waitFor, waitForFrame, pressUntil } from './helpers.ts';

const MODEL: ModelInfo = { provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8000 };

const GATE = Symbol('gate');
type Step = AnyEvent | typeof GATE;

interface Fake {
  client: ApiClient;
  calls: {
    start: { content: string; mode: string }[];
    send: string[];
    confirm: { callId: string; approved: boolean }[];
    stop: number;
    del: number;
    usage: number;
  };
}

function makeFake(scenario: Step[], usage = { total_tokens: 4242, max_context_length: 8000 }): Fake {
  const calls: Fake['calls'] = { start: [], send: [], confirm: [], stop: 0, del: 0, usage: 0 };
  let releaseGate: (() => void) | null = null;

  const client = {
    async *startAgent(_shortId: number, content: string, mode: string) {
      calls.start.push({ content, mode });
      for (const step of scenario) {
        if (step === GATE) {
          await new Promise<void>((res) => {
            releaseGate = res;
          });
          continue;
        }
        yield step;
      }
    },
    async getUsage() {
      calls.usage += 1;
      return usage;
    },
    async sendMessage(_id: number, content: string) {
      calls.send.push(content);
    },
    async confirmToolCall(_id: number, callId: string, approved: boolean) {
      calls.confirm.push({ callId, approved });
      if (releaseGate) {
        const g = releaseGate;
        releaseGate = null;
        g();
      }
    },
    async stopAgent() {
      calls.stop += 1;
    },
    async deleteConversation() {
      calls.del += 1;
    },
  } as unknown as ApiClient;

  return { client, calls };
}

// Types text into the buffer and waits for it to render before submitting, so
// the Enter is never processed against a half-typed buffer.
async function submit(
  stdin: { write: (s: string) => void },
  getFrame: () => string | undefined,
  text: string,
): Promise<void> {
  stdin.write(text);
  await waitForFrame(getFrame, new RegExp(text.replace(/[.*+?^${}()|[\]\\]/g, '\\$&')));
  stdin.write('\r');
}

test('renders the header from model metadata on startup', async () => {
  const { client } = makeFake([]);
  const { lastFrame } = render(<App client={client} model={MODEL} shortId={2} mode="supervised" />);
  await waitForFrame(lastFrame, /gpt-4o \(openai\)/);
  const f = lastFrame() ?? '';
  assert.match(f, /SUPERVISED/);
  assert.match(f, /#2/);
});

test('submitting a prompt starts the agent and renders the streamed transcript', async () => {
  const scenario: Step[] = [
    { kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'nmap host' }, requires_confirmation: false },
    { kind: 'tool_result', call_id: 'c1', name: 'terminal', args: { command: 'nmap host' }, result: { session_id: 's', command: 'nmap host', allowed: true, status: 0, output: '80/tcp open' } },
    { kind: 'text', chunk: 'Found a web port.', stream: false, stream_done: false },
    { kind: 'stop', issuer: 'agent', reason: null, error: null, max_iteration: false },
  ];
  const { client, calls } = makeFake(scenario);
  const { stdin, lastFrame } = render(<App client={client} model={MODEL} shortId={1} mode="supervised" />);
  await waitForFrame(lastFrame, /gpt-4o/);

  await submit(stdin, lastFrame, 'enumerate the host');
  await waitForFrame(lastFrame, /Found a web port\./);

  const f = lastFrame() ?? '';
  assert.deepEqual(calls.start, [{ content: 'enumerate the host', mode: 'supervised' }]);
  assert.match(f, /enumerate the host/);
  assert.match(f, /\$ nmap host/);
  assert.match(f, /80\/tcp open/);
  // Usage refreshed after tool_result and stop; header reflects the new total.
  assert.ok(calls.usage >= 1);
  assert.match(f, /4\.2k\/8k/);
});

test('a confirmation-required tool call shows the form and confirms on y', async () => {
  const scenario: Step[] = [
    { kind: 'tool_call', call_id: 'c9', name: 'terminal', args: { command: 'rm -rf /etc' }, requires_confirmation: true },
    GATE,
    { kind: 'tool_result', call_id: 'c9', name: 'terminal', args: { command: 'rm -rf /etc' }, result: { session_id: 's', command: 'rm -rf /etc', allowed: true, status: 0, output: 'done' } },
    { kind: 'stop', issuer: 'agent', reason: null, error: null, max_iteration: false },
  ];
  const { client, calls } = makeFake(scenario);
  const { stdin, lastFrame } = render(<App client={client} model={MODEL} shortId={1} mode="supervised" />);
  await waitForFrame(lastFrame, /gpt-4o/);

  await submit(stdin, lastFrame, 'delete etc');
  await waitForFrame(lastFrame, /confirm/);
  assert.match(lastFrame() ?? '', /rm -rf \/etc/);

  await pressUntil(stdin, 'y', () => calls.confirm.length === 1);
  assert.deepEqual(calls.confirm, [{ callId: 'c9', approved: true }]);
  await waitForFrame(lastFrame, /done/);
  assert.doesNotMatch(lastFrame() ?? '', /approve · reject/);
});

test('a slash command is routed to the registry (/stop)', async () => {
  const scenario: Step[] = [
    { kind: 'text', chunk: 'working…', stream: false, stream_done: false },
    GATE,
    { kind: 'stop', issuer: 'user', reason: null, error: null, max_iteration: false },
  ];
  const { client, calls } = makeFake(scenario);
  const { stdin, lastFrame } = render(<App client={client} model={MODEL} shortId={5} mode="supervised" />);
  await waitForFrame(lastFrame, /gpt-4o/);

  await submit(stdin, lastFrame, 'do work');
  await waitForFrame(lastFrame, /working/);

  await submit(stdin, lastFrame, '/stop');
  await waitFor(() => calls.stop === 1);
  assert.equal(calls.stop, 1);
});

test('Ctrl+R toggles reasoning visibility', async () => {
  const { client } = makeFake([]);
  const initialEvents: AnyEvent[] = [
    { kind: 'user_message', content: 'hi' },
    { kind: 'reasoning', chunk: 'the secret plan' },
    { kind: 'stop', issuer: 'agent', reason: null, error: null, max_iteration: false },
  ];
  const { stdin, lastFrame } = render(
    <App client={client} model={MODEL} shortId={1} mode="supervised" initialEvents={initialEvents} initialTotalTokens={100} />,
  );
  await waitForFrame(lastFrame, /reasoning hidden/);
  assert.doesNotMatch(lastFrame() ?? '', /the secret plan/);

  await pressUntil(stdin, '\x12', () => /the secret plan/.test(lastFrame() ?? '')); // Ctrl+R
  await pressUntil(stdin, '\x12', () => !/the secret plan/.test(lastFrame() ?? '')); // toggle back
  assert.match(lastFrame() ?? '', /reasoning hidden/);
});

test('resuming renders the historical transcript and prior token usage', async () => {
  const { client } = makeFake([]);
  const initialEvents: AnyEvent[] = [
    { kind: 'user_message', content: 'earlier prompt' },
    { kind: 'text', chunk: 'earlier answer', stream: false, stream_done: false },
    { kind: 'stop', issuer: 'agent', reason: null, error: null, max_iteration: false },
  ];
  const { lastFrame } = render(
    <App client={client} model={MODEL} shortId={42} mode="supervised" initialEvents={initialEvents} initialTotalTokens={777} />,
  );
  await waitForFrame(lastFrame, /earlier prompt/);
  const f = lastFrame() ?? '';
  assert.match(f, /earlier answer/);
  assert.match(f, /#42/);
  assert.match(f, /777\/8k/); // resumed usage reflected in the header
});

test('a prompt submitted while running is sent, not started again', async () => {
  const scenario: Step[] = [
    { kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'sleep' }, requires_confirmation: false },
    GATE,
    { kind: 'tool_result', call_id: 'c1', name: 'terminal', args: { command: 'sleep' }, result: { session_id: 's', command: 'sleep', allowed: true, status: 0 } },
    { kind: 'stop', issuer: 'agent', reason: null, error: null, max_iteration: false },
  ];
  const { client, calls } = makeFake(scenario);
  const { stdin, lastFrame } = render(<App client={client} model={MODEL} shortId={1} mode="supervised" />);
  await waitForFrame(lastFrame, /gpt-4o/);

  await submit(stdin, lastFrame, 'first prompt');
  // Now running, blocked on the gated tool call.
  await waitFor(() => calls.start.length === 1);
  await waitForFrame(lastFrame, /\$ sleep/);

  await submit(stdin, lastFrame, 'second prompt');
  await waitFor(() => calls.send.length === 1);

  assert.equal(calls.start.length, 1, 'only the first prompt starts a run');
  assert.deepEqual(calls.send, ['second prompt'], 'the second prompt is enqueued via send');
});
