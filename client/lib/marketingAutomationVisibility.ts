export function countAutomationEntries<TMarketing, TChatbot>(marketing: TMarketing[], chatbot: TChatbot[]): number {
  return marketing.length + chatbot.length;
}

export function hasAutomationEntries<T>(entries: T[]): boolean {
  return entries.length > 0;
}
