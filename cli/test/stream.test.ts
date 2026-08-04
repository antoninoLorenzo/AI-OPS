import test from 'node:test';
import assert from 'node:assert/strict';

import { splitNdjson } from '../src/api/stream.ts';

async function* fromChunks(chunks: (Uint8Array | string)[]): AsyncGenerator<Uint8Array | string> {
  for (const chunk of chunks) yield chunk;
}

async function collect(chunks: (Uint8Array | string)[]): Promise<string[]> {
  const lines: string[] = [];
  for await (const line of splitNdjson(fromChunks(chunks))) lines.push(line);
  return lines;
}

test('splits complete lines from a single chunk', async () => {
  assert.deepEqual(await collect(['a\nb\nc\n']), ['a', 'b', 'c']);
});

test('yields a trailing line with no final newline', async () => {
  assert.deepEqual(await collect(['a\nb\nc']), ['a', 'b', 'c']);
});

test('reassembles a line split across chunk boundaries', async () => {
  assert.deepEqual(await collect(['{"kind":', '"stop",', '"issuer":"agent"}\n']), [
    '{"kind":"stop","issuer":"agent"}',
  ]);
});

test('handles multiple newlines arriving in one chunk', async () => {
  assert.deepEqual(await collect(['line1\nline2\n', 'line3\nline4\n']), [
    'line1', 'line2', 'line3', 'line4',
  ]);
});

test('skips empty and whitespace-only lines', async () => {
  assert.deepEqual(await collect(['a\n\n  \nb\n']), ['a', 'b']);
});

test('decodes a multibyte character split across byte chunks', async () => {
  const encoder = new TextEncoder();
  const full = encoder.encode('é\n'); // 'é' is two bytes in UTF-8
  const first = full.slice(0, 1);
  const second = full.slice(1);
  assert.deepEqual(await collect([first, second]), ['é']);
});

test('handles Uint8Array chunks', async () => {
  const encoder = new TextEncoder();
  assert.deepEqual(await collect([encoder.encode('x\ny\n')]), ['x', 'y']);
});
