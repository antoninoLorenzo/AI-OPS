// Test helpers for interactive (ink) tests. Node runs test files concurrently,
// so fixed sleeps get starved under load; poll for the expected condition
// instead of guessing a delay.

// Strips ANSI escape codes (colors, styles, cursor moves) from a rendered
// frame. Ink emits these whenever the environment reports color support (an
// interactive TTY or CI), so plain-text assertions must strip them first to
// stay stable across environments.
// eslint-disable-next-line no-control-regex
export function stripAnsi(s: string): string {
  return s.replace(/\x1B\[[0-9;]*m/g, '');
}

export async function waitFor(
  predicate: () => boolean,
  { timeout = 2000, step = 10 }: { timeout?: number; step?: number } = {},
): Promise<void> {
  const start = Date.now();
  for (;;) {
    if (predicate()) return;
    if (Date.now() - start >= timeout) {
      throw new Error('waitFor: condition not met within timeout');
    }
    await new Promise((r) => setTimeout(r, step));
  }
}

// Waits until the rendered frame matches a pattern.
export async function waitForFrame(getFrame: () => string | undefined, pattern: RegExp): Promise<void> {
  await waitFor(() => pattern.test(stripAnsi(getFrame() ?? '')));
}

// Writes a key repeatedly until `predicate` holds. Ink registers a component's
// useInput handler in an effect that runs just after the render commit, so a key
// written the instant a mid-stream form appears can land before the handler is
// attached (a synthetic-input timing artifact — a real user is far slower). The
// predicate stops the loop as soon as the key takes effect, so exactly one press
// is delivered in the common case.
export async function pressUntil(
  stdin: { write: (s: string) => void },
  key: string,
  predicate: () => boolean,
  { attempts = 50, step = 40 }: { attempts?: number; step?: number } = {},
): Promise<void> {
  for (let i = 0; i < attempts; i++) {
    if (predicate()) return;
    stdin.write(key);
    await new Promise((r) => setTimeout(r, step));
  }
  if (!predicate()) throw new Error('pressUntil: predicate not met');
}
