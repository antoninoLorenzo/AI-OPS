#!/usr/bin/env node
/*
npm run bundle:sea
$(nvm which 26.7.0) --build-sea sea-config.json
strip dist/ai-ops-cli
*/
import { build } from 'esbuild';

await build({
  entryPoints: ['src/cli.tsx'],
  bundle: true,
  minify: true,
  platform: 'node',
  format: 'esm',
  outfile: 'dist/cli.sea.js',
  alias: {
    'react-devtools-core': './shims/react-devtools-core.js',
  },
  banner: {
    js: "import { createRequire } from 'node:module'; const require = createRequire(import.meta.url);",
  },
});

console.log('SEA bundle written to dist/cli.sea.js');