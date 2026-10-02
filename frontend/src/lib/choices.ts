/** Which alternative the student picked for each "Select One" row, remembered in this browser per roadmap. */
export function readChoices(key: string): Record<string, string> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key) ?? "{}");
    return parsed && typeof parsed === "object" ? (parsed as Record<string, string>) : {};
  } catch {
    return {};
  }
}

export function writeChoices(key: string, choices: Record<string, string>) {
  try {
    localStorage.setItem(key, JSON.stringify(choices));
  } catch {
    /* storage blocked: the choice just won't survive a reload */
  }
}

/** A remembered set of ids (e.g. the GE rows the student marked completed), per roadmap. */
export function readSet(key: string): Set<string> {
  try {
    const parsed: unknown = JSON.parse(localStorage.getItem(key) ?? "[]");
    return new Set(Array.isArray(parsed) ? parsed.filter((x): x is string => typeof x === "string") : []);
  } catch {
    return new Set();
  }
}

export function writeSet(key: string, ids: ReadonlySet<string>) {
  try {
    localStorage.setItem(key, JSON.stringify([...ids]));
  } catch {
    /* storage blocked */
  }
}
