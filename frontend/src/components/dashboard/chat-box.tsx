"use client";

import * as React from "react";
import { Send, MessageSquare, Loader2 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Button } from "@/components/ui/button";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { Avatar, AvatarFallback } from "@/components/ui/avatar";
import { cn } from "@/lib/utils";
import type { StudyResult, SampleResult, DashboardStats } from "@/lib/types";

export interface ChatMessage {
  role: "user" | "assistant";
  content: string;

  // Only present on assistant messages — the result snapshot that
  // belongs to this turn.
  studies?: StudyResult[];
  samples?: SampleResult[];
  dashboardStats?: DashboardStats | null;
  filters?: Record<string, string>;
}

interface ChatBoxProps {
  messages: ChatMessage[];
  onSend: (query: string) => void;
  loading: boolean;

  // Index into `messages` of the assistant turn whose results are
  // currently shown in Results/Stats.
  activeIndex: number | null;

  // Fired as a different assistant message scrolls into view.
  onActiveIndexChange: (index: number) => void;
}

const SUGGESTED_QUERIES = [
  "Mouse retina 10x datasets",
  "Retina PMI < 24h",
  "Human blood Control vs Disease",
  "Human retina scRNA-seq GSEs",
];

export function ChatBox({
  messages,
  onSend,
  loading,
  activeIndex,
  onActiveIndexChange,
}: ChatBoxProps) {
  const [value, setValue] = React.useState("");

  const bottomRef = React.useRef<HTMLDivElement>(null);
  const viewportRef = React.useRef<HTMLDivElement>(null);
  const bubbleRefs = React.useRef<Map<number, HTMLDivElement>>(new Map());
  const prevMessageCount = React.useRef(0);

  // Only jump to bottom when a NEW message is appended.
  // Never do this on every render, otherwise the user would be
  // pulled back down while reviewing an older message.
  React.useEffect(() => {
    if (messages.length > prevMessageCount.current) {
      bottomRef.current?.scrollIntoView({ behavior: "smooth" });
    }

    prevMessageCount.current = messages.length;
  }, [messages.length]);

  // Scrollspy:
  // Whichever assistant bubble crosses the center area of the
  // chat viewport becomes the active turn.
  React.useEffect(() => {
    const root = viewportRef.current;

    if (!root) return;

    const observer = new IntersectionObserver(
      (entries) => {
        const visible = entries.find((e) => e.isIntersecting);

        if (!visible) return;

        const index = Number(
          (visible.target as HTMLElement).dataset.msgIndex
        );

        if (!Number.isNaN(index)) {
          onActiveIndexChange(index);
        }
      },
      {
        root,
        rootMargin: "-45% 0px -45% 0px",
        threshold: 0,
      }
    );

    bubbleRefs.current.forEach((el) => observer.observe(el));

    return () => observer.disconnect();
  }, [messages, onActiveIndexChange]);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();

    const trimmed = value.trim();

    if (!trimmed || loading) return;

    onSend(trimmed);
    setValue("");
  }

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="shrink-0 flex flex-row items-center gap-2">
        <MessageSquare className="size-4" />
        <CardTitle className="text-base">Ask a question</CardTitle>
      </CardHeader>

      <CardContent className="flex min-h-0 flex-1 flex-col gap-3">
        {/* Chat area is ALWAYS visible */}
        <ScrollArea
          className="min-h-0 flex-1 rounded-md border p-3"
          viewportRef={viewportRef}
        >
          {messages.length === 0 ? (
            <div className="flex h-full items-center justify-center">
              <p className="px-6 text-center text-sm text-muted-foreground">
                Ask a question to start the conversation.
              </p>
            </div>
          ) : (
            <div className="space-y-3">
              {messages.map((m, i) => {
                const isActiveTurn =
                  m.role === "assistant" && i === activeIndex;

                return (
                  <div
                    key={i}
                    ref={(el) => {
                      if (m.role === "assistant") {
                        if (el) {
                          bubbleRefs.current.set(i, el);
                        } else {
                          bubbleRefs.current.delete(i);
                        }
                      }
                    }}
                    data-msg-index={i}
                    className={cn(
                      "flex gap-2 text-sm",
                      m.role === "user" && "flex-row-reverse"
                    )}
                  >
                    <Avatar className="size-6 shrink-0">
                      <AvatarFallback className="text-[10px]">
                        {m.role === "user" ? "You" : "AI"}
                      </AvatarFallback>
                    </Avatar>

                    <div
                      className={cn(
                        "max-w-[85%] rounded-lg px-3 py-2 whitespace-pre-wrap",
                        m.role === "user"
                          ? "bg-primary text-primary-foreground"
                          : "bg-muted",
                        isActiveTurn && "ring-2 ring-primary/50"
                      )}
                    >
                      {m.content}
                    </div>
                  </div>
                );
              })}

              {loading && (
                <div className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="size-3.5 animate-spin" />
                  Thinking…
                </div>
              )}

              <div ref={bottomRef} />
            </div>
          )}
        </ScrollArea>

        {/* Input */}
        <form onSubmit={handleSubmit} className="flex shrink-0 gap-2">
          <Input
            value={value}
            onChange={(e) => setValue(e.target.value)}
            placeholder="Ask about datasets, genes, conditions, platforms…"
            disabled={loading}
          />

          <Button
            type="submit"
            size="icon"
            disabled={loading || !value.trim()}
            
          >
            <Send className="size-4" />
          </Button>
        </form>

        {/* Suggested queries */}
        <div className="shrink-0 space-y-1.5">
          <p className="text-xs text-muted-foreground">
            Suggested queries:
          </p>

          <div className="flex flex-wrap gap-1.5">
            {SUGGESTED_QUERIES.map((q) => (
              <Badge
                key={q}
                variant="outline"
                className="cursor-pointer hover:bg-accent"
                onClick={() => !loading && onSend(q)}
              >
                {q}
              </Badge>
            ))}
          </div>
        </div>
      </CardContent>
    </Card>
  );
}