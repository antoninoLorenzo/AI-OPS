import test from 'node:test';
import assert from 'node:assert/strict';
import http from 'node:http';
import { spawn } from 'node:child_process';
import { AddressInfo } from 'node:net';
import { fileURLToPath } from 'node:url';
import { dirname, join } from 'node:path';

const cliPath = join(dirname(fileURLToPath(import.meta.url)), '..', 'src', 'cli.tsx');

interface RunResult {
  code: number | null;
  stderr: string;
  stdout: string;
}

// Runs the CLI entry point as a child process. Only startup error paths are
// exercised here — they exit before render(), so no TTY is required.
function runCli(args: string[], timeoutMs = 15000): Promise<RunResult> {
  return new Promise((resolve, reject) => {
    const child = spawn('node', ['--import', 'tsx', cliPath, ...args], {
      stdio: ['ignore', 'pipe', 'pipe'],
      env: { ...process.env },
    });
    let stdout = '';
    let stderr = '';
    child.stdout.on('data', (d) => (stdout += d.toString()));
    child.stderr.on('data', (d) => (stderr += d.toString()));
    const timer = setTimeout(() => {
      child.kill('SIGKILL');
      reject(new Error('cli did not exit in time (likely reached render())'));
    }, timeoutMs);
    child.on('exit', (code) => {
      clearTimeout(timer);
      resolve({ code, stderr, stdout });
    });
    child.on('error', reject);
  });
}

async function withServer(
  handler: http.RequestListener,
  fn: (baseUrl: string) => Promise<void>,
): Promise<void> {
  const server = http.createServer(handler);
  await new Promise<void>((resolve) => server.listen(0, '127.0.0.1', resolve));
  const { port } = server.address() as AddressInfo;
  try {
    await fn(`http://127.0.0.1:${port}`);
  } finally {
    await new Promise<void>((resolve) => server.close(() => resolve()));
  }
}

test('exits 1 with a message when the API is unreachable', async () => {
  const result = await runCli(['--base-url', 'http://127.0.0.1:1']);
  assert.equal(result.code, 1);
  assert.match(result.stderr, /not reachable/);
});

test('exits 1 when resuming a conversation that does not exist', async () => {
  await withServer(
    (req, res) => {
      const url = new URL(req.url ?? '/', 'http://localhost');
      if (url.pathname === '/health') {
        res.writeHead(200, { 'Content-Type': 'application/json' });
        return res.end(JSON.stringify({ status: 'ok' }));
      }
      // GET /conversation/99 -> 404
      res.writeHead(404, { 'Content-Type': 'application/json' });
      res.end(JSON.stringify({ detail: 'not found' }));
    },
    async (baseUrl) => {
      const result = await runCli(['--base-url', baseUrl, '--resume', '99']);
      assert.equal(result.code, 1);
      assert.match(result.stderr, /No conversation with short_id=99/);
    },
  );
});

test('exits 1 with a usage error on an invalid --resume value', async () => {
  // A non-integer resume fails config validation before any request is made.
  const result = await runCli(['--base-url', 'http://127.0.0.1:8000', '--resume', 'abc']);
  assert.equal(result.code, 1);
  assert.match(result.stderr, /[Ii]nvalid configuration/);
});
