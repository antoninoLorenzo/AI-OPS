// Top-level app: owns the session reducer, arbitrates focus between the input
// and the confirmation form, handles the global reasoning toggle, and routes
// submissions to either a command, a fresh run, or an enqueued message.
//
// Child order is load-bearing: the status bar renders last so it stays at the
// bottom of the viewport once the transcript outgrows the terminal.
import React, { useCallback, useEffect, useMemo, useReducer, useState } from 'react';
import { Box, useApp, useInput, useStdout } from 'ink';
import type { ApiClient } from '../api/client.js';
import type { AnyEvent } from '../api/events.js';
import {
  sessionReducer,
  initialState,
  isRunning,
  canSubmitPrompt,
  activeConfirmation,
  settledCount,
  type Mode,
  type ModelInfo,
  type ToolBlock,
} from '../state/sessionReducer.js';
import { StatusBar } from './StatusBar.js';
import { Transcript } from './Transcript.js';
import { InputBar } from './InputBar.js';
import { ConfirmationForm } from './ConfirmationForm.js';
import { useAgentStream } from '../hooks/useAgentStream.js';
import { buildRegistry } from '../commands/index.js';

// Erase the screen (2J), erase the scrollback (3J), home the cursor (H). Same
// sequence Ink itself uses when it has to redraw from scratch.
const CLEAR_TERMINAL = '\u001B[2J\u001B[3J\u001B[H';

// A short description of the tool call awaiting confirmation.
function confirmationLabel(block: ToolBlock | undefined): string {
  if (!block) return '';
  if (block.name === 'terminal') {
    const command = (block.args as { command?: unknown }).command;
    if (typeof command === 'string') return `${block.name} $ ${command}`;
  }
  return block.name;
}

export function App({
  client,
  model,
  shortId,
  mode,
  initialEvents,
  initialTotalTokens = 0,
}: {
  client: ApiClient;
  model: ModelInfo;
  shortId: number;
  mode: Mode;
  initialEvents?: AnyEvent[];
  initialTotalTokens?: number;
}) {
  const [state, dispatch] = useReducer(sessionReducer, mode, initialState);
  const [reasoningRevealed, setReasoningRevealed] = useState(false);
  const { exit } = useApp();
  const registry = useMemo(() => buildRegistry(), []);
  const stream = useAgentStream({ client, shortId, mode, dispatch });

  // One-time hydration of the status bar, session and any resumed transcript.
  useEffect(() => {
    dispatch({ type: 'SET_MODEL', model });
    dispatch({ type: 'SET_SESSION', shortId, mode });
    if (initialEvents && initialEvents.length > 0) {
      dispatch({ type: 'LOAD_EVENTS', events: initialEvents });
      dispatch({ type: 'SET_USAGE', totalTokens: initialTotalTokens });
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Global reasoning visibility toggle (Ctrl+R).
  //
  // The settled transcript is in <Static>, which Ink writes once and cannot
  // rewrite, so a visibility change is applied by replaying it: flipping
  // `reasoningRevealed` also flips the Static key below, remounting it. The
  // screen is cleared here first, and the ordering matters. This runs in a key
  // handler, outside React, so the clear reaches the terminal before the render
  // that setState schedules; doing it in an effect would clear the replay Ink
  // had already committed.
  const { write } = useStdout();
  useInput((input, key) => {
    if (key.ctrl && input === 'r') {
      write(CLEAR_TERMINAL);
      setReasoningRevealed((r) => !r);
    }
  });

  const handleSubmit = useCallback(
    async (raw: string) => {
      const value = raw.trim();
      if (value.length === 0) return;

      if (value.startsWith('/')) {
        const parts = value.slice(1).split(/\s+/);
        const def = registry.get(parts[0]);
        if (def) {
          await def.run(parts.slice(1), { client, shortId, dispatch, exit });
        } else {
          dispatch({ type: 'STREAM_ERROR', message: `unknown command: /${parts[0]}` });
        }
        return;
      }

      // A prompt: enqueue for a running agent, otherwise start a fresh run.
      if (isRunning(state)) {
        if (canSubmitPrompt(state)) await stream.send(value);
      } else {
        await stream.start(value);
      }
    },
    [registry, client, shortId, exit, state, stream],
  );

  const confActive = state.inputMode === 'confirmation';
  const activeCallId = activeConfirmation(state);
  const confBlock = activeCallId
    ? (state.blocks.find((b) => b.type === 'tool' && b.callId === activeCallId) as ToolBlock | undefined)
    : undefined;
  // The input stays enabled while running (commands remain usable); only new
  // prompts are blocked while a message is already enqueued.
  const promptBlocked = isRunning(state) && !canSubmitPrompt(state);
  const settled = settledCount(state);

  return (
    <Box flexDirection="column">
      <Transcript
        blocks={state.blocks}
        settled={settled}
        reasoningRevealed={reasoningRevealed}
        replayKey={reasoningRevealed ? 'revealed' : 'hidden'}
      />
      {confActive ? (
        <ConfirmationForm
          active
          label={confirmationLabel(confBlock)}
          pendingCount={state.confirmationQueue.length}
          onApprove={() => activeCallId && stream.confirm(activeCallId, true)}
          onReject={() => activeCallId && stream.confirm(activeCallId, false)}
        />
      ) : (
        <InputBar active={!confActive} registry={registry} onSubmit={handleSubmit} blocked={promptBlocked} />
      )}
      <StatusBar
        model={state.model}
        mode={state.mode}
        shortId={state.shortId}
        totalTokens={state.totalTokens}
        running={state.status === 'running'}
      />
    </Box>
  );
}
