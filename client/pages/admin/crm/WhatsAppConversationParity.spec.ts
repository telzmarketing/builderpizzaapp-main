import { readFileSync } from "node:fs";
import { describe, expect, it } from "vitest";

const crmSource = readFileSync(new URL("./CrmAgenteWhatsApp.tsx", import.meta.url), "utf8");
const operationsSource = readFileSync(
  new URL("../../../components/admin/OperationsContactPanel.tsx", import.meta.url),
  "utf8",
);

function initialConversationLimit(source: string): number | null {
  const match = source.match(
    /agenteWhatsAppApi\.listConversations\(\{[\s\S]*?limit:\s*(\d+)[\s\S]*?\}\)/,
  );
  return match ? Number(match[1]) : null;
}

describe("WhatsApp conversation parity between CRM and Operations", () => {
  it("uses the same conversation API and initial pagination in both screens", () => {
    expect(crmSource).toContain("agenteWhatsAppApi.listConversations({");
    expect(operationsSource).toContain("agenteWhatsAppApi.listConversations({");

    const crmLimit = initialConversationLimit(crmSource);
    const operationsLimit = initialConversationLimit(operationsSource);

    expect(crmLimit).not.toBeNull();
    expect(operationsLimit).not.toBeNull();
    expect(crmLimit).toBe(operationsLimit);
  });

  it("keeps the complete API response as the WhatsApp list in both screens", () => {
    expect(crmSource).toMatch(/const rows = await conversationRequest;[\s\S]*?setSessions\(rows\)/);
    expect(operationsSource).toMatch(
      /const nextWhatsApp = wa \?\? \[\];[\s\S]*?setWhatsapp\(nextWhatsApp\)/,
    );
  });

  it("renders every visible WhatsApp conversation from the loaded list", () => {
    expect(crmSource).toContain("filteredSessions.map((session) =>");
    expect(crmSource).toContain("session.customer_name || session.phone");
    expect(crmSource).toContain("session.unread_count");

    expect(operationsSource).toContain(
      'const items = channel === "chatbot" ? chatbot : whatsapp;',
    );
    expect(operationsSource).toContain("items.map((item) =>");
    expect(operationsSource).toContain("item.customer_name || item.phone");
    expect(operationsSource).toContain('"unread_count" in item ? item.unread_count');
  });

  it("starts the CRM conversation view without status or text filtering", () => {
    expect(crmSource).toContain('useState<StatusFilter>("all")');
    expect(crmSource).toContain('const [search, setSearch] = useState("")');
    expect(crmSource).toMatch(/if \(filter !== "all" && session\.status !== filter\) return false;/);
    expect(crmSource).toMatch(/if \(!term\) return true;/);
  });
});
