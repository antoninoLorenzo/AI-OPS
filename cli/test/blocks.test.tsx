import test from 'node:test';
import assert from 'node:assert/strict';
import React from 'react';
import { render } from 'ink-testing-library';

import { TerminalBlock, statusCircle, TerminalResultSchema } from '../src/blocks/TerminalBlock.tsx';
import { LoadSkillBlock } from '../src/blocks/LoadSkillBlock.tsx';
import { WriteFileBlock } from '../src/blocks/WriteFileBlock.tsx';
import { WhiteboardBlock } from '../src/blocks/WhiteboardBlock.tsx';
import { GenericToolBlock } from '../src/blocks/GenericToolBlock.tsx';
import { ReasoningBlock } from '../src/blocks/ReasoningBlock.tsx';
import { TextBlock } from '../src/blocks/TextBlock.tsx';
import { ToolBlockView } from '../src/blocks/ToolBlockView.tsx';
import type { ToolBlock, TextBlock as TextBlockData } from '../src/state/sessionReducer.ts';
import { stripAnsi } from './helpers.ts';

function frame(node: React.ReactElement): string {
  return stripAnsi(render(node).lastFrame() ?? '');
}

function tool(overrides: Partial<ToolBlock>): ToolBlock {
  return {
    type: 'tool',
    id: 'blk-1',
    callId: 'c1',
    name: 'terminal',
    args: {},
    requiresConfirmation: false,
    status: 'pending',
    ...overrides,
  };
}

// --- statusCircle (pure mapping) --------------------------------------------

test('statusCircle maps exit status and timeout to colors', () => {
  const base = { session_id: 's', command: 'x', allowed: true, timed_out: false };
  assert.equal(statusCircle(TerminalResultSchema.parse({ ...base, status: 0 })), 'green');
  assert.equal(statusCircle(TerminalResultSchema.parse({ ...base, status: 1 })), 'red');
  assert.equal(statusCircle(TerminalResultSchema.parse({ ...base, status: 127 })), 'red');
  assert.equal(statusCircle(TerminalResultSchema.parse({ ...base, status: -1 })), 'empty');
  assert.equal(statusCircle(TerminalResultSchema.parse({ ...base, status: null })), 'empty');
  assert.equal(
    statusCircle(TerminalResultSchema.parse({ ...base, status: 0, timed_out: true })),
    'yellow',
    'timeout takes precedence over exit status',
  );
});

// --- TerminalBlock ----------------------------------------------------------

test('terminal issued shows an empty circle and the command', () => {
  const f = frame(<TerminalBlock block={tool({ args: { command: 'ls -la' } })} />);
  assert.match(f, /○ \$ ls -la/);
});

test('terminal completed shows a filled circle, command and output', () => {
  const f = frame(
    <TerminalBlock
      block={tool({
        status: 'done',
        args: { command: 'whoami' },
        result: { session_id: 's', command: 'whoami', allowed: true, status: 0, output: 'root' },
      })}
    />,
  );
  assert.match(f, /● \$ whoami/);
  assert.match(f, /root/);
});

test('terminal blocked shows [BLOCKED] and no output', () => {
  const f = frame(
    <TerminalBlock
      block={tool({
        status: 'rejected-timeout',
        args: { command: 'rm -rf /' },
        result: { session_id: 's', command: 'rm -rf /', allowed: false },
      })}
    />,
  );
  assert.match(f, /\[BLOCKED\] \$ rm -rf \//);
});

test('terminal output is not truncated in the block content', () => {
  const output = Array.from({ length: 5 }, (_, i) => `row-${i}`).join('\n');
  const f = frame(
    <TerminalBlock
      block={tool({
        status: 'done',
        args: { command: 'cat f' },
        result: { session_id: 's', command: 'cat f', allowed: true, status: 0, output },
      })}
    />,
  );
  for (let i = 0; i < 5; i++) assert.match(f, new RegExp(`row-${i}`));
});

// --- LoadSkillBlock ---------------------------------------------------------

test('load_skill shows the loaded skill name', () => {
  const f = frame(
    <LoadSkillBlock
      block={tool({
        name: 'load_skill',
        status: 'done',
        args: { skill_id: 'recon' },
        result: { skill: { name: 'recon', description: 'd', content: 'c' } },
      })}
    />,
  );
  assert.match(f, /loaded skill: recon/);
});

test('load_skill shows "not found" when the skill is null', () => {
  const f = frame(
    <LoadSkillBlock
      block={tool({ name: 'load_skill', status: 'done', args: { skill_id: 'nope' }, result: { skill: null } })}
    />,
  );
  assert.match(f, /loaded skill: not found/);
});

// --- WriteFileBlock ---------------------------------------------------------

test('write_file shows the path and content when issued', () => {
  const f = frame(
    <WriteFileBlock
      block={tool({ name: 'write_file', args: { path: 'exploit.py', content: 'print(1)' } })}
    />,
  );
  assert.match(f, /Writing to exploit\.py/);
  assert.match(f, /print\(1\)/);
});

test('write_file shows the tree view on success', () => {
  const f = frame(
    <WriteFileBlock
      block={tool({
        name: 'write_file',
        status: 'done',
        args: { path: 'a.txt', content: 'x' },
        result: { tree_view: 'workspace/\n└── a.txt' },
      })}
    />,
  );
  assert.match(f, /└── a\.txt/);
});

test('write_file shows the error when writing fails', () => {
  const f = frame(
    <WriteFileBlock
      block={tool({
        name: 'write_file',
        status: 'done',
        args: { path: '../escape', content: 'x' },
        result: { error: 'not_authorized' },
      })}
    />,
  );
  assert.match(f, /write_file error: not_authorized/);
});

// --- WhiteboardBlock --------------------------------------------------------

test('whiteboard collapsed shows name and description but not content', () => {
  const f = frame(
    <WhiteboardBlock
      block={tool({
        name: 'write_whiteboard',
        args: { name: 'finding-1', description: 'open port 80', content: 'nginx 1.18 detected' },
      })}
    />,
  );
  assert.match(f, /finding-1: open port 80/);
  assert.doesNotMatch(f, /nginx 1\.18 detected/);
});

test('whiteboard expanded reveals the content', () => {
  const f = frame(
    <WhiteboardBlock
      expanded
      block={tool({
        name: 'write_whiteboard',
        args: { name: 'finding-1', description: 'open port 80', content: 'nginx 1.18 detected' },
      })}
    />,
  );
  assert.match(f, /nginx 1\.18 detected/);
});

// --- GenericToolBlock -------------------------------------------------------

test('generic tool renders name, args and result json', () => {
  const f = frame(
    <GenericToolBlock
      block={tool({ name: 'mystery', args: { foo: 'bar' }, status: 'done', result: { ok: true } })}
    />,
  );
  assert.match(f, /mystery/);
  assert.match(f, /foo/);
  assert.match(f, /ok/);
});

// --- ReasoningBlock ---------------------------------------------------------

test('reasoning is hidden by default and revealed on toggle', () => {
  const hidden = frame(<ReasoningBlock content="secret plan" revealed={false} />);
  assert.doesNotMatch(hidden, /secret plan/);
  assert.match(hidden, /reasoning hidden/);

  const shown = frame(<ReasoningBlock content="secret plan" revealed={true} />);
  assert.match(shown, /secret plan/);
});

// --- TextBlock --------------------------------------------------------------

test('text block renders content and a cursor only while streaming', () => {
  const streaming: TextBlockData = { type: 'text', id: 'blk-1', content: 'partial', streaming: true };
  const done: TextBlockData = { type: 'text', id: 'blk-2', content: 'complete', streaming: false };
  assert.match(frame(<TextBlock block={streaming} />), /partial▋/);
  const doneFrame = frame(<TextBlock block={done} />);
  assert.match(doneFrame, /complete/);
  assert.doesNotMatch(doneFrame, /▋/);
});

// --- ToolBlockView dispatch -------------------------------------------------

test('tool errors render uniformly regardless of tool', () => {
  const f = frame(
    <ToolBlockView
      reasoningRevealed={false}
      block={tool({
        name: 'terminal',
        status: 'error',
        error: { failure: 'execution_error', message: 'segfault' },
      })}
    />,
  );
  assert.match(f, /✗ terminal execution_error: segfault/);
});

test('think tool renders its thought like reasoning (hidden by default)', () => {
  const block = tool({ name: 'think', status: 'done', args: { thought: 'I will scan first' }, result: {} });
  assert.doesNotMatch(frame(<ToolBlockView reasoningRevealed={false} block={block} />), /I will scan first/);
  assert.match(frame(<ToolBlockView reasoningRevealed={true} block={block} />), /I will scan first/);
});

test('ToolBlockView routes each tool name to its renderer', () => {
  assert.match(
    frame(<ToolBlockView reasoningRevealed={false} block={tool({ name: 'terminal', args: { command: 'id' } })} />),
    /\$ id/,
  );
  assert.match(
    frame(
      <ToolBlockView
        reasoningRevealed={false}
        block={tool({ name: 'load_skill', status: 'done', args: { skill_id: 'x' }, result: { skill: null } })}
      />,
    ),
    /loaded skill:/,
  );
  assert.match(
    frame(<ToolBlockView reasoningRevealed={false} block={tool({ name: 'unknown_tool', args: { a: 1 } })} />),
    /unknown_tool/,
  );
});
