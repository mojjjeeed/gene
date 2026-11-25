"use client";

import type { RunEvent } from "@a9/contracts";
import { useEffect, useReducer } from "react";
import { initialRunState, runReducer, type RunState } from "./reducer";

/**
 * Follow one run's event stream. The browser's EventSource reconnects by itself and sends the last
 * `id:` it saw as Last-Event-ID, so the server replays the backlog instead of the UI showing a spinner.
 * The reducer drops any overlap by seq.
 */
export function useRunEvents(runId: string | null): RunState {
  const [state, dispatch] = useReducer(runReducer, { ...initialRunState, runId });

  useEffect(() => {
    dispatch({ type: "reset", runId });
    if (!runId) return;

    const source = new EventSource(`/api/runs/${encodeURIComponent(runId)}/events`);
    source.onopen = () => dispatch({ type: "connection", state: "open" });
    source.onmessage = (message) => {
      const event = JSON.parse(message.data) as RunEvent;
      dispatch({ type: "event", event });
      if (event.type === "run_finished" || event.type === "run_failed") {
        // The server closes after a terminal event; stop EventSource from reconnecting forever.
        source.close();
        dispatch({ type: "connection", state: "closed" });
      }
    };
    source.onerror = () => {
      // readyState CONNECTING means the browser is retrying; CLOSED means it gave up.
      dispatch({ type: "connection", state: source.readyState === EventSource.CLOSED ? "closed" : "reconnecting" });
    };
    return () => source.close();
  }, [runId]);

  return state;
}
