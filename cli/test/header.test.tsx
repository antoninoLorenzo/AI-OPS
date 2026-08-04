import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { Header, humanizeTokens } from '../src/components/Header.tsx';

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

test('header shows model, provider, mode, short id and usage', () => {
  const f = frame(
    <Header
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
});

test('header shows 0/max before the agent starts', () => {
  const f = frame(
    <Header
      model={{ provider: 'openai', modelId: 'gpt-4o', maxContextLength: 8000 }}
      mode="unsupervised"
      shortId={1}
      totalTokens={0}
    />,
  );
  assert.match(f, /UNSUPERVISED/);
  assert.match(f, /0\/8k/);
});

test('header shows total/? when max context length is unknown', () => {
  const f = frame(
    <Header
      model={{ provider: 'vllm', modelId: 'local', maxContextLength: null }}
      mode="supervised"
      shortId={2}
      totalTokens={500}
    />,
  );
  assert.match(f, /500\/\?/);
});

test('header shows a placeholder before model metadata is loaded', () => {
  const f = frame(<Header model={null} mode="supervised" shortId={null} totalTokens={0} />);
  assert.match(f, /…/);
});
