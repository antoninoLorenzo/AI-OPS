// Command registry: the single source of truth for both execution and
// completion. `get` resolves a submitted command; `match` feeds the completion
// list. Each command parses its own arguments inside `run`, so adding a command
// means registering one definition and changing nothing else.
import type { ApiClient } from '../api/client.js';
import type { Action } from '../state/sessionReducer.js';

export interface ParamSpec {
  name: string;
  description: string;
  required?: boolean;
}

export interface CommandSpec {
  name: string; // canonical name without the leading slash, e.g. "exit"
  description: string;
  params: ParamSpec[];
}

// Everything a command needs to act on the session and the backend.
export interface AppContext {
  client: ApiClient;
  shortId: number;
  dispatch: (action: Action) => void;
  exit: () => void;
}

export interface CommandDefinition {
  spec: CommandSpec;
  run: (args: string[], ctx: AppContext) => Promise<void> | void;
}

export class CommandRegistry {
  private commands = new Map<string, CommandDefinition>();

  register(def: CommandDefinition): void {
    this.commands.set(def.spec.name, def);
  }

  get(name: string): CommandDefinition | undefined {
    return this.commands.get(name);
  }

  // Prefix match over command names, sorted alphabetically for stable ordering.
  match(prefix: string): CommandDefinition[] {
    return [...this.commands.values()]
      .filter((def) => def.spec.name.startsWith(prefix))
      .sort((a, b) => a.spec.name.localeCompare(b.spec.name));
  }

  all(): CommandDefinition[] {
    return [...this.commands.values()].sort((a, b) => a.spec.name.localeCompare(b.spec.name));
  }
}
