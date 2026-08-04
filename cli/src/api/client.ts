// Typed wrapper over the AI-OPS API. One method per endpoint; the API key (when
// configured) is sent in the `X-AI-OPS-ApiKey` header on every request. `fetch`
// is injectable so the client can be tested against a local server or a stub.
import { z } from 'zod';
import { AnyEventSchema, parseEventLine, type AnyEvent } from './events.js';
import { streamResponseLines } from './stream.js';

export const API_KEY_HEADER = 'X-AI-OPS-ApiKey';

export const ModelMetadataSchema = z.object({
  provider: z.string(),
  model_id: z.string(),
  max_context_length: z.number().nullish(),
  tool_use: z.boolean(),
  reasoning: z.boolean(),
  response_format: z.boolean(),
  structured_output: z.boolean(),
});
export type ModelMetadata = z.infer<typeof ModelMetadataSchema>;

export const ConversationSchema = z.object({
  uuid: z.string(),
  short_id: z.number().int(),
  messages: z.array(z.unknown()).default([]),
});
export type Conversation = z.infer<typeof ConversationSchema>;

export const UsageSchema = z.object({
  total_tokens: z.number(),
  max_context_length: z.number().nullable(),
});
export type Usage = z.infer<typeof UsageSchema>;

export type Mode = 'supervised' | 'unsupervised';

export type FetchFn = typeof fetch;

export interface ApiClientOptions {
  baseUrl: string;
  apiKey?: string;
  fetch?: FetchFn;
}

// Raised for any non-success HTTP response. `status` lets callers distinguish
// the documented cases (404 missing, 400 already-running / bad confirmation,
// 409 send conflict, 500 invalid conversation).
export class ApiError extends Error {
  readonly status: number;
  constructor(message: string, status: number) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
  }
}

export class ApiClient {
  private readonly baseUrl: string;
  private readonly apiKey?: string;
  private readonly fetchFn: FetchFn;

  constructor(options: ApiClientOptions) {
    // Trim a trailing slash so path joins are predictable.
    this.baseUrl = options.baseUrl.replace(/\/+$/, '');
    this.apiKey = options.apiKey;
    this.fetchFn = options.fetch ?? fetch;
  }

  private url(path: string): string {
    return `${this.baseUrl}${path}`;
  }

  private headers(extra?: Record<string, string>): Record<string, string> {
    const headers: Record<string, string> = { ...extra };
    if (this.apiKey) headers[API_KEY_HEADER] = this.apiKey;
    return headers;
  }

  private async request(path: string, init?: RequestInit): Promise<Response> {
    const response = await this.fetchFn(this.url(path), {
      ...init,
      headers: this.headers(init?.headers as Record<string, string> | undefined),
    });
    return response;
  }

  private async requestJson<T>(path: string, schema: z.ZodType<T>, init?: RequestInit): Promise<T> {
    const response = await this.request(path, init);
    if (!response.ok) {
      throw new ApiError(`${init?.method ?? 'GET'} ${path} failed`, response.status);
    }
    const json = await response.json();
    return schema.parse(json);
  }

  private jsonInit(method: string, body?: unknown): RequestInit {
    return {
      method,
      headers: { 'Content-Type': 'application/json' },
      body: body === undefined ? undefined : JSON.stringify(body),
    };
  }

  // GET /health — throws (network error or non-200) when the API is unreachable.
  async health(): Promise<void> {
    const response = await this.request('/health');
    if (!response.ok) {
      throw new ApiError('Health check failed', response.status);
    }
  }

  // GET /model
  async getModel(): Promise<ModelMetadata> {
    return this.requestJson('/model', ModelMetadataSchema);
  }

  // POST /conversation
  async createConversation(): Promise<Conversation> {
    return this.requestJson('/conversation', ConversationSchema, this.jsonInit('POST'));
  }

  // GET /conversation/{short_id} — throws ApiError(404) when missing.
  async loadConversation(shortId: number): Promise<AnyEvent[]> {
    const events = await this.requestJson(
      `/conversation/${shortId}`,
      z.array(AnyEventSchema),
    );
    return events;
  }

  // POST /conversation/{short_id} — streams NDJSON events. Throws ApiError(400)
  // if the agent is already running, ApiError(500) on invalid conversation.
  async *startAgent(shortId: number, content: string, mode: Mode): AsyncGenerator<AnyEvent> {
    const response = await this.request(
      `/conversation/${shortId}`,
      this.jsonInit('POST', { content, mode }),
    );
    if (!response.ok) {
      throw new ApiError(`Failed to start agent (short_id=${shortId})`, response.status);
    }
    for await (const line of streamResponseLines(response)) {
      yield parseEventLine(line);
    }
  }

  // POST /conversation/{short_id}/send — throws ApiError(404) if no agent,
  // ApiError(409) if not running or a message is already enqueued.
  async sendMessage(shortId: number, content: string): Promise<void> {
    const response = await this.request(
      `/conversation/${shortId}/send`,
      this.jsonInit('POST', { content }),
    );
    if (!response.ok) {
      throw new ApiError(`Failed to send message (short_id=${shortId})`, response.status);
    }
  }

  // POST /conversation/{short_id}/stop
  async stopAgent(shortId: number): Promise<void> {
    const response = await this.request(`/conversation/${shortId}/stop`, { method: 'POST' });
    if (!response.ok) {
      throw new ApiError(`Failed to stop agent (short_id=${shortId})`, response.status);
    }
  }

  // DELETE /conversation/{short_id}
  async deleteConversation(shortId: number): Promise<void> {
    const response = await this.request(`/conversation/${shortId}`, { method: 'DELETE' });
    if (!response.ok) {
      throw new ApiError(`Failed to delete conversation (short_id=${shortId})`, response.status);
    }
  }

  // POST /conversation/{short_id}/confirmation/{tool_call_id}?approved=<bool>
  async confirmToolCall(shortId: number, toolCallId: string, approved: boolean): Promise<void> {
    const path = `/conversation/${shortId}/confirmation/${encodeURIComponent(toolCallId)}?approved=${approved}`;
    const response = await this.request(path, { method: 'POST' });
    if (!response.ok) {
      throw new ApiError(`Failed to confirm tool call ${toolCallId}`, response.status);
    }
  }

  // GET /conversation/{short_id}/usage
  async getUsage(shortId: number): Promise<Usage> {
    return this.requestJson(`/conversation/${shortId}/usage`, UsageSchema);
  }
}
