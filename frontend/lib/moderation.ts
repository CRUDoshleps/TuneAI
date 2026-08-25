const profanityPatterns = [
  /(^|[^а-яё])([а-яё]*бля(?:д|т)[а-яё]*)(?=$|[^а-яё])/giu,
  /(^|[^а-яё])([а-яё]*п[иеё]зд[а-яё]*)(?=$|[^а-яё])/giu,
  /(^|[^а-яё])([а-яё]*х[уy][йяеёиюи][а-яё]*)(?=$|[^а-яё])/giu,
  /(^|[^а-яё])((?:за|на|по|вы|про|при|разъ|раз|съ|от|до)?(?:е|ё)б(?:а|и|у|л|н|о|ё|ы|с|т|уч)[а-яё]*)(?=$|[^а-яё])/giu,
  /(^|[^а-яё])([а-яё]*(?:сос(?:а(?:л[аи]?|ть|т[ьи]?|ешь|и|н[а-яё]*)|у|и)|отсос[а-яё]*)[а-яё]*)(?=$|[^а-яё])/giu
];

export function censorText(value: string): string {
  return profanityPatterns.reduce(
    (current, pattern) =>
      current.replace(pattern, (_match, prefix: string, word: string) => `${prefix}${"*".repeat([...word].length)}`),
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
