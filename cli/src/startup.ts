// Startup orchestration, kept separate from the cli.tsx process glue so it can
// be tested against a mock server. Order follows the spec: check the API is
// reachable, create or resume the conversation, then fetch model metadata.
import { ApiClient, ApiError, type FetchFn } from './api/client.js';
import type { AnyEvent } from './api/events.js';
import type { AppConfig } from './config.js';
import type { Mode, ModelInfo } from './state/sessionReducer.js';

export interface StartupResult {
  client: ApiClient;
  model: ModelInfo;
  shortId: number;
  mode: Mode;
  initialEvents?: AnyEvent[];
  initialTotalTokens: number;
}

// A startup-fatal condition with a user-facing message. cli.tsx prints the
// message and exits.
export class StartupError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'StartupError';
  }
}

export async function runStartup(
  config: AppConfig,
  opts: { fetch?: FetchFn } = {},
): Promise<StartupResult> {
  const client = new ApiClient({
    baseUrl: config.baseUrl,
    apiKey: config.apiKey,
    fetch: opts.fetch,
  });

  // 1. The API must be reachable, otherwise there is nothing to do.
  try {
    await client.health();
  } catch (err) {
    throw new StartupError(`API is not reachable at ${config.baseUrl}: ${(err as Error).message}`);
  }

  let shortId: number;
  let initialEvents: AnyEvent[] | undefined;
  let initialTotalTokens = 0;

  // 2. Resume an existing conversation, or create a new one.
  if (config.resume !== undefined) {
    try {
      initialEvents = await client.loadConversation(config.resume);
    } catch (err) {
      if (err instanceof ApiError && err.status === 404) {
        throw new StartupError(`No conversation with short_id=${config.resume}`);
      }
      throw new StartupError(`Failed to resume conversation #${config.resume}: ${(err as Error).message}`);
    }
    shortId = config.resume;
    // A resumed conversation carries prior token consumption.
    try {
      const usage = await client.getUsage(shortId);
      initialTotalTokens = usage.total_tokens;
    } catch {
      // Advisory only; fall back to 0 rather than failing startup.
    }
  } else {
    try {
      const conversation = await client.createConversation();
      shortId = conversation.short_id;
    } catch (err) {
      throw new StartupError(`Failed to create a conversation: ${(err as Error).message}`);
    }
  }

  // 3. Fetch model metadata for the header.
  let model: ModelInfo;
  try {
    const metadata = await client.getModel();
    model = {
      provider: metadata.provider,
      modelId: metadata.model_id,
      maxContextLength: metadata.max_context_length ?? null,
    };
  } catch (err) {
    throw new StartupError(`Failed to fetch model metadata: ${(err as Error).message}`);
  }

  return {
    client,
    model,
    shortId,
    mode: config.mode,
    initialEvents,
    initialTotalTokens,
  };
}
