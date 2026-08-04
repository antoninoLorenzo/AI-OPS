// Drives the agent stream: starts a run, dispatches one action per parsed
// event, refreshes token usage after each ToolResult/ToolError/Stop, and
// exposes send/confirm/stop. A ref guards against concurrent starts (a fresh
// prompt while already running goes through `send`, not `start`).
import { useCallback, useRef } from 'react';
import type { ApiClient } from '../api/client.js';
import type { Action, Mode } from '../state/sessionReducer.js';

export interface AgentStream {
  start: (content: string) => Promise<void>;
  send: (content: string) => Promise<void>;
  confirm: (callId: string, approved: boolean) => Promise<void>;
  stop: () => Promise<void>;
}

export function useAgentStream({
  client,
  shortId,
  mode,
  dispatch,
}: {
  client: ApiClient;
  shortId: number;
  mode: Mode;
  dispatch: (action: Action) => void;
}): AgentStream {
  const runningRef = useRef(false);

  const refreshUsage = useCallback(async () => {
    try {
      const usage = await client.getUsage(shortId);
      dispatch({ type: 'SET_USAGE', totalTokens: usage.total_tokens });
    } catch {
      // Usage is advisory; never break the run over a failed refresh.
    }
  }, [client, shortId, dispatch]);

  const start = useCallback(
    async (content: string) => {
      if (runningRef.current) return;
      runningRef.current = true;
      dispatch({ type: 'SUBMIT_PROMPT', content });
      dispatch({ type: 'STREAM_START' });
      try {
        for await (const event of client.startAgent(shortId, content, mode)) {
          dispatch({ type: 'EVENT', event });
          if (event.kind === 'tool_result' || event.kind === 'tool_error' || event.kind === 'stop') {
            await refreshUsage();
          }
        }
      } catch (err) {
        dispatch({ type: 'STREAM_ERROR', message: (err as Error).message });
      } finally {
        runningRef.current = false;
      }
    },
    [client, shortId, mode, dispatch, refreshUsage],
  );

  const send = useCallback(
    async (content: string) => {
      try {
        await client.sendMessage(shortId, content);
        dispatch({ type: 'ENQUEUE_MESSAGE', content });
      } catch {
        // 404/409: the message was not accepted; leave the input unblocked.
      }
    },
    [client, shortId, dispatch],
  );

  const confirm = useCallback(
    async (callId: string, approved: boolean) => {
      try {
        await client.confirmToolCall(shortId, callId, approved);
        // Only record the acknowledgment when the backend accepted it; a failed
        // POST leaves the call awaiting, and its backend timeout resolves it.
        dispatch({ type: 'CONFIRMATION_SENT', callId, approved });
      } catch {
        /* leave awaiting; the confirmation timeout will settle it */
      }
    },
    [client, shortId, dispatch],
  );

  const stop = useCallback(async () => {
    try {
      await client.stopAgent(shortId);
    } catch {
      /* best effort */
    }
  }, [client, shortId]);

  return { start, send, confirm, stop };
}
