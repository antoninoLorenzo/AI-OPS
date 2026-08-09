import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtempSync, writeFileSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';

import {
  parseFlags,
  readConfigFile,
  resolveConfig,
  ConfigError,
} from '../src/config.ts';

function withTempFile(name: string, contents: string, fn: (path: string) => void): void {
  const dir = mkdtempSync(join(tmpdir(), 'ai-ops-cfg-'));
  const path = join(dir, name);
  writeFileSync(path, contents, 'utf8');
  try {
    fn(path);
  } finally {
    rmSync(dir, { recursive: true, force: true });
  }
}

test('parseFlags maps known flags to config source', () => {
  const source = parseFlags([
    '--base-url', 'http://localhost:9000',
    '--api-key', 'secret',
    '--mode', 'unsupervised',
    '--resume', '7',
  ]);
  assert.deepEqual(source, {
    baseUrl: 'http://localhost:9000',
    apiKey: 'secret',
    mode: 'unsupervised',
    resume: '7',
  });
});

test('parseFlags returns only the provided known keys', () => {
  const source = parseFlags(['--base-url', 'http://x']);
  assert.deepEqual(source, { baseUrl: 'http://x' });
});

test('parseFlags rejects an unknown flag with a ConfigError', () => {
  // A typo (e.g. --reload for --resume) must fail loudly, not be dropped.
  assert.throws(() => parseFlags(['--base-url', 'http://x', '--reload', '8']), ConfigError);
});

test('readConfigFile returns empty object when file is missing', () => {
  const source = readConfigFile(join(tmpdir(), 'definitely-does-not-exist-ai-ops.json'));
  assert.deepEqual(source, {});
});

test('readConfigFile maps snake_case keys to camelCase', () => {
  withTempFile('cli.json', JSON.stringify({ base_url: 'http://127.0.0.1:8000', api_key: 'k' }), (path) => {
    assert.deepEqual(readConfigFile(path), { baseUrl: 'http://127.0.0.1:8000', apiKey: 'k' });
  });
});

test('readConfigFile throws ConfigError on malformed JSON', () => {
  withTempFile('cli.json', '{ not valid json', (path) => {
    assert.throws(() => readConfigFile(path), ConfigError);
  });
});

test('readConfigFile throws ConfigError when JSON is not an object', () => {
  withTempFile('cli.json', '[1,2,3]', (path) => {
    assert.throws(() => readConfigFile(path), ConfigError);
  });
});

test('resolveConfig gives flags precedence over the file', () => {
  const config = resolveConfig(
    { baseUrl: 'http://file:8000', apiKey: 'file-key', mode: 'supervised' },
    { baseUrl: 'http://flag:9000', mode: 'unsupervised' },
  );
  assert.equal(config.baseUrl, 'http://flag:9000');
  assert.equal(config.apiKey, 'file-key');
  assert.equal(config.mode, 'unsupervised');
});

test('resolveConfig applies default mode and coerces resume', () => {
  const config = resolveConfig({}, { baseUrl: 'http://x:8000', resume: '12' });
  assert.equal(config.mode, 'supervised');
  assert.equal(config.resume, 12);
});

test('resolveConfig throws when baseUrl is missing', () => {
  assert.throws(() => resolveConfig({}, {}), ConfigError);
});

test('resolveConfig throws when baseUrl is not a url', () => {
  assert.throws(() => resolveConfig({}, { baseUrl: 'not-a-url' }), ConfigError);
});

test('resolveConfig throws on invalid mode', () => {
  assert.throws(
    () => resolveConfig({}, { baseUrl: 'http://x:8000', mode: 'bogus' }),
    ConfigError,
  );
});

test('resolveConfig throws on non-integer resume', () => {
  assert.throws(
    () => resolveConfig({}, { baseUrl: 'http://x:8000', resume: '1.5' }),
    ConfigError,
  );
});
