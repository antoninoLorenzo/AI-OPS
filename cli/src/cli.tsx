#!/usr/bin/env -S npx tsx
// Executable entry point: resolve configuration, run startup against the API,
// then render the app. Any startup-fatal condition (malformed config,
// unreachable API, missing resumed conversation) prints a message and exits 1.
import React from 'react';
import { render } from 'ink';
import { loadConfig, ConfigError } from './config.js';
import { runStartup, StartupError } from './startup.js';
import { App } from './components/App.js';

async function main(): Promise<void> {
  // Configuration: CLI flags over the optional ~/.config/ai_ops/cli.json file.
  let config;
  try {
    config = loadConfig();
  } catch (err) {
    if (err instanceof ConfigError) {
      console.error(err.message);
      process.exit(1);
    }
    throw err;
  }

  // Startup: reachability, conversation, model metadata.
  let startup;
  try {
    startup = await runStartup(config);
  } catch (err) {
    if (err instanceof StartupError) {
      console.error(err.message);
      process.exit(1);
    }
    throw err;
  }

  const { waitUntilExit } = render(
    <App
      client={startup.client}
      model={startup.model}
      shortId={startup.shortId}
      mode={startup.mode}
      initialEvents={startup.initialEvents}
      initialTotalTokens={startup.initialTotalTokens}
    />,
  );
  await waitUntilExit();
}

main().catch((err) => {
  console.error(err);
  process.exit(1);
});
