import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { AddressInfo } from 'node:net';

import { runStartup, StartupError } from '../src/startup.ts';
import { API_KEY_HEADER } from '../src/api/client.ts';
import type { AppConfig } from '../src/config.ts';

const MODEL = {
  provider: 'openai',
  model_id: 'gpt-4o',
  max_context_length: 8192,
  tool_use: true,
  reasoning: false,
  response_format: true,
  structured_output: true,
};

interface Captured {
  apiKeys: (string | undefined)[];
  createdConversations: number;
  hitModel: boolean;
}

interface ServerOptions {
  // Behavior toggles for the mock endpoints.
  modelMaxContext?: number | null;
  resumeEvents?: unknown[] | 'not-found';
}

function makeServer(captured: Captured, opts: ServerOptions): http.Server {
  // Distinguish "not provided" from an explicit null.
  const maxContext = 'modelMaxContext' in opts ? opts.modelMaxContext : MODEL.max_context_length;
  return http.createServer((req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    captured.apiKeys.push(req.headers[API_KEY_HEADER.toLowerCase()] as string | undefined);
    const { method } = req;
    const path = url.pathname;
    const json = (status: number, body: unknown) => {
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(body));
    };

    if (method === 'GET' && path === '/health') return json(200, { status: 'ok' });

    if (method === 'GET' && path === '/model') {
      captured.hitModel = true;
      return json(200, { ...MODEL, max_context_length: maxContext });
    }

    if (method === 'POST' && path === '/conversation') {
      captured.createdConversations += 1;
      return json(200, { uuid: 'u-1', short_id: 42, messages: [] });
    }

    if (method === 'GET' && path.startsWith('/conversation/') && path.endsWith('/usage')) {
      return json(200, { total_tokens: 777, max_context_length: maxContext });
    }

    // resume: GET /conversation/{short_id}
    if (method === 'GET' && /^\/conversation\/\d+$/.test(path)) {
      if (opts.resumeEvents === 'not-found') return json(404, { detail: 'not found' });
      return json(200, opts.resumeEvents ?? []);
    }

    return json(404, { detail: `unhandled ${method} ${path}` });
  });
}

async function withServer(
  opts: ServerOptions,
  fn: (baseUrl: string, captured: Captured) => Promise<void>,
): Promise<void> {
  const captured: Captured = { apiKeys: [], createdConversations: 0, hitModel: false };
  const server = makeServer(captured, opts);
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;
  try {
    await fn(`http://127.0.0.1:${port}`, captured);
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

function config(overrides: Partial<AppConfig> & { baseUrl: string }): AppConfig {
  return { mode: 'supervised', ...overrides };
}

test('fresh start: creates a conversation and loads model metadata', async () => {
  await withServer({}, async (baseUrl, captured) => {
    const result = await runStartup(config({ baseUrl, mode: 'unsupervised' }));
    assert.equal(captured.createdConversations, 1);
    assert.equal(result.shortId, 42);
    assert.equal(result.mode, 'unsupervised');
    assert.equal(result.model.modelId, 'gpt-4o');
    assert.equal(result.model.provider, 'openai');
    assert.equal(result.model.maxContextLength, 8192);
    assert.equal(result.initialEvents, undefined);
    assert.equal(result.initialTotalTokens, 0);
    assert.ok(captured.hitModel);
  });
});

test('a null max context length maps to null in ModelInfo', async () => {
  await withServer({ modelMaxContext: null }, async (baseUrl) => {
    const result = await runStartup(config({ baseUrl }));
    assert.equal(result.model.maxContextLength, null);
  });
});

test('the api key is sent on every startup request', async () => {
  await withServer({}, async (baseUrl, captured) => {
    await runStartup(config({ baseUrl, apiKey: 'sekret' }));
    assert.ok(captured.apiKeys.length >= 3, 'health, create and model at least');
    assert.ok(captured.apiKeys.every((k) => k === 'sekret'));
  });
});

test('unreachable API raises StartupError', async () => {
  // Nothing is listening on this port.
  await assert.rejects(
    () => runStartup(config({ baseUrl: 'http://127.0.0.1:1' })),
    (err) => err instanceof StartupError && /not reachable/.test(err.message),
  );
});

test('resume: loads the event list and prior token usage', async () => {
  const events = [
    { kind: 'user_message', content: 'earlier prompt' },
    { kind: 'text', chunk: 'earlier answer', stream: false, stream_done: false },
    { kind: 'stop', issuer: 'agent', reason: null, error: null, max_iteration: false },
  ];
  await withServer({ resumeEvents: events }, async (baseUrl, captured) => {
    const result = await runStartup(config({ baseUrl, resume: 42 }));
    assert.equal(result.shortId, 42);
    assert.equal(captured.createdConversations, 0, 'resume must not create a conversation');
    assert.equal(result.initialEvents?.length, 3);
    assert.equal(result.initialEvents?.[0].kind, 'user_message');
    assert.equal(result.initialTotalTokens, 777);
    assert.ok(captured.hitModel);
  });
});

test('resume of a missing conversation raises StartupError (404)', async () => {
  await withServer({ resumeEvents: 'not-found' }, async (baseUrl) => {
    await assert.rejects(
      () => runStartup(config({ baseUrl, resume: 99 })),
      (err) => err instanceof StartupError && /No conversation with short_id=99/.test(err.message),
    );
  });
});

test('resume validates streamed historical events (malformed -> error)', async () => {
  // An unrecognized event kind must not be silently accepted.
  await withServer({ resumeEvents: [{ kind: 'bogus' }] }, async (baseUrl) => {
    await assert.rejects(() => runStartup(config({ baseUrl, resume: 42 })));
  });
});
