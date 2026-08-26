type MetrikaParameter = string | number | boolean;
type MetrikaParameters = Record<string, MetrikaParameter>;

declare global {
  interface Window {
    ym?: (counterId: number, method: "reachGoal", goal: string, parameters?: MetrikaParameters) => void;
  }
}

export const METRIKA_GOALS = {
  demoOpen: "tuneai-demo-open",
  demoStart: "tuneai-demo-start",
  consultation: "tuneai-consultation",
  login: "ym-login",
  register: "ym-register"
} as const;

function getCounterId() {
  const rawCounterId = process.env.NEXT_PUBLIC_YANDEX_METRIKA_ID?.trim() || "";
  if (!/^\d+$/.test(rawCounterId)) return null;

  const counterId = Number(rawCounterId);
  return Number.isSafeInteger(counterId) ? counterId : null;
}

export function reachMetrikaGoal(goal: string, parameters?: MetrikaParameters) {
  if (typeof window === "undefined" || typeof window.ym !== "function") return;

  const counterId = getCounterId();
  if (counterId === null) return;

  window.ym(counterId, "reachGoal", goal, parameters);
}
