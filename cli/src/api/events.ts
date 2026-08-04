// Event taxonomy mirrored from `ai_ops.core.schema`. Each NDJSON line is parsed
// through a zod discriminated union keyed on `kind`; a line that fails
// validation raises rather than being silently dropped or mis-rendered.
import { z } from 'zod';

// `kind` values are the lowercased `StrEnum.auto()` names from the backend.
export const EventKind = {
  UserMessage: 'user_message',
  Text: 'text',
  Reasoning: 'reasoning',
  ToolCall: 'tool_call',
  ToolResult: 'tool_result',
  ToolError: 'tool_error',
  Stop: 'stop',
  ToolConfirmation: 'tool_confirmation',
} as const;

// Tool `args`/`result` are arbitrary serialized pydantic models. At the union
// level they are kept as opaque objects; per-tool renderers narrow them with
// the dedicated schemas exported below.
const ToolPayload = z.record(z.string(), z.unknown());

export const UserMessageEventSchema = z.object({
  kind: z.literal(EventKind.UserMessage),
  content: z.string(),
});

export const TextEventSchema = z.object({
  kind: z.literal(EventKind.Text),
  chunk: z.string(),
  stream: z.boolean().default(false),
  stream_done: z.boolean().default(false),
});

export const ReasoningEventSchema = z.object({
  kind: z.literal(EventKind.Reasoning),
  chunk: z.string(),
});

export const ToolCallEventSchema = z.object({
  kind: z.literal(EventKind.ToolCall),
  call_id: z.string(),
  name: z.string(),
  args: ToolPayload,
  requires_confirmation: z.boolean().default(false),
});

export const ToolResultEventSchema = z.object({
  kind: z.literal(EventKind.ToolResult),
  call_id: z.string(),
  name: z.string(),
  args: ToolPayload,
  result: ToolPayload,
});

export const ToolErrorEventSchema = z.object({
  kind: z.literal(EventKind.ToolError),
  failure: z.enum(['validation_error', 'execution_error']),
  tool_call_id: z.string(),
  name: z.string(),
  error: z.string(),
});

export const StopEventSchema = z.object({
  kind: z.literal(EventKind.Stop),
  issuer: z.enum(['agent', 'user']),
  reason: z.string().nullish(),
  max_iteration: z.boolean().default(false),
  error: z.string().nullish(),
});

// Client -> server only; never received over the stream, so it is not part of
// the received union but is exported for the confirmation flow.
export const ToolConfirmationEventSchema = z.object({
  kind: z.literal(EventKind.ToolConfirmation),
  call_id: z.string(),
  approved: z.boolean(),
});

// Received event union. Mirrors `AnyEvent` minus the client-only confirmation.
export const AnyEventSchema = z.discriminatedUnion('kind', [
  UserMessageEventSchema,
  TextEventSchema,
  ReasoningEventSchema,
  ToolCallEventSchema,
  ToolResultEventSchema,
  ToolErrorEventSchema,
  StopEventSchema,
]);

export type UserMessageEvent = z.infer<typeof UserMessageEventSchema>;
export type TextEvent = z.infer<typeof TextEventSchema>;
export type ReasoningEvent = z.infer<typeof ReasoningEventSchema>;
export type ToolCallEvent = z.infer<typeof ToolCallEventSchema>;
export type ToolResultEvent = z.infer<typeof ToolResultEventSchema>;
export type ToolErrorEvent = z.infer<typeof ToolErrorEventSchema>;
export type StopEvent = z.infer<typeof StopEventSchema>;
export type ToolConfirmationEvent = z.infer<typeof ToolConfirmationEventSchema>;
export type AnyEvent = z.infer<typeof AnyEventSchema>;

export class EventParseError extends Error {
  readonly line: string;
  constructor(message: string, line: string) {
    super(message);
    this.name = 'EventParseError';
    this.line = line;
  }
}

// Parses a single NDJSON line into a narrowed event. Raises EventParseError on
// invalid JSON or a payload that does not match the union.
export function parseEventLine(line: string): AnyEvent {
  let json: unknown;
  try {
    json = JSON.parse(line);
  } catch {
    throw new EventParseError('Invalid JSON in event stream', line);
  }
  const result = AnyEventSchema.safeParse(json);
  if (!result.success) {
    const issues = result.error.issues
      .map((issue) => `${issue.path.join('.') || '(root)'}: ${issue.message}`)
      .join('; ');
    throw new EventParseError(`Unrecognized event: ${issues}`, line);
  }
  return result.data;
}
