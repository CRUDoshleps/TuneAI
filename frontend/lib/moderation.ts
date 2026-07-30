const profanityPatterns = [
  /\b[а-яё]*бля(?:д|т)[а-яё]*\b/giu,
  /\b[а-яё]*п[иеё]зд[а-яё]*\b/giu,
  /\b[а-яё]*х[уy][йяеёиюи][а-яё]*\b/giu,
  /\b(?:за|на|по|вы|про|при|разъ|раз|съ|от|до)?(?:е|ё)б(?:а|и|у|л|н|о|ё|ы|с|т|уч)[а-яё]*\b/giu
];

export function censorText(value: string): string {
  return profanityPatterns.reduce(
    (current, pattern) => current.replace(pattern, (match) => "*".repeat([...match].length)),
    value
  );
}

export function censorContent<T>(value: T): T {
  if (typeof value === "string") {
    return censorText(value) as T;
  }
  if (Array.isArray(value)) {
    return value.map((item) => censorContent(item)) as T;
  }
  if (value && typeof value === "object") {
    return Object.fromEntries(
      Object.entries(value).map(([key, item]) => [key, censorContent(item)])
    ) as T;
  }
  return value;
}
