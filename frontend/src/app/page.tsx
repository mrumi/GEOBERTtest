"use client";

import * as React from "react";
import { useRouter } from "next/navigation";
import Image from "next/image";
import { AlertCircle, LogOut, Loader2 } from "lucide-react";

import { ThemeToggle } from "@/components/theme-toggle";
import { Button } from "@/components/ui/button";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { StatBar } from "@/components/dashboard/stat-bar";
import { ResultsPanel } from "@/components/dashboard/results-panel";
import { StatsQualityPanel } from "@/components/dashboard/stats-quality-panel";
import { ChatBox, type ChatMessage } from "@/components/dashboard/chat-box";
import { SessionHistoryPanel } from "@/components/dashboard/session-history-panel";
import { getToken, clearToken } from "@/lib/auth-store";
import { runQuery, listSessions, getSession, createSession, getMe, ApiError } from "@/lib/api";
import type { SessionSummary, UserOut } from "@/lib/types";

export default function DashboardPage() {
  const router = useRouter();

  const [checkingAuth, setCheckingAuth] = React.useState(true);
  const [user, setUser] = React.useState<UserOut | null>(null);

  const [sessionId, setSessionId] = React.useState<string | null>(null);
  const [sessions, setSessions] = React.useState<SessionSummary[]>([]);
  const [sessionsLoading, setSessionsLoading] = React.useState(false);

  const [messages, setMessages] = React.useState<ChatMessage[]>([]);
  const [activeIndex, setActiveIndex] = React.useState<number | null>(null);

  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  const activeMessage = activeIndex !== null ? messages[activeIndex] : null;
  const studies = activeMessage?.studies ?? [];
  const samples = activeMessage?.samples ?? [];
  const filters = activeMessage?.filters ?? {};
  const dashboardStats = activeMessage?.dashboardStats ?? null;

  const assistantIndices = React.useMemo(
    () => messages.reduce<number[]>((acc, m, i) => (m.role === "assistant" ? [...acc, i] : acc), []),
    [messages]
  );
  const turnLabel =
    assistantIndices.length > 1 && activeIndex !== null
      ? `Query ${assistantIndices.indexOf(activeIndex) + 1} of ${assistantIndices.length}`
      : undefined;

  const refreshSessions = React.useCallback(async () => {
    if (!getToken()) return;
    setSessionsLoading(true);
    try {
      const list = await listSessions();
      setSessions(list);
    } catch {
      // silently ignore
    } finally {
      setSessionsLoading(false);
    }
  }, []);

  React.useEffect(() => {
    const token = getToken();
    if (!token) {
      router.push("/login");
      return;
    }
    getMe()
      .then((profile) => {
        setUser(profile);
        setCheckingAuth(false);
      })
      .catch(() => {
        clearToken();
        router.push("/login");
      });
  }, [router]);

  function handleLogout() {
    clearToken();
    router.push("/login");
  }

  React.useEffect(() => {
    // eslint-disable-next-line react-hooks/set-state-in-effect
    refreshSessions();
  }, [refreshSessions]);

  async function handleSend(query: string) {
    setError(null);
    setLoading(true);
    const assistantIndex = messages.length + 1;
    setMessages((prev) => [...prev, { role: "user", content: query }]);

    try {
      const result = await runQuery(query, sessionId);

      setSessionId(result.session_id);
      setMessages((prev) => [
        ...prev,
        {
          role: "assistant",
          content: result.answer,
          studies: result.studies,
          samples: result.samples,
          dashboardStats: result.dashboard_stats,
          filters: result.filters,
        },
      ]);
      setActiveIndex(assistantIndex);

      refreshSessions();
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Something went wrong.";
      setError(message);
      setMessages((prev) => [...prev, { role: "assistant", content: `⚠️ ${message}` }]);
    } finally {
      setLoading(false);
    }
  }

  async function handleSelectSession(id: string) {
    setError(null);
    setLoading(true);
    try {
      const detail = await getSession(id);
      setSessionId(detail.id);

      const restored: ChatMessage[] = detail.messages.map((m) => ({
        role: m.role,
        content: m.content,
        studies: m.studies ?? undefined,
        samples: m.samples ?? undefined,
        dashboardStats: m.dashboard_stats ?? undefined,
        filters: (m.query_info?.filters as Record<string, string> | undefined) ?? undefined,
      }));
      setMessages(restored);

      let lastAssistant: number | null = null;
      restored.forEach((m, i) => {
        if (m.role === "assistant") lastAssistant = i;
      });
      setActiveIndex(lastAssistant);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to load session.");
    } finally {
      setLoading(false);
    }
  }

  async function handleNewSession() {
    setError(null);
    try {
      const session = await createSession();
      setSessionId(session.id);
      setMessages([]);
      setActiveIndex(null);
      refreshSessions();
    } catch (err) {
      setError(err instanceof ApiError ? err.message : "Failed to create session.");
    }
  }

  function handleSessionDeleted(deletedId: string) {
    setSessions((prev) => prev.filter((s) => s.id !== deletedId));
    if (sessionId === deletedId) {
      setSessionId(null);
      setMessages([]);
      setActiveIndex(null);
    }
  }

  if (checkingAuth) {
    return (
      <div className="flex min-h-screen items-center justify-center">
        <Loader2 className="size-6 animate-spin text-muted-foreground" />
      </div>
    );
  }

  return (
    <div className="mx-auto max-w-7xl space-y-4 p-4 sm:p-6">
      <header className="flex items-center justify-between gap-3">
        <div className="flex items-center gap-2">
          <Image src="/logo.png" alt="GeoBERT Logo" width={150} height={190}/>
        </div>
        <div className="flex items-center gap-3">
          {user && (
            <div className="flex items-center gap-2">
              <Avatar className="size-7">
                <AvatarFallback className="text-[11px]">
                  {user.full_name.split(" ").map((p) => p[0]).slice(0, 2).join("").toUpperCase()}
                </AvatarFallback>
              </Avatar>
              <div className="hidden text-right sm:block">
                <div className="text-sm font-medium leading-tight">{user.full_name}</div>
                <div className="text-xs capitalize text-muted-foreground leading-tight">{user.role}</div>
              </div>
            </div>
          )}
          <ThemeToggle />
          <Button variant="ghost" size="icon" onClick={handleLogout} aria-label="Log out">
            <LogOut className="size-4" />
          </Button>
        </div>
      </header>

      {error && (
        <div className="flex items-center gap-2 rounded-md border border-destructive/40 bg-destructive/10 px-3 py-2 text-sm text-destructive">
          <AlertCircle className="size-4 shrink-0" />
          {error}
        </div>
      )}

      <StatBar stats={dashboardStats?.stats_overview ?? null} />

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="lg:col-span-2">
          <ResultsPanel studies={studies} samples={samples} filters={filters} loading={loading} turnLabel={turnLabel} />
        </div>
        <div>
          <StatsQualityPanel stats={dashboardStats} />
        </div>
      </div>

      <div className="grid h-[clamp(320px,70vh,500px)] grid-cols-1 gap-4 lg:grid-cols-3">
        <div className="min-h-0 lg:col-span-2">
          <ChatBox
            messages={messages}
            onSend={handleSend}
            loading={loading}
            activeIndex={activeIndex}
            onActiveIndexChange={setActiveIndex}
          />
        </div>
        <div className="min-h-0">
          <SessionHistoryPanel
            sessions={sessions}
            currentSessionId={sessionId}
            onSelectSession={handleSelectSession}
            onNewSession={handleNewSession}
            onSessionDeleted={handleSessionDeleted}
            loading={sessionsLoading}
          />
        </div>
      </div>
    </div>
  );
}