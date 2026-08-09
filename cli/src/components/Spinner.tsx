// A one-character running indicator. It exists so that a long tool call is
// visibly distinguishable from a hung client: without it there is no way to
// tell, from the screen, whether the agent is still working.
//
// It is cheap only because the settled transcript lives in <Static> (see
// Transcript.tsx). Each tick repaints Ink's live frame, so before that split a
// spinner would have repainted the whole session several times a second.
import React, { useEffect, useState } from 'react';
import { Text } from 'ink';

const FRAMES = ['/', '-', '\\', '-'];
const INTERVAL_MS = 120;

export function Spinner({ active }: { active: boolean }) {
  const [frame, setFrame] = useState(0);

  useEffect(() => {
    if (!active) {
      setFrame(0);
      return;
    }
    const timer = setInterval(() => {
      setFrame((f) => (f + 1) % FRAMES.length);
    }, INTERVAL_MS);
    // A pending timer must never be what keeps the process (or a test run)
    // alive; the interval only matters while something else holds it open.
    timer.unref();
    return () => {
      clearInterval(timer);
    };
  }, [active]);

  if (!active) return null;
  return <Text color="cyan">{FRAMES[frame]}</Text>;
}
