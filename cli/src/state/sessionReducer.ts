// Pure session state reduction. Every case in `applyEvent` mirrors an entry in
// the spec's "Event Stream" table one-to-one; the NDJSON read loop dispatches
// exactly one `EVENT` action per parsed line. Keeping this a pure reducer (vs.
// scattered useState setters) avoids stale closures in the read loop, where an
// `await` sits between every chunk.
//
// Object identity is preserved for blocks that did not change: every update
// touches only the affected block, so `React.memo` on block components stays
// effective. Ids are generated from an in-state counter so reductions are
// deterministic and testable (no Date.now/random).
import type { AnyEvent } from '../api/events.js';

export type Mode = 'supervised' | 'unsupervised';

export type SessionStatus = 'idle' | 'running' | 'awaiting-confirmation' | 'stopped' | 'error';

// Which surface owns keyboard focus. Arbitrated centrally so exactly one of the
// input field, the confirmation form, or the completion dropdown is active.
export type InputMode = 'input' | 'confirmation' | 'completion';

export interface ModelInfo {
  provider: string;
  modelId: string;
  maxContextLength: number | null;
}

// --- Blocks -----------------------------------------------------------------

export type ToolStatus =
  | 'pending'
  | 'awaiting-confirmation'
  | 'done'
  | 'error'
  | 'rejected-timeout';

export interface UserBlock {
  type: 'user';
  id: string;
  content: string;
}

export interface TextBlock {
  type: 'text';
  id: string;
  content: string;
  streaming: boolean;
}

export interface ReasoningBlock {
  type: 'reasoning';
  id: string;
  content: string;
}

export interface ToolBlock {
  type: 'tool';
  id: string;
  callId: string;
  name: string;
  args: Record<string, unknown>;
  requiresConfirmation: boolean;
  status: ToolStatus;
  result?: Record<string, unknown>;
  error?: { failure: string; message: string };
}

export interface StopBlock {
  type: 'stop';
  id: string;
  issuer: 'agent' | 'user';
  reason: string | null;
  error: string | null;
  maxIteration: boolean;
}

// Client-side stream/transport failure (not a StopEvent from the agent).
export interface ErrorBlock {
  type: 'error';
  id: string;
  message: string;
}

export type Block =
  | UserBlock
  | TextBlock
  | ReasoningBlock
  | ToolBlock
  | StopBlock
  | ErrorBlock;

// --- State ------------------------------------------------------------------

export interface SessionState {
  status: SessionStatus;
  inputMode: InputMode;
  blocks: Block[];
  model: ModelInfo | null;
  shortId: number | null;
  mode: Mode;
  totalTokens: number;
  // FIFO of call_ids blocking on user confirmation, in order of arrival. The
  // head is the one whose form is shown; a call leaves the queue when the user
  // answers it or a result/error arrives for it (the backend-timeout path).
  // A queue (not a single target) so a second confirmation-required call does
  // not strand the first — each carries its own backend timeout.
  confirmationQueue: string[];
  // A user message posted to a running agent that has not been drained yet.
  // While set, the input blocks new prompts.
  enqueuedMessage: boolean;
  // Tool calls in flight (issued, no result/error yet). Used to detect when an
  // enqueued message has drained (the agent drains when none are pending).
  pendingToolCalls: number;
  // call_ids the user acknowledged (y/n). A confirmation-required result whose
  // call was never acknowledged was rejected by the backend timeout.
  acknowledged: Record<string, true>;
  // Open accumulation blocks; null when no block of that kind is in progress.
  openTextId: string | null;
  openReasoningId: string | null;
  // Monotonic id source for generated block ids.
  seq: number;
  // Last fatal error message, mirrored from an error block / stop.error.
  error: string | null;
}

export function initialState(mode: Mode = 'supervised'): SessionState {
  return {
    status: 'idle',
    inputMode: 'input',
    blocks: [],
    model: null,
    shortId: null,
    mode,
    totalTokens: 0,
    confirmationQueue: [],
    enqueuedMessage: false,
    pendingToolCalls: 0,
    acknowledged: {},
    openTextId: null,
    openReasoningId: null,
    seq: 0,
    error: null,
  };
}

// --- Actions ----------------------------------------------------------------

export type Action =
  | { type: 'SET_MODEL'; model: ModelInfo }
  | { type: 'SET_SESSION'; shortId: number; mode: Mode }
  | { type: 'SET_USAGE'; totalTokens: number }
  | { type: 'STREAM_START' }
  | { type: 'STREAM_ERROR'; message: string }
  | { type: 'EVENT'; event: AnyEvent }
  | { type: 'LOAD_EVENTS'; events: AnyEvent[] }
  | { type: 'SUBMIT_PROMPT'; content: string }
  | { type: 'ENQUEUE_MESSAGE'; content: string }
  | { type: 'CONFIRMATION_SENT'; callId: string; approved: boolean }
  | { type: 'SET_INPUT_MODE'; mode: InputMode };

// --- Block helpers (immutable) ----------------------------------------------

function nextId(state: SessionState): [string, number] {
  const seq = state.seq + 1;
  return [`blk-${seq}`, seq];
}

// Replaces exactly one block by id, preserving the identity of all others.
function mapBlock(blocks: Block[], id: string, fn: (b: Block) => Block): Block[] {
  return blocks.map((b) => (b.id === id ? fn(b) : b));
}

function findTool(blocks: Block[], callId: string): ToolBlock | undefined {
  for (const b of blocks) {
    if (b.type === 'tool' && b.callId === callId) return b;
  }
  return undefined;
}

// Finalizes an open streaming text block (streaming -> false) if one is open.
function finalizeText(state: SessionState): Pick<SessionState, 'blocks' | 'openTextId'> {
  if (state.openTextId === null) return { blocks: state.blocks, openTextId: null };
  const blocks = mapBlock(state.blocks, state.openTextId, (b) =>
    b.type === 'text' ? { ...b, streaming: false } : b,
  );
  return { blocks, openTextId: null };
}

// Closing reasoning needs no block mutation; it just stops accumulation.
function closeReasoning(): Pick<SessionState, 'openReasoningId'> {
  return { openReasoningId: null };
}

// --- Event reduction --------------------------------------------------------

interface ApplyOptions {
  // Historical replay (resume): build blocks but suppress live side effects
  // (running status, confirmation prompts, timeout labeling, enqueue draining).
  historical: boolean;
}

function applyEvent(state: SessionState, event: AnyEvent, opts: ApplyOptions): SessionState {
  const { historical } = opts;

  switch (event.kind) {
    case 'user_message': {
      // Streamed only on resume; live user messages come via SUBMIT/ENQUEUE.
      const closedText = finalizeText(state);
      const [id, seq] = nextId(state);
      const block: UserBlock = { type: 'user', id, content: event.content };
      return {
        ...state,
        ...closedText,
        ...closeReasoning(),
        blocks: [...closedText.blocks, block],
        seq,
      };
    }

    case 'text': {
      // Reasoning cannot continue across a text event.
      const closedReasoning = closeReasoning();

      if (event.stream) {
        if (state.openTextId !== null) {
          const openId = state.openTextId;
          const blocks = mapBlock(state.blocks, openId, (b) =>
            b.type === 'text'
              ? { ...b, content: b.content + event.chunk, streaming: !event.stream_done }
              : b,
          );
          return {
            ...state,
            ...closedReasoning,
            blocks,
            openTextId: event.stream_done ? null : openId,
          };
        }
        const [id, seq] = nextId(state);
        const block: TextBlock = {
          type: 'text',
          id,
          content: event.chunk,
          streaming: !event.stream_done,
        };
        return {
          ...state,
          ...closedReasoning,
          blocks: [...state.blocks, block],
          openTextId: event.stream_done ? null : id,
          seq,
        };
      }

      // Non-streamed: render as one finalized block.
      const closedText = finalizeText(state);
      const [id, seq] = nextId(state);
      const block: TextBlock = { type: 'text', id, content: event.chunk, streaming: false };
      return {
        ...state,
        ...closedReasoning,
        ...closedText,
        blocks: [...closedText.blocks, block],
        seq,
      };
    }

    case 'reasoning': {
      // Text streaming cannot continue across a reasoning event.
      const closedText = finalizeText(state);
      if (state.openReasoningId !== null) {
        const openId = state.openReasoningId;
        const blocks = mapBlock(closedText.blocks, openId, (b) =>
          b.type === 'reasoning' ? { ...b, content: b.content + event.chunk } : b,
        );
        return { ...state, ...closedText, blocks };
      }
      const [id, seq] = nextId(state);
      const block: ReasoningBlock = { type: 'reasoning', id, content: event.chunk };
      return {
        ...state,
        ...closedText,
        blocks: [...closedText.blocks, block],
        openReasoningId: id,
        seq,
      };
    }

    case 'tool_call': {
      const closedText = finalizeText(state);
      const [id, seq] = nextId(state);
      const requires = event.requires_confirmation;
      const block: ToolBlock = {
        type: 'tool',
        id,
        callId: event.call_id,
        name: event.name,
        args: event.args,
        requiresConfirmation: requires,
        status: requires && !historical ? 'awaiting-confirmation' : 'pending',
      };
      const base: SessionState = {
        ...state,
        ...closedText,
        ...closeReasoning(),
        blocks: [...closedText.blocks, block],
        pendingToolCalls: state.pendingToolCalls + 1,
        seq,
      };
      if (requires && !historical) {
        // Append to the queue in arrival order; the head owns the form.
        return {
          ...base,
          status: 'awaiting-confirmation',
          inputMode: 'confirmation',
          confirmationQueue: [...state.confirmationQueue, event.call_id],
        };
      }
      return base;
    }

    case 'tool_result': {
      const closedText = finalizeText(state);
      const existing = findTool(closedText.blocks, event.call_id);
      let blocks: Block[];
      if (existing) {
        const rejectedByTimeout =
          !historical && existing.requiresConfirmation && state.acknowledged[event.call_id] !== true;
        blocks = mapBlock(closedText.blocks, existing.id, (b) =>
          b.type === 'tool'
            ? { ...b, result: event.result, status: rejectedByTimeout ? 'rejected-timeout' : 'done' }
            : b,
        );
      } else {
        // Result with no preceding call (shouldn't happen); render standalone.
        const [id, seq] = nextId(state);
        const block: ToolBlock = {
          type: 'tool',
          id,
          callId: event.call_id,
          name: event.name,
          args: event.args,
          requiresConfirmation: false,
          status: 'done',
          result: event.result,
        };
        return {
          ...state,
          ...closedText,
          ...closeReasoning(),
          blocks: [...closedText.blocks, block],
          seq,
        };
      }
      const settledResult = afterToolSettled(
        { ...state, ...closedText, ...closeReasoning(), blocks },
        historical,
      );
      // If this result resolves a queued confirmation (the backend-timeout
      // path, where the user never answered), drop it and advance the queue.
      return historical ? settledResult : resolveQueuedConfirmation(settledResult, event.call_id);
    }

    case 'tool_error': {
      const closedText = finalizeText(state);
      const existing = findTool(closedText.blocks, event.tool_call_id);
      let blocks: Block[];
      if (existing) {
        blocks = mapBlock(closedText.blocks, existing.id, (b) =>
          b.type === 'tool'
            ? { ...b, status: 'error', error: { failure: event.failure, message: event.error } }
            : b,
        );
      } else {
        const [id, seq] = nextId(state);
        const block: ToolBlock = {
          type: 'tool',
          id,
          callId: event.tool_call_id,
          name: event.name,
          args: {},
          requiresConfirmation: false,
          status: 'error',
          error: { failure: event.failure, message: event.error },
        };
        return {
          ...state,
          ...closedText,
          ...closeReasoning(),
          blocks: [...closedText.blocks, block],
          seq,
        };
      }
      const settledError = afterToolSettled(
        { ...state, ...closedText, ...closeReasoning(), blocks },
        historical,
      );
      return historical
        ? settledError
        : resolveQueuedConfirmation(settledError, event.tool_call_id);
    }

    case 'stop': {
      const closedText = finalizeText(state);
      let blocks = closedText.blocks;
      const informative =
        event.issuer === 'user' || !!event.reason || !!event.error || event.max_iteration;
      let seq = state.seq;
      if (informative) {
        const [id, nseq] = nextId(state);
        seq = nseq;
        const block: StopBlock = {
          type: 'stop',
          id,
          issuer: event.issuer,
          reason: event.reason ?? null,
          error: event.error ?? null,
          maxIteration: event.max_iteration,
        };
        blocks = [...blocks, block];
      }
      const status: SessionStatus = historical ? state.status : event.error ? 'error' : 'stopped';
      return {
        ...state,
        ...closedText,
        ...closeReasoning(),
        blocks,
        seq,
        status,
        // The stream ended: any confirmation prompts are moot and input frees up.
        inputMode: historical ? state.inputMode : 'input',
        confirmationQueue: historical ? state.confirmationQueue : [],
        enqueuedMessage: historical ? state.enqueuedMessage : false,
        error: event.error ?? state.error,
      };
    }

    default: {
      // Exhaustiveness: AnyEvent has no other kinds.
      const _never: never = event;
      return _never;
    }
  }
}

// Shared bookkeeping after a tool call settles (result or error): decrement the
// pending count and, once nothing is pending, release any enqueued message
// (the agent drains it at the next boundary with no pending tool calls).
function afterToolSettled(state: SessionState, historical: boolean): SessionState {
  const pending = Math.max(0, state.pendingToolCalls - 1);
  const enqueuedMessage = !historical && pending === 0 ? false : state.enqueuedMessage;
  return { ...state, pendingToolCalls: pending, enqueuedMessage };
}

// Removes a call from the confirmation queue and recomputes focus/status. If
// another confirmation remains, its form takes over (still blocked on the
// user); otherwise focus returns to the input and the agent resumes running.
// A no-op when the call was not awaiting confirmation.
function resolveQueuedConfirmation(state: SessionState, callId: string): SessionState {
  if (!state.confirmationQueue.includes(callId)) return state;
  const confirmationQueue = state.confirmationQueue.filter((id) => id !== callId);
  if (confirmationQueue.length > 0) {
    return { ...state, confirmationQueue, status: 'awaiting-confirmation', inputMode: 'confirmation' };
  }
  return { ...state, confirmationQueue, status: 'running', inputMode: 'input' };
}

// --- Reducer ----------------------------------------------------------------

export function sessionReducer(state: SessionState, action: Action): SessionState {
  switch (action.type) {
    case 'SET_MODEL':
      return { ...state, model: action.model };

    case 'SET_SESSION':
      return { ...state, shortId: action.shortId, mode: action.mode };

    case 'SET_USAGE':
      return { ...state, totalTokens: action.totalTokens };

    case 'STREAM_START':
      return { ...state, status: 'running', error: null };

    case 'STREAM_ERROR': {
      const [id, seq] = nextId(state);
      const block: ErrorBlock = { type: 'error', id, message: action.message };
      const closedText = finalizeText(state);
      return {
        ...state,
        ...closedText,
        ...closeReasoning(),
        blocks: [...closedText.blocks, block],
        seq,
        status: 'error',
        inputMode: 'input',
        confirmationQueue: [],
        enqueuedMessage: false,
        pendingToolCalls: 0,
        error: action.message,
      };
    }

    case 'EVENT':
      return applyEvent(state, action.event, { historical: false });

    case 'LOAD_EVENTS': {
      // Fold historical events, then settle into a resumable idle state.
      let next = action.events.reduce(
        (acc, event) => applyEvent(acc, event, { historical: true }),
        state,
      );
      next = finalizeState(next);
      return { ...next, status: 'idle', inputMode: 'input', confirmationQueue: [] };
    }

    case 'SUBMIT_PROMPT': {
      const closedText = finalizeText(state);
      const [id, seq] = nextId(state);
      const block: UserBlock = { type: 'user', id, content: action.content };
      return {
        ...state,
        ...closedText,
        ...closeReasoning(),
        blocks: [...closedText.blocks, block],
        seq,
      };
    }

    case 'ENQUEUE_MESSAGE': {
      const closedText = finalizeText(state);
      const [id, seq] = nextId(state);
      const block: UserBlock = { type: 'user', id, content: action.content };
      return {
        ...state,
        ...closedText,
        blocks: [...closedText.blocks, block],
        seq,
        enqueuedMessage: true,
      };
    }

    case 'CONFIRMATION_SENT': {
      const acknowledged = { ...state.acknowledged, [action.callId]: true as const };
      // The answered tool proceeds to execution; mark its block pending again.
      const blocks = mapBlock(state.blocks, findToolId(state.blocks, action.callId), (b) =>
        b.type === 'tool' ? { ...b, status: 'pending' } : b,
      );
      // Advance the queue: focus returns to the input only once none remain.
      return resolveQueuedConfirmation({ ...state, acknowledged, blocks }, action.callId);
    }

    case 'SET_INPUT_MODE':
      // A pending confirmation owns focus; typing cannot steal it.
      if (state.inputMode === 'confirmation') return state;
      return { ...state, inputMode: action.mode };

    default: {
      const _never: never = action;
      return _never;
    }
  }
}

// Resolves a tool block id by call id (empty string if absent, which mapBlock
// simply never matches).
function findToolId(blocks: Block[], callId: string): string {
  return findTool(blocks, callId)?.id ?? '';
}

// Finalizes any open accumulation blocks (used after historical replay).
function finalizeState(state: SessionState): SessionState {
  const closedText = finalizeText(state);
  return { ...state, ...closedText, ...closeReasoning() };
}

// --- Selectors --------------------------------------------------------------

export function isRunning(state: SessionState): boolean {
  return state.status === 'running' || state.status === 'awaiting-confirmation';
}

// The confirmation whose form is currently shown (head of the queue), or null.
export function activeConfirmation(state: SessionState): string | null {
  return state.confirmationQueue[0] ?? null;
}

// New prompts are blocked while a confirmation owns focus or a message is
// already enqueued for the running agent.
export function canSubmitPrompt(state: SessionState): boolean {
  return state.inputMode !== 'confirmation' && !state.enqueuedMessage;
}
