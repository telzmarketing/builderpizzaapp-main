export interface ChatbotViewportSnapshot {
  height: number;
  offsetTop: number;
}

/**
 * Returns the visible browser viewport, including the reduced height caused by
 * the virtual keyboard on mobile browsers.
 */
export function readChatbotViewport(): ChatbotViewportSnapshot {
  if (typeof window === "undefined") return { height: 0, offsetTop: 0 };

  const viewport = window.visualViewport;
  return {
    height: Math.max(0, viewport?.height ?? window.innerHeight),
    offsetTop: Math.max(0, viewport?.offsetTop ?? 0),
  };
}
