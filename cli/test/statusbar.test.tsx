import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { StatusBar, humanizeTokens } from '../src/components/StatusBar.tsx';

function frame(node: React.ReactElement): string {
  return render(node).lastFrame() ?? '';
}

test('humanizeTokens formats magnitudes', () => {
  assert.equal(humanizeTokens(0), '0');
  assert.equal(humanizeTokens(999), '999');
  assert.equal(humanizeTokens(1000), '1k');
  assert.equal(humanizeTokens(1234), '1.2k');
  assert.equal(humanizeTokens(8000), '8k');
  assert.equal(humanizeTokens(8192), '8.2k');
  assert.equal(humanizeTokens(2_000_000), '2M');
});

test('status bar shows model, provider, mode, short id and usage', () => {
  const f = frame(
    <StatusBar
      model={{ provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8000 }}
      mode="supervised"
      shortId={3}
      totalTokens={1234}
    />,
  );
  assert.match(f, /gpt-4o \(openai\)/);
  assert.match(f, /SUPERVISED/);
  assert.match(f, /#3/);
  assert.match(f, /1\.2k\/8k/);
  assert.match(f, /ctrl\+r reasoning/); // key hints live in the bar, not a separate line
});

test('status bar shows 0/max before the agent starts', () => {
  const f = frame(
    <StatusBar
      model={{ provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8000 }}
      mode="unsupervised"
      shortId={1}
      totalTokens={0}
    />,
  );
  assert.match(f, /UNSUPERVISED/);
  assert.match(f, /0\/8k/);
});

test('status bar shows total/? when max context length is unknown', () => {
  const f = frame(
    <StatusBar
      model={{ provider: 'vllm', modelId: 'local', maxContextLength: null }}
      mode="supervised"
      shortId={2}
      totalTokens={500}
    />,
  );
  assert.match(f, /500\/\?/);
});

test('status bar shows a placeholder before model metadata is loaded', () => {
  const f = frame(<StatusBar model={null} mode="supervised" shortId={null} totalTokens={0} />);
  assert.match(f, /…/);
});

test('status bar shows a running indicator only while the agent works', () => {
  const props = {
    model: { provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8000 },
    mode: 'supervised' as const,
    shortId: 1,
    totalTokens: 0,
  };
  const running = frame(<StatusBar {...props} running />);
  assert.match(running, /running/);
  assert.match(running, /[/\\|-]/, 'a spinner frame is drawn');

  // Idle is the default: no indicator, and the bar keeps its usual contents.
  const idle = frame(<StatusBar {...props} />);
  assert.doesNotMatch(idle, /running/);
  assert.match(idle, /gpt-4o \(openai\)/);
});
