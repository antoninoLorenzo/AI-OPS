// /exit — deletes the conversation on the backend, then exits the CLI.
import type { CommandDefinition } from './registry.js';

export const exitCommand: CommandDefinition = {
  spec: {
    name: 'exit',
    description: 'close the session and quit',
    params: [],
  },
  run: async (_args, ctx) => {
    // Best-effort cleanup; quit regardless so the user is never trapped.
    try {
      await ctx.client.deleteConversation(ctx.shortId);
    } catch {
      /* ignore cleanup failure */
    }
    ctx.exit();
  },
};
