"use client";

import * as React from "react";
import { History, Plus, MoreVertical, Trash2, Loader2, Download } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Button } from "@/components/ui/button";
import { ScrollArea } from "@/components/ui/scroll-area";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
} from "@/components/ui/dropdown-menu";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "@/components/ui/alert-dialog";
import { cn } from "@/lib/utils";
import { deleteSession as deleteSessionApi, getSession, ApiError } from "@/lib/api";
import type { SessionSummary, SessionDetail } from "@/lib/types";

interface SessionHistoryPanelProps {
  sessions: SessionSummary[];
  currentSessionId: string | null;
  onSelectSession: (sessionId: string) => void;
  onNewSession: () => void;
  onSessionDeleted: (sessionId: string) => void;
  loading: boolean;
}

function timeAgo(isoDate: string): string {
  const diffMs = Date.now() - new Date(isoDate).getTime();
  const minutes = Math.floor(diffMs / 60000);
  if (minutes < 1) return "just now";
  if (minutes < 60) return `${minutes}m ago`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ago`;
  return `${Math.floor(hours / 24)}d ago`;
}

// One row per retrieved GSE/GSM per turn, plus the query/answer text
// that turn belongs to — so opening the CSV in a spreadsheet gives a
// flat, filterable table instead of nested JSON.
const CSV_HEADERS = [
  "turn", "user_query", "llm_generated_final_answer", "result_type", "Retrieved gse_id", "Retrieved gsm_id",
  "relevance_score", "geo_link",
];

function csvEscape(value: string | number | null | undefined): string {
  const str = value === null || value === undefined ? "" : String(value);
  if (/[",\n]/.test(str)) {
    return `"${str.replace(/"/g, '""')}"`;
  }
  return str;
}

function buildSessionCsv(detail: SessionDetail): string {
  const rows: (string | number)[][] = [];

  let turn = 0;
  let pendingQuery = "";

  for (const m of detail.messages) {
    if (m.role === "user") {
      turn += 1;
      pendingQuery = m.content;
      continue;
    }
    if (m.role !== "assistant") continue;

    const answer = m.content;
    const studies = m.studies ?? [];
    const samples = m.samples ?? [];

    if (studies.length === 0 && samples.length === 0) {
      rows.push([turn, pendingQuery, answer, "", "", "", "", ""]);
      continue;
    }

    for (const s of studies) {
      rows.push([
        turn, pendingQuery, answer, "study",
        s.gse_id, "",
        s.relevance_score != null ? s.relevance_score.toFixed(4) : "",
        s.geo_link ?? "",
      ]);
    }

    for (const s of samples) {
      rows.push([
        turn, pendingQuery, answer, "sample",
        s.gse_id, s.gsm_id,
        s.relevance_score != null ? s.relevance_score.toFixed(4) : "",
        `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${s.gsm_id}`,
      ]);
    }
  }

  const lines = [CSV_HEADERS.join(",")];
  for (const row of rows) {
    lines.push(row.map(csvEscape).join(","));
  }
  return lines.join("\n");
}

function triggerCsvDownload(filename: string, csvContent: string) {
  const blob = new Blob([csvContent], { type: "text/csv;charset=utf-8;" });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  document.body.removeChild(link);
  URL.revokeObjectURL(url);
}

export function SessionHistoryPanel({
  sessions,
  currentSessionId,
  onSelectSession,
  onNewSession,
  onSessionDeleted,
  loading,
}: SessionHistoryPanelProps) {
  const [pendingDeleteId, setPendingDeleteId] = React.useState<string | null>(null);
  const [deleting, setDeleting] = React.useState(false);
  const [deleteError, setDeleteError] = React.useState<string | null>(null);
  const [downloadingId, setDownloadingId] = React.useState<string | null>(null);

  async function handleConfirmDelete() {
    if (!pendingDeleteId) return;
    setDeleting(true);
    setDeleteError(null);
    try {
      await deleteSessionApi(pendingDeleteId);
      onSessionDeleted(pendingDeleteId);
      setPendingDeleteId(null);
    } catch (err) {
      setDeleteError(err instanceof ApiError ? err.message : "Failed to delete session.");
    } finally {
      setDeleting(false);
    }
  }

  async function handleDownload(session: SessionSummary) {
    if (downloadingId) return;
    setDownloadingId(session.id);
    try {
      const detail = await getSession(session.id);
      const csv = buildSessionCsv(detail);
      const safeTitle = session.title.replace(/[^a-z0-9]+/gi, "_").slice(0, 40);
      triggerCsvDownload(`geollm_${safeTitle}_${session.id.slice(0, 8)}.csv`, csv);
    } catch (err) {
      console.error("Failed to export session CSV:", err);
    } finally {
      setDownloadingId(null);
    }
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="shrink-0 flex flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <History className="size-4" />
          <CardTitle className="text-base">Session History</CardTitle>
        </div>
        <Button size="sm" variant="outline" className="h-7 gap-1" onClick={onNewSession}>
          <Plus className="size-3.5" />
          New Session
        </Button>
      </CardHeader>

      <CardContent className="min-h-0 flex-1">
        {sessions.length === 0 ? (
          <p className="py-6 text-center text-sm text-muted-foreground">
            {loading ? "Loading…" : "No sessions yet — ask a question to start one."}
          </p>
        ) : (
          <ScrollArea className="h-full">
            <div className="w-0 min-w-full space-y-1 pr-2">
              {sessions.map((s) => {
                const isCurrent = s.id === currentSessionId;
                return (
                  <div
                    key={s.id}
                    className={cn(
                      "group flex w-full items-center gap-1 rounded-md border border-transparent pr-1 transition-all duration-200",
                      "hover:bg-slate-200 hover:border-slate-500",
                      "dark:hover:bg-accent dark:hover:border-transparent",
                      isCurrent && "bg-accent border-slate-400 shadow-sm dark:border-transparent"
                    )}
                  >
                    <button
                      onClick={() => onSelectSession(s.id)}
                      className="flex min-w-0 flex-1 flex-col items-start gap-0.5 px-3 py-2 text-left text-sm"
                    >
                      <div className="flex w-full items-center gap-2 min-w-0">
                        <span
                          className={cn(
                            "size-1.5 shrink-0 rounded-full",
                            isCurrent ? "bg-primary" : "bg-muted-foreground/40"
                          )}
                        />
                        <span className="min-w-0 truncate font-medium">{s.title}</span>
                      </div>
                      <span className="pl-3.5 text-xs text-muted-foreground">
                        {timeAgo(s.updated_at)}
                        {isCurrent && " · current"}
                      </span>
                    </button>

                    <Button
                      variant="ghost"
                      size="icon"
                      className="size-7 shrink-0 opacity-40 hover:opacity-100"
                      aria-label="Download session as CSV"
                      disabled={downloadingId === s.id}
                      onClick={() => handleDownload(s)}
                    >
                      {downloadingId === s.id ? (
                        <Loader2 className="size-3.5 animate-spin" />
                      ) : (
                        <Download className="size-3.5" />
                      )}
                    </Button>

                    <DropdownMenu>
                      <DropdownMenuTrigger asChild>
                        <Button
                          variant="ghost"
                          size="icon"
                          className="size-7 shrink-0 opacity-40 group-hover:opacity-100 data-[state=open]:opacity-100"
                          aria-label="Session options"
                        >
                          <MoreVertical className="size-3.5" />
                        </Button>
                      </DropdownMenuTrigger>
                      <DropdownMenuContent align="end">
                        <DropdownMenuItem variant="destructive" onClick={() => setPendingDeleteId(s.id)}>
                          <Trash2 className="size-3.5" />
                          Delete
                        </DropdownMenuItem>
                      </DropdownMenuContent>
                    </DropdownMenu>
                  </div>
                );
              })}
            </div>
          </ScrollArea>
        )}
      </CardContent>

      <AlertDialog
        open={pendingDeleteId !== null}
        onOpenChange={(open) => {
          if (!open) {
            setPendingDeleteId(null);
            setDeleteError(null);
          }
        }}
      >
        <AlertDialogContent>
          <AlertDialogHeader>
            <AlertDialogTitle>Delete this chat?</AlertDialogTitle>
            <AlertDialogDescription>
              This will permanently delete this session and all its messages. This action cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>

          {deleteError && <p className="text-sm text-destructive">{deleteError}</p>}

          <AlertDialogFooter>
            <AlertDialogCancel disabled={deleting}>Cancel</AlertDialogCancel>
            <AlertDialogAction onClick={handleConfirmDelete} disabled={deleting}>
              {deleting ? <Loader2 className="size-3.5 animate-spin" /> : "Delete"}
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </Card>
  );
}