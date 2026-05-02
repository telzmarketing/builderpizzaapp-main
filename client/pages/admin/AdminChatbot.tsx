import { useState } from "react";
import { BarChart3, FileText, HelpCircle, MessageCircle, MessagesSquare, Settings, Zap } from "lucide-react";
import {
  AdminPageContent,
  AdminPageHeader,
  AdminPageShell,
  AdminPageTabs,
  type AdminPageTab,
} from "@/components/admin/AdminPageChrome";
import ChatbotDashboard from "./chatbot/ChatbotDashboard";
import ChatbotConfig from "./chatbot/ChatbotConfig";
import ChatbotFAQ from "./chatbot/ChatbotFAQ";
import ChatbotConversations from "./chatbot/ChatbotConversations";
import ChatbotAutomations from "./chatbot/ChatbotAutomations";
import ChatbotReports from "./chatbot/ChatbotReports";

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
        {tab === "dashboard" && <ChatbotDashboard />}
        {tab === "config" && <ChatbotConfig />}
        {tab === "faq" && <ChatbotFAQ />}
        {tab === "automations" && <ChatbotAutomations />}
        {tab === "conversations" && <ChatbotConversations />}
        {tab === "reports" && <ChatbotReports />}
      </AdminPageContent>
    </AdminPageShell>
  );
}
