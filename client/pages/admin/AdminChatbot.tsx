import { lazy, Suspense, useState, type ComponentType } from "react";
import { BarChart3, FileText, HelpCircle, MessageCircle, MessagesSquare, Settings, Zap } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";

type Tab = "dashboard" | "config" | "faq" | "conversations" | "automations" | "reports";

const tabLoaders: Record<Tab, () => Promise<{ default: ComponentType }>> = {
  dashboard: () => import("./chatbot/ChatbotDashboard"),
  config: () => import("./chatbot/ChatbotConfig"),
  faq: () => import("./chatbot/ChatbotFAQ"),
  conversations: () => import("./chatbot/ChatbotConversations"),
  automations: () => import("./chatbot/ChatbotAutomations"),
  reports: () => import("./chatbot/ChatbotReports"),
};

const preloadedTabs = new Set<Tab>();

function preloadChatbotTab(tab: Tab) {
  if (preloadedTabs.has(tab)) return;
  preloadedTabs.add(tab);
  tabLoaders[tab]().catch(() => preloadedTabs.delete(tab));
}

const ChatbotDashboard = lazy(tabLoaders.dashboard);
const ChatbotConfig = lazy(tabLoaders.config);
const ChatbotFAQ = lazy(tabLoaders.faq);
const ChatbotConversations = lazy(tabLoaders.conversations);
const ChatbotAutomations = lazy(tabLoaders.automations);
const ChatbotReports = lazy(tabLoaders.reports);

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
      <AdminPageTabs
        tabs={TABS}
        active={tab}
        onPreview={preloadChatbotTab}
        onChange={(next) => {
          preloadChatbotTab(next);
          setTab(next as Tab);
        }}
      />
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
