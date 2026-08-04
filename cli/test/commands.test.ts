import test from 'node:test';
import assert from 'node:assert/strict';

import { CommandRegistry, type CommandDefinition, type AppContext } from '../src/commands/registry.ts';
import { buildRegistry } from '../src/commands/index.ts';
import { exitCommand } from '../src/commands/exit.ts';
import { stopCommand } from '../src/commands/stop.ts';
import type { ApiClient } from '../src/api/client.ts';

function fakeCtx(opts: {
  client: Partial<ApiClient>;
  shortId?: number;
  dispatch?: AppContext['dispatch'];
  exit?: AppContext['exit'];
}): AppContext {
  return {
    client: opts.client as unknown as ApiClient,
    shortId: opts.shortId ?? 1,
    dispatch: opts.dispatch ?? (() => {}),
    exit: opts.exit ?? (() => {}),
  };
}

test('registry get resolves a registered command and returns undefined otherwise', () => {
  const reg = buildRegistry();
  assert.equal(reg.get('exit')?.spec.name, 'exit');
  assert.equal(reg.get('stop')?.spec.name, 'stop');
  assert.equal(reg.get('nope'), undefined);
});

test('registry match returns prefix matches sorted', () => {
  const reg = buildRegistry();
  assert.deepEqual(reg.match('ex').map((d) => d.spec.name), ['exit']);
  assert.deepEqual(reg.match('s').map((d) => d.spec.name), ['stop']);
  assert.deepEqual(reg.match('').map((d) => d.spec.name), ['exit', 'stop']);
  assert.deepEqual(reg.match('z').map((d) => d.spec.name), []);
});

test('registry is extensible: a new command is matchable and runnable', async () => {
  const reg = new CommandRegistry();
  let ran = false;
  const cmd: CommandDefinition = {
    spec: { name: 'scan', description: 'do a scan', params: [{ name: 'target', description: 't', required: true }] },
    run: () => {
      ran = true;
    },
  };
  reg.register(cmd);
  assert.equal(reg.get('scan'), cmd);
  assert.deepEqual(reg.match('sc').map((d) => d.spec.name), ['scan']);
  await reg.get('scan')!.run([], fakeCtx({ client: {} }));
  assert.equal(ran, true);
});

test('/exit deletes the conversation then exits', async () => {
  const calls: string[] = [];
  await exitCommand.run(
    [],
    fakeCtx({
      shortId: 7,
      client: {
        deleteConversation: async (id: number) => {
          calls.push(`delete:${id}`);
        },
      },
      exit: () => calls.push('exit'),
    }),
  );
  assert.deepEqual(calls, ['delete:7', 'exit']);
});

test('/exit still exits when the delete request fails', async () => {
  let exited = false;
  await exitCommand.run(
    [],
    fakeCtx({
      client: {
        deleteConversation: async () => {
          throw new Error('network');
        },
      },
      exit: () => {
        exited = true;
      },
    }),
  );
  assert.equal(exited, true);
});

test('/stop calls stopAgent for the session', async () => {
  let stopped = -1;
  await stopCommand.run(
    [],
    fakeCtx({
      shortId: 4,
      client: {
        stopAgent: async (id: number) => {
          stopped = id;
        },
      },
    }),
  );
  assert.equal(stopped, 4);
});
