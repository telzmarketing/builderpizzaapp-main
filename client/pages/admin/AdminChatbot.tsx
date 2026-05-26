import { lazy, Suspense, useState } from "react";
import { BarChart3, FileText, HelpCircle, MessageCircle, MessagesSquare, Settings, Zap } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";

const ChatbotDashboard = lazy(() => import("./chatbot/ChatbotDashboard"));
const ChatbotConfig = lazy(() => import("./chatbot/ChatbotConfig"));
const ChatbotFAQ = lazy(() => import("./chatbot/ChatbotFAQ"));
const ChatbotConversations = lazy(() => import("./chatbot/ChatbotConversations"));
const ChatbotAutomations = lazy(() => import("./chatbot/ChatbotAutomations"));
const ChatbotReports = lazy(() => import("./chatbot/ChatbotReports"));

type Tab = "dashboard" | "config" | "faq" | "conversations" | "automations" | "reports";

const TABS: AdminPageTab<Tab>[] = [
  { id: "dashboard", icon: <BarChart3 size={15} />, label: "Dashboard" },
  { id: "config", icon: <Settings size={15} />, label: "Configuracoes" },
  { id: "faq", icon: <HelpCircle size={15} />, label: "Base FAQ" },
  { id: "automations", icon: <Zap size={15} />, label: "Automacoes" },
  { id: "conversations", icon: <MessagesSquare size={15} />, label: "Conversas" },
  { id: "reports", icon: <FileText size={15} />, label: "Relatorios" },
];

export default function AdminChatbot() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <AdminPageShell>
      <AdminPageHeader
        icon={<MessageCircle size={20} />}
        title="Chatbot"
        description="Atendimento inteligente integrado ao site"
      />
      <AdminPageTabs tabs={TABS} active={tab} onChange={(next) => setTab(next as Tab)} />
      <AdminPageContent>
        <Suspense fallback={<ChatbotTabFallback />}>
          {tab === "dashboard" && <ChatbotDashboard />}
          {tab === "config" && <ChatbotConfig />}
          {tab === "faq" && <ChatbotFAQ />}
          {tab === "automations" && <ChatbotAutomations />}
          {tab === "conversations" && <ChatbotConversations />}
          {tab === "reports" && <ChatbotReports />}
        </Suspense>
      </AdminPageContent>
    </AdminPageShell>
  );
}

function ChatbotTabFallback() {
  return (
    <div className="rounded-lg border border-dashed border-gray-200 bg-white p-6 text-sm text-gray-500">
      Carregando painel do chatbot...
    </div>
  );
}
