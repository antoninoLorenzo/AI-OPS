// NDJSON consumption over a streaming fetch body, using Node built-ins only.
// `splitNdjson` is a pure transform (async-iterable of byte/string chunks ->
// complete lines) so it can be tested with chunks split at arbitrary
// boundaries; `streamResponseLines` adapts a fetch Response onto it.

// Splits a stream of chunks into complete, non-empty lines. A trailing line
// without a newline (as NDJSON streams commonly end) is still yielded.
export async function* splitNdjson(
  chunks: AsyncIterable<Uint8Array | string>,
): AsyncGenerator<string> {
  const decoder = new TextDecoder();
  let buffer = '';

  for await (const chunk of chunks) {
    buffer += typeof chunk === 'string' ? chunk : decoder.decode(chunk, { stream: true });

    let newline: number;
    while ((newline = buffer.indexOf('\n')) !== -1) {
      const line = buffer.slice(0, newline).trim();
      buffer = buffer.slice(newline + 1);
      if (line.length > 0) yield line;
    }
  }

  buffer += decoder.decode();
  const last = buffer.trim();
  if (last.length > 0) yield last;
}

// Reads a web ReadableStream (Node's fetch body) chunk by chunk. Kept separate
// from `splitNdjson` so the line-splitting logic stays free of I/O.
async function* readBodyChunks(body: ReadableStream<Uint8Array>): AsyncGenerator<Uint8Array> {
  const reader = body.getReader();
  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) return;
      if (value) yield value;
    }
  } finally {
    reader.releaseLock();
  }
}

// Yields complete NDJSON lines from a fetch Response body.
export function streamResponseLines(response: Response): AsyncGenerator<string> {
  const body = response.body;
  if (!body) {
    throw new Error('Response has no body to stream');
  }
  return splitNdjson(readBodyChunks(body));
}
