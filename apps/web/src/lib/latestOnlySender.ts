// Sends values one request at a time, always finishing with the most recent value.
//
// Onboarding saves a draft after every answer. If two saves are in flight at once, the server
// can receive them out of order and keep the older step, so FR6 resume would land one question
// early. Here only one request runs at a time; values queued meanwhile collapse to the latest,
// which is sent as soon as the current request finishes.

export interface LatestOnlySender<T> {
  /** Queue a value; it replaces any value still waiting to be sent. */
  send(value: T): void;
  /** Drop the waiting value (if any) and resolve once the in-flight request has finished. */
  flush(): Promise<void>;
}

export const createLatestOnlySender = <T>(
  request: (value: T) => Promise<unknown>,
  onResult?: (ok: boolean) => void,
): LatestOnlySender<T> => {
  let waiting: { value: T } | null = null;
  let running: Promise<void> | null = null;

  const drain = async () => {
    while (waiting) {
      const { value } = waiting;
      waiting = null;
      try {
        await request(value);
        onResult?.(true);
      } catch {
        onResult?.(false);
      }
    }
    running = null;
  };

  return {
    send(value) {
      waiting = { value };
      running ??= drain();
    },
    async flush() {
      waiting = null;
      await running;
    },
  };
};
