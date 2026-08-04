import { CommandRegistry } from './registry.js';
import { exitCommand } from './exit.js';
import { stopCommand } from './stop.js';

// Builds the registry with the commands available in the current version.
export function buildRegistry(): CommandRegistry {
  const registry = new CommandRegistry();
  registry.register(exitCommand);
  registry.register(stopCommand);
  return registry;
}

export { CommandRegistry } from './registry.js';
export type { CommandDefinition, CommandSpec, ParamSpec, AppContext } from './registry.js';
