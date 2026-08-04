// /stop — asks the backend to stop the running agent. Stop is non-preemptive:
// the agent halts after the current event, and a StopEvent arrives on the stream.
import type { CommandDefinition } from './registry.js';

export const stopCommand: CommandDefinition = {
  spec: {
    name: 'stop',
    description: 'stop the running agent',
    params: [],
  },
  run: async (_args, ctx) => {
    await ctx.client.stopAgent(ctx.shortId);
  },
};
