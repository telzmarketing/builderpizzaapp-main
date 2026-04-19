import { useState, useEffect } from "react";
import {
  MessageCircle, BarChart3, Settings, Brain, Cpu,
  HelpCircle, MessagesSquare, Zap, FileText,
} from "lucide-react";
import AdminSidebar from "@/components/AdminSidebar";
import ChatbotDashboard   from "./chatbot/ChatbotDashboard";
import ChatbotConfig      from "./chatbot/ChatbotConfig";
import ChatbotPrompt      from "./chatbot/ChatbotPrompt";
import ChatbotAI          from "./chatbot/ChatbotAI";
import ChatbotFAQ         from "./chatbot/ChatbotFAQ";
import ChatbotConversations from "./chatbot/ChatbotConversations";
import ChatbotAutomations from "./chatbot/ChatbotAutomations";
import ChatbotReports     from "./chatbot/ChatbotReports";

type Tab = "dashboard" | "config" | "prompt" | "ai" | "faq" | "conversations" | "automations" | "reports";

const TABS: { id: Tab; icon: React.ReactNode; label: string }[] = [
  { id: "dashboard",     icon: <BarChart3 size={15} />,       label: "Dashboard" },
  { id: "config",        icon: <Settings size={15} />,        label: "Configurações" },
  { id: "prompt",        icon: <Brain size={15} />,           label: "Prompt & IA" },
  { id: "ai",            icon: <Cpu size={15} />,             label: "Provedor" },
  { id: "faq",           icon: <HelpCircle size={15} />,      label: "Base FAQ" },
  { id: "conversations", icon: <MessagesSquare size={15} />,  label: "Conversas" },
  { id: "automations",   icon: <Zap size={15} />,             label: "Automações" },
  { id: "reports",       icon: <FileText size={15} />,        label: "Relatórios" },
];

export default function AdminChatbot() {
  const [tab, setTab] = useState<Tab>("dashboard");

  return (
    <div className="min-h-screen bg-gradient-to-br from-surface-01 to-surface-00">
      <div className="flex h-screen">
        <AdminSidebar />
        <div className="flex-1 flex flex-col overflow-hidden">

          {/* Top bar */}
          <div className="bg-surface-02 px-8 py-4 border-b border-surface-03 flex items-center gap-3 flex-shrink-0">
            <MessageCircle size={22} className="text-gold" />
            <div>
              <h2 className="text-xl font-bold text-cream">Chatbot</h2>
              <p className="text-stone text-xs">Atendimento inteligente integrado ao site</p>
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 px-6 pt-4 border-b border-surface-03 overflow-x-auto flex-shrink-0 bg-surface-02">
            {TABS.map((t) => (
              <button
                key={t.id}
                onClick={() => setTab(t.id)}
                className={`flex items-center gap-1.5 px-4 py-2.5 rounded-t-lg text-xs font-medium whitespace-nowrap transition-colors ${
                  tab === t.id
                    ? "bg-surface-01 text-gold border border-b-0 border-surface-03"
                    : "text-stone hover:text-parchment"
                }`}
              >
                {t.icon}
                {t.label}
              </button>
            ))}
          </div>

          {/* Content */}
          <div className="flex-1 overflow-y-auto bg-surface-01 p-6">
            {tab === "dashboard"     && <ChatbotDashboard />}
            {tab === "config"        && <ChatbotConfig />}
            {tab === "prompt"        && <ChatbotPrompt />}
            {tab === "ai"            && <ChatbotAI />}
            {tab === "faq"           && <ChatbotFAQ />}
            {tab === "conversations" && <ChatbotConversations />}
            {tab === "automations"   && <ChatbotAutomations />}
            {tab === "reports"       && <ChatbotReports />}
          </div>
        </div>
      </div>
    </div>
  );
}
