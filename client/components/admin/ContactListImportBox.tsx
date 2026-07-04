import { useRef, useState } from "react";
import { FileText, Upload } from "lucide-react";

export interface ImportedMarketingContact {
  name: string;
  whatsapp: string;
  email: string;
}

type Channel = "whatsapp" | "email";

interface ContactListImportBoxProps {
  channel: Channel;
  onContacts: (contacts: ImportedMarketingContact[]) => void;
}

const TEMPLATE = "nome,whatsapp,email\nMaria Silva,5511999999999,maria@email.com\nJoao Souza,5511888888888,joao@email.com";

function splitCsvLine(line: string): string[] {
  const values: string[] = [];
  let current = "";
  let quoted = false;
  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"') {
      quoted = !quoted;
      continue;
    }
    if ((char === "," || char === ";") && !quoted) {
      values.push(current.trim());
      current = "";
      continue;
    }
    current += char;
  }
  values.push(current.trim());
  return values;
}

function parseContacts(text: string): ImportedMarketingContact[] {
  const lines = text.split(/\r?\n/).map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return [];

  const first = splitCsvLine(lines[0]).map((item) => item.toLowerCase());
  const hasHeader = first.some((item) => ["nome", "name", "whatsapp", "telefone", "phone", "email"].includes(item));
  const header = hasHeader ? first : ["nome", "whatsapp", "email"];
  const rows = hasHeader ? lines.slice(1) : lines;
  const nameIndex = Math.max(header.findIndex((item) => ["nome", "name"].includes(item)), 0);
  const whatsappIndex = header.findIndex((item) => ["whatsapp", "telefone", "phone", "celular"].includes(item));
  const emailIndex = header.findIndex((item) => item === "email" || item === "e-mail");

  return rows.map((line) => {
    const values = splitCsvLine(line);
    return {
      name: values[nameIndex]?.trim() ?? "",
      whatsapp: whatsappIndex >= 0 ? values[whatsappIndex]?.trim() ?? "" : values[1]?.trim() ?? "",
      email: emailIndex >= 0 ? values[emailIndex]?.trim() ?? "" : values[2]?.trim() ?? "",
    };
  }).filter((contact) => contact.name && (contact.whatsapp || contact.email));
}

export default function ContactListImportBox({ channel, onContacts }: ContactListImportBoxProps) {
  const inputRef = useRef<HTMLInputElement>(null);
  const [summary, setSummary] = useState<{ total: number; usable: number } | null>(null);

  const handleFile = async (file?: File | null) => {
    if (!file) return;
    const text = await file.text();
    const contacts = parseContacts(text);
    const usable = contacts.filter((contact) => channel === "whatsapp" ? contact.whatsapp : contact.email).length;
    setSummary({ total: contacts.length, usable });
    onContacts(contacts);
  };

  return (
    <div className="rounded-xl border border-surface-03 bg-surface-03/40 p-3 space-y-3">
      <div className="flex items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-xs font-semibold text-cream">Modelo padrao: nome,whatsapp,email</p>
          <p className="text-[11px] text-stone/70">CSV ou TXT separado por virgula ou ponto e virgula.</p>
        </div>
        <button
          type="button"
          onClick={() => inputRef.current?.click()}
          className="inline-flex items-center gap-2 rounded-lg bg-gold px-3 py-2 text-xs font-semibold text-black hover:bg-gold/90"
        >
          <Upload size={14} /> Importar
        </button>
      </div>
      <input
        ref={inputRef}
        type="file"
        accept=".csv,.txt,text/csv,text/plain"
        className="hidden"
        onChange={(event) => handleFile(event.target.files?.[0])}
      />
      <pre className="max-h-24 overflow-auto rounded-lg bg-surface-02 p-2 text-[11px] leading-relaxed text-stone">{TEMPLATE}</pre>
      {summary && (
        <div className="flex items-center gap-2 text-[11px] text-stone">
          <FileText size={13} className="text-gold" />
          <span>{summary.usable} contato(s) utilizavel(is) de {summary.total} linha(s) importada(s).</span>
        </div>
      )}
    </div>
  );
}
