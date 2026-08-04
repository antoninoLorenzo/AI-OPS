import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { AddressInfo } from 'node:net';

import { ApiClient, ApiError, API_KEY_HEADER } from '../src/api/client.ts';
import type { AnyEvent } from '../src/api/events.ts';

interface Captured {
  apiKey?: string;
  startBody?: { content: string; mode: string };
  sendBody?: { content: string };
  confirmPath?: string;
  confirmQuery?: string;
}

async function readBody(req: http.IncomingMessage): Promise<string> {
  const chunks: Buffer[] = [];
  for await (const chunk of req) chunks.push(chunk as Buffer);
  return Buffer.concat(chunks).toString('utf8');
}

const MODEL = {
  provider: 'openai',
  model_id: 'gpt-4o',
  max_context_length: 8192,
  tool_use: true,
  reasoning: false,
  response_format: true,
  structured_output: true,
};

const STREAM_EVENTS = [
  { kind: 'tool_call', call_id: 'c1', name: 'terminal', args: { command: 'ls' } },
  {
    kind: 'tool_result', call_id: 'c1', name: 'terminal', args: { command: 'ls' },
    result: { session_id: 's', command: 'ls', allowed: true, status: 0, output: 'file.txt' },
  },
  { kind: 'stop', issuer: 'agent' },
];

function makeServer(captured: Captured): http.Server {
  return http.createServer(async (req, res) => {
    const url = new URL(req.url ?? '/', 'http://localhost');
    const key = req.headers[API_KEY_HEADER.toLowerCase()];
    if (typeof key === 'string') captured.apiKey = key;
    const { method } = req;
    const path = url.pathname;

    const json = (status: number, body: unknown) => {
      res.writeHead(status, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify(body));
    };

    if (method === 'GET' && path === '/health') return json(200, { status: 'ok' });
    if (method === 'GET' && path === '/model') return json(200, MODEL);
    if (method === 'POST' && path === '/conversation') {
      return json(200, { uuid: 'u-1', short_id: 1, messages: [] });
    }

    // load conversation
    if (method === 'GET' && path === '/conversation/1') {
      return json(200, [{ kind: 'user_message', content: 'hi' }, { kind: 'stop', issuer: 'agent' }]);
    }
    if (method === 'GET' && path === '/conversation/404') return json(404, { detail: 'not found' });

    // start agent (stream)
    if (method === 'POST' && path === '/conversation/1') {
      captured.startBody = JSON.parse(await readBody(req));
      res.writeHead(200, { 'Content-Type': 'application/x-ndjson' });
      for (const ev of STREAM_EVENTS) res.write(JSON.stringify(ev) + '\n');
      return res.end();
    }
    if (method === 'POST' && path === '/conversation/400') return json(400, { detail: 'already running' });
    if (method === 'POST' && path === '/conversation/500') return json(500, { detail: 'invalid conversation' });

    // send
    if (method === 'POST' && path === '/conversation/1/send') {
      captured.sendBody = JSON.parse(await readBody(req));
      return json(200, { enqueued: true });
    }
    if (method === 'POST' && path === '/conversation/9/send') return json(409, { detail: 'conflict' });

    // stop
    if (method === 'POST' && path === '/conversation/1/stop') return json(200, null);
    if (method === 'POST' && path === '/conversation/404/stop') return json(404, { detail: 'no agent' });

    // delete
    if (method === 'DELETE' && path === '/conversation/1') return json(200, null);
    if (method === 'DELETE' && path === '/conversation/404') return json(404, { detail: 'no agent' });

    // confirmation
    if (method === 'POST' && path.startsWith('/conversation/1/confirmation/')) {
      captured.confirmPath = path;
      captured.confirmQuery = url.search;
      if (path.endsWith('/bad')) return json(400, { detail: 'no such call' });
      return json(200, null);
    }

    // usage
    if (method === 'GET' && path === '/conversation/1/usage') {
      return json(200, { total_tokens: 1234, max_context_length: 8192 });
    }

    return json(404, { detail: `unhandled ${method} ${path}` });
  });
}

async function withServer(
  captured: Captured,
  fn: (baseUrl: string) => Promise<void>,
): Promise<void> {
  const server = makeServer(captured);
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;
  try {
    await fn(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

test('health resolves on 200 and sends the api key header', async () => {
  const captured: Captured = {};
  await withServer(captured, async (baseUrl) => {
    const client = new ApiClient({ baseUrl, apiKey: 'topsecret' });
    await client.health();
    assert.equal(captured.apiKey, 'topsecret');
  });
});

test('no api key header is sent when none is configured', async () => {
  const captured: Captured = {};
  await withServer(captured, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    await client.health();
    assert.equal(captured.apiKey, undefined);
  });
});

test('health rejects when the API is unreachable', async () => {
  // Point at a closed port; the connection error should propagate.
  const client = new ApiClient({ baseUrl: 'http://127.0.0.1:1' });
  await assert.rejects(() => client.health());
});

test('getModel parses model metadata', async () => {
  await withServer({}, async (baseUrl) => {
    const model = await new ApiClient({ baseUrl }).getModel();
    assert.equal(model.model_id, 'gpt-4o');
    assert.equal(model.max_context_length, 8192);
    assert.equal(model.tool_use, true);
  });
});

test('createConversation returns the short_id', async () => {
  await withServer({}, async (baseUrl) => {
    const conv = await new ApiClient({ baseUrl }).createConversation();
    assert.equal(conv.short_id, 1);
    assert.equal(conv.uuid, 'u-1');
  });
});

test('loadConversation returns parsed events', async () => {
  await withServer({}, async (baseUrl) => {
    const events = await new ApiClient({ baseUrl }).loadConversation(1);
    assert.equal(events.length, 2);
    assert.equal(events[0].kind, 'user_message');
    assert.equal(events[1].kind, 'stop');
  });
});

test('loadConversation throws ApiError(404) for a missing conversation', async () => {
  await withServer({}, async (baseUrl) => {
    await assert.rejects(
      () => new ApiClient({ baseUrl }).loadConversation(404),
      (err) => err instanceof ApiError && err.status === 404,
    );
  });
});

test('startAgent streams parsed events in order and carries content/mode', async () => {
  const captured: Captured = {};
  await withServer(captured, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    const received: AnyEvent[] = [];
    for await (const ev of client.startAgent(1, 'scan the host', 'supervised')) received.push(ev);
    assert.deepEqual(received.map((e) => e.kind), ['tool_call', 'tool_result', 'stop']);
    assert.deepEqual(captured.startBody, { content: 'scan the host', mode: 'supervised' });
  });
});

test('startAgent throws ApiError(400) when the agent is already running', async () => {
  await withServer({}, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    await assert.rejects(
      async () => {
        for await (const _ of client.startAgent(400, 'x', 'supervised')) void _;
      },
      (err) => err instanceof ApiError && err.status === 400,
    );
  });
});

test('startAgent throws ApiError(500) on invalid conversation', async () => {
  await withServer({}, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    await assert.rejects(
      async () => {
        for await (const _ of client.startAgent(500, 'x', 'supervised')) void _;
      },
      (err) => err instanceof ApiError && err.status === 500,
    );
  });
});

test('sendMessage posts the content and resolves on 200', async () => {
  const captured: Captured = {};
  await withServer(captured, async (baseUrl) => {
    await new ApiClient({ baseUrl }).sendMessage(1, 'another prompt');
    assert.deepEqual(captured.sendBody, { content: 'another prompt' });
  });
});

test('sendMessage throws ApiError(409) on conflict', async () => {
  await withServer({}, async (baseUrl) => {
    await assert.rejects(
      () => new ApiClient({ baseUrl }).sendMessage(9, 'x'),
      (err) => err instanceof ApiError && err.status === 409,
    );
  });
});

test('stopAgent resolves on 200 and throws ApiError(404) when missing', async () => {
  await withServer({}, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    await client.stopAgent(1);
    await assert.rejects(
      () => client.stopAgent(404),
      (err) => err instanceof ApiError && err.status === 404,
    );
  });
});

test('deleteConversation resolves on 200 and throws ApiError(404) when missing', async () => {
  await withServer({}, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    await client.deleteConversation(1);
    await assert.rejects(
      () => client.deleteConversation(404),
      (err) => err instanceof ApiError && err.status === 404,
    );
  });
});

test('confirmToolCall encodes the approved query parameter and tool_call_id', async () => {
  const captured: Captured = {};
  await withServer(captured, async (baseUrl) => {
    const client = new ApiClient({ baseUrl });
    await client.confirmToolCall(1, 'call-42', true);
    assert.equal(captured.confirmPath, '/conversation/1/confirmation/call-42');
    assert.equal(captured.confirmQuery, '?approved=true');

    await client.confirmToolCall(1, 'call-42', false);
    assert.equal(captured.confirmQuery, '?approved=false');
  });
});

test('confirmToolCall throws ApiError(400) for an unknown call', async () => {
  await withServer({}, async (baseUrl) => {
    await assert.rejects(
      () => new ApiClient({ baseUrl }).confirmToolCall(1, 'bad', true),
      (err) => err instanceof ApiError && err.status === 400,
    );
  });
});

test('getUsage parses token usage', async () => {
  await withServer({}, async (baseUrl) => {
    const usage = await new ApiClient({ baseUrl }).getUsage(1);
    assert.equal(usage.total_tokens, 1234);
    assert.equal(usage.max_context_length, 8192);
  });
});

test('trailing slashes in baseUrl are normalized', async () => {
  await withServer({}, async (baseUrl) => {
    const model = await new ApiClient({ baseUrl: baseUrl + '///' }).getModel();
    assert.equal(model.model_id, 'gpt-4o');
  });
});
