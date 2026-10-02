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
