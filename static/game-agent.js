(function(root) {
  "use strict";
  const DEFAULTS = { maxSteps: 100, maxDurationMs: 30000, maxRepeatedStates: 3, allowedActions: [] };

  function createAgent({ adapter, decide, limits = {}, onEvent = () => {} } = {}) {
    if (!adapter || typeof adapter.observe !== "function" ||
        typeof adapter.execute !== "function" || typeof decide !== "function") {
      throw new TypeError("Agent requires adapter.observe, adapter.execute and decide.");
    }
    const config = { ...DEFAULTS, ...limits };
    if (!Number.isInteger(config.maxSteps) || config.maxSteps < 1 || config.maxSteps > 10000) {
      throw new RangeError("maxSteps must be between 1 and 10000.");
    }
    if (!Number.isFinite(config.maxDurationMs) || config.maxDurationMs < 1 || config.maxDurationMs > 3600000) {
      throw new RangeError("maxDurationMs must be between 1 and 3600000.");
    }
    if (!Number.isInteger(config.maxRepeatedStates) || config.maxRepeatedStates < 2 || config.maxRepeatedStates > 10) {
      throw new RangeError("maxRepeatedStates must be between 2 and 10.");
    }
    const allowed = new Set(config.allowedActions);
    let stopped = false;

    return {
      stop() { stopped = true; },
      async run({ signal } = {}) {
        stopped = false;
        const started = Date.now();
        const history = [];
        const stateVisits = new Map();
        const emit = (type, details = {}) => {
          try { onEvent({ type, ...details, steps: history.length }); } catch (_) {}
        };
        const finish = (status, reason) => ({
          status, reason, steps: history.length, elapsedMs: Date.now() - started, history
        });
        emit("started");

        for (let step = 0; step < config.maxSteps; step++) {
          if (stopped || signal?.aborted) return finish("stopped", "cancelled");
          if (Date.now() - started >= config.maxDurationMs) return finish("limited", "time_limit");

          const observation = await adapter.observe();
          if (adapter.isTerminal?.(observation)) {
            emit("finished", { observation });
            return finish("completed", "terminal_state");
          }

          // A site adapter may expose a compact semantic key for the actual board state.
          // Repeated states are a loop warning, not proof that the game is unwinnable.
          if (typeof adapter.getStateKey === "function") {
            const key = adapter.getStateKey(observation);
            if (typeof key === "string" && key.length > 0 && key.length <= 2000) {
              const visits = (stateVisits.get(key) || 0) + 1;
              stateVisits.set(key, visits);
              if (visits >= config.maxRepeatedStates) {
                emit("stalled", { reason: "repeated_state", stateVisits: visits });
                return finish("stalled", "repeated_state");
              }
              if (stateVisits.size > 100) stateVisits.delete(stateVisits.keys().next().value);
            }
          }

          const action = await decide(observation, history.slice());
          if (!action) return finish("stalled", "no_action");
          if (typeof action.type !== "string" || !allowed.has(action.type)) {
            return finish("blocked", "action_not_allowed");
          }
          if (stopped || signal?.aborted) return finish("stopped", "cancelled");

          const result = await adapter.execute(action);
          const next = await adapter.observe();
          const verified = adapter.verify
            ? await adapter.verify({ before: observation, action, result, after: next })
            : true;
          const record = { step: step + 1, action, result, verified };
          history.push(record);
          emit("step", record);
          if (!verified) return finish("error", "action_not_verified");
          if (adapter.isTerminal?.(next)) {
            emit("finished", { observation: next });
            return finish("completed", "terminal_state");
          }
        }
        return finish("limited", "step_limit");
      }
    };
  }

  root.AutoEarnGameAgent = { createAgent };
})(globalThis);
