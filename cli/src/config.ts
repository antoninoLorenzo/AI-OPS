// Configuration: a single zod schema is both the runtime validator and the
// static type. Each source (flags, file) returns a partial that the resolver
// merges with flags taking precedence, then validates against the schema.
import { readFileSync } from 'node:fs';
import { homedir } from 'node:os';
import { join } from 'node:path';
import { parseArgs } from 'node:util';
import { z } from 'zod';

export const AppConfigSchema = z.object({
  baseUrl: z.string().url(),
  apiKey: z.string().optional(),
  mode: z.enum(['supervised', 'unsupervised']).default('supervised'),
  resume: z.coerce.number().int().optional(),
});

export type AppConfig = z.infer<typeof AppConfigSchema>;

// A partial, pre-validation view of the config. Values are kept as the raw
// strings each source produces; the schema coerces/validates on resolve.
export type ConfigSource = {
  baseUrl?: string;
  apiKey?: string;
  mode?: string;
  resume?: string | number;
};

export const DEFAULT_CONFIG_PATH = join(homedir(), '.config', 'ai_ops', 'cli.json');

// Raised for any startup-fatal configuration problem (malformed file, schema
// validation failure). cli.tsx catches this and exits with the message.
export class ConfigError extends Error {
  constructor(message: string) {
    super(message);
    this.name = 'ConfigError';
  }
}

// Isolated so the parsing library can be swapped without touching the schema,
// the merge logic, or any consumer of AppConfig.
export function parseFlags(argv: string[]): ConfigSource {
  // strict: an unknown or malformed flag (a typo like --reload) is fatal rather
  // than silently dropped, which would otherwise fall through to default
  // behavior (e.g. creating a new conversation instead of resuming). parseArgs
  // throws a plain Error; rethrow as ConfigError so cli.tsx exits cleanly.
  let values;
  try {
    ({ values } = parseArgs({
      args: argv,
      options: {
        'base-url': { type: 'string' },
        'api-key': { type: 'string' },
        mode: { type: 'string' },
        resume: { type: 'string' },
      },
      strict: true,
      allowPositionals: true,
    }));
  } catch (err) {
    throw new ConfigError(`Invalid command-line flags: ${(err as Error).message}`);
  }

  const source: ConfigSource = {};
  if (typeof values['base-url'] === 'string') source.baseUrl = values['base-url'];
  if (typeof values['api-key'] === 'string') source.apiKey = values['api-key'];
  if (typeof values.mode === 'string') source.mode = values.mode;
  if (typeof values.resume === 'string') source.resume = values.resume;
  return source;
}

// Reads ~/.config/ai_ops/cli.json. A missing file is not an error (the file is
// optional); a present-but-malformed file is fatal.
export function readConfigFile(path: string = DEFAULT_CONFIG_PATH): ConfigSource {
  let raw: string;
  try {
    raw = readFileSync(path, 'utf8');
  } catch (err) {
    if ((err as NodeJS.ErrnoException).code === 'ENOENT') return {};
    throw new ConfigError(`Could not read configuration file at ${path}: ${(err as Error).message}`);
  }

  let parsed: unknown;
  try {
    parsed = JSON.parse(raw);
  } catch {
    throw new ConfigError(`Malformed configuration file at ${path}: invalid JSON`);
  }

  if (typeof parsed !== 'object' || parsed === null || Array.isArray(parsed)) {
    throw new ConfigError(`Malformed configuration file at ${path}: expected a JSON object`);
  }

  const obj = parsed as Record<string, unknown>;
  const source: ConfigSource = {};
  if (typeof obj.base_url === 'string') source.baseUrl = obj.base_url;
  if (typeof obj.api_key === 'string') source.apiKey = obj.api_key;
  if (typeof obj.mode === 'string') source.mode = obj.mode;
  if (typeof obj.resume === 'string' || typeof obj.resume === 'number') {
    source.resume = obj.resume;
  }
  return source;
}

// Merges sources with flags taking precedence, then validates. Only defined
// keys from each source participate in the merge.
export function resolveConfig(file: ConfigSource, flags: ConfigSource): AppConfig {
  const merged: ConfigSource = { ...file, ...flags };

  const result = AppConfigSchema.safeParse(merged);
  if (!result.success) {
    const issues = result.error.issues
      .map((issue) => `${issue.path.join('.') || '(root)'}: ${issue.message}`)
      .join('; ');
    throw new ConfigError(`Invalid configuration: ${issues}`);
  }
  return result.data;
}

// Convenience end-to-end resolution from process argv.
export function loadConfig(
  argv: string[] = process.argv.slice(2),
  filePath: string = DEFAULT_CONFIG_PATH,
): AppConfig {
  return resolveConfig(readConfigFile(filePath), parseFlags(argv));
}
