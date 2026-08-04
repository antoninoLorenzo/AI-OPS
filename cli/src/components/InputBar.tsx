// Multiline input that takes both prompts and commands. Enter submits;
// Shift+Enter inserts a newline. While the buffer is a command (`/…` with no
// space yet), a presentational completion list is shown: Tab completes, Up/Down
// highlight, Enter runs the highlighted command. The key handling is a pure
// function (`handleInputKey`) so it can be unit-tested without a terminal.
import React, { useMemo, useState } from 'react';
import { Box, Text, useInput } from 'ink';
import type { CommandRegistry, CommandDefinition } from '../commands/registry.js';
import { Completion } from './Completion.js';

export interface InputState {
  value: string;
  cursor: number;
  selectedIndex: number;
}

export function emptyInput(): InputState {
  return { value: '', cursor: 0, selectedIndex: 0 };
}

// The subset of Ink's Key we react to.
export interface KeyLike {
  return?: boolean;
  shift?: boolean;
  tab?: boolean;
  upArrow?: boolean;
  downArrow?: boolean;
  leftArrow?: boolean;
  rightArrow?: boolean;
  backspace?: boolean;
  delete?: boolean;
  ctrl?: boolean;
  meta?: boolean;
}

export interface KeyResult {
  state: InputState;
  submit?: string; // set when the buffer should be submitted
}

// The command names (with leading slash) currently offered as completions for a
// buffer. Empty unless the buffer is `/<name>` with no whitespace yet.
export function completionsFor(value: string, registry: CommandRegistry): CommandDefinition[] {
  if (!value.startsWith('/')) return [];
  const rest = value.slice(1);
  if (/\s/.test(rest)) return []; // past the command name, into arguments
  return registry.match(rest);
}

function insert(state: InputState, text: string): InputState {
  const value = state.value.slice(0, state.cursor) + text + state.value.slice(state.cursor);
  return { value, cursor: state.cursor + text.length, selectedIndex: 0 };
}

// Pure keypress reducer for the input buffer. `completions` is the currently
// offered command list (already derived from `state.value`).
export function handleInputKey(
  state: InputState,
  input: string,
  key: KeyLike,
  completions: CommandDefinition[],
): KeyResult {
  const hasCompletions = completions.length > 0;

  if (key.return) {
    if (key.shift) return { state: insert(state, '\n') };
    // Enter runs the highlighted command when completing, else submits the buffer.
    const submit = hasCompletions
      ? '/' + completions[Math.min(state.selectedIndex, completions.length - 1)].spec.name
      : state.value;
    return { state: emptyInput(), submit };
  }

  if (key.tab) {
    if (hasCompletions) {
      const chosen = completions[Math.min(state.selectedIndex, completions.length - 1)];
      const value = '/' + chosen.spec.name + ' ';
      return { state: { value, cursor: value.length, selectedIndex: 0 } };
    }
    return { state };
  }

  if (key.upArrow) {
    if (!hasCompletions) return { state };
    return { state: { ...state, selectedIndex: Math.max(0, state.selectedIndex - 1) } };
  }
  if (key.downArrow) {
    if (!hasCompletions) return { state };
    return {
      state: { ...state, selectedIndex: Math.min(completions.length - 1, state.selectedIndex + 1) },
    };
  }

  if (key.leftArrow) return { state: { ...state, cursor: Math.max(0, state.cursor - 1) } };
  if (key.rightArrow) {
    return { state: { ...state, cursor: Math.min(state.value.length, state.cursor + 1) } };
  }

  if (key.backspace || key.delete) {
    if (state.cursor === 0) return { state };
    const value = state.value.slice(0, state.cursor - 1) + state.value.slice(state.cursor);
    return { state: { value, cursor: state.cursor - 1, selectedIndex: 0 } };
  }

  // Printable input (letters, digits, space, symbols). Control chords carry
  // their own flags and are ignored here.
  if (input && !key.ctrl && !key.meta) {
    return { state: insert(state, input) };
  }

  return { state };
}

// Renders the buffer with a block cursor at the caret. String slicing handles
// multiline naturally (a '\n' in the slice becomes a line break).
function BufferView({ state, active }: { state: InputState; active: boolean }) {
  const before = state.value.slice(0, state.cursor);
  const after = state.value.slice(state.cursor);
  const cursorChar = after.length > 0 ? after[0] : ' ';
  return (
    <Text>
      <Text color="cyan">{'> '}</Text>
      {before}
      {active ? <Text inverse>{cursorChar}</Text> : cursorChar === ' ' ? '' : cursorChar}
      {active ? after.slice(1) : after.slice(cursorChar === ' ' ? 0 : 1)}
    </Text>
  );
}

export function InputBar({
  active,
  registry,
  onSubmit,
  blocked = false,
}: {
  active: boolean;
  registry: CommandRegistry;
  onSubmit: (value: string) => void;
  blocked?: boolean;
}) {
  const [state, setState] = useState<InputState>(emptyInput);
  const completions = useMemo(() => completionsFor(state.value, registry), [state.value, registry]);

  useInput(
    (input, key) => {
      const result = handleInputKey(state, input, key, completions);
      setState(result.state);
      if (result.submit !== undefined) {
        const trimmed = result.submit.trim();
        if (trimmed.length > 0) onSubmit(trimmed);
      }
    },
    { isActive: active },
  );

  return (
    <Box flexDirection="column">
      <BufferView state={state} active={active} />
      {completions.length > 0 ? (
        <Completion matches={completions} selectedIndex={state.selectedIndex} />
      ) : null}
      {blocked ? <Text dimColor>a message is already queued — waiting for the agent to drain it</Text> : null}
    </Box>
  );
}
