"use client";

import { X, ListFilter } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { ScrollArea } from "@/components/ui/scroll-area";
import { ResultCard } from "./result-card";
import { SampleCard } from "./sample-card";
import type { StudyResult, SampleResult } from "@/lib/types";

interface ResultsPanelProps {
  studies: StudyResult[];
  samples: SampleResult[];
  filters: Record<string, string>;
  loading: boolean;
  turnLabel?: string;
}

export function ResultsPanel({ studies, samples, filters, loading, turnLabel }: ResultsPanelProps) {
  const filterEntries = Object.entries(filters);
  const totalCount = studies.length + samples.length;

  return (
    <Card>
      <CardHeader className="flex flex-row items-center justify-between gap-2">
        <div className="flex items-center gap-2">
          <ListFilter className="size-4" />
          <CardTitle className="text-base">Results</CardTitle>
        </div>
        {turnLabel && <span className="text-xs text-muted-foreground">{turnLabel}</span>}
      </CardHeader>

      <CardContent className="space-y-4">
        {filterEntries.length > 0 && (
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="text-xs text-muted-foreground">Filters:</span>
            {filterEntries.map(([field, value]) => (
              <Badge key={field} variant="secondary" className="gap-1">
                {value}
                <X className="size-3 opacity-60" />
              </Badge>
            ))}
          </div>
        )}

        <p className="text-sm text-muted-foreground">
          {loading
            ? "Searching…"
            : `${studies.length} stud${studies.length === 1 ? "y" : "ies"}${
                samples.length > 0 ? ` · ${samples.length} sample${samples.length === 1 ? "" : "s"}` : ""
              }`}
        </p>

        {!loading && totalCount === 0 && (
          <p className="py-8 text-center text-sm text-muted-foreground">
            Ask a question below to search GEO datasets.
          </p>
        )}

        {totalCount > 0 && (
          <ScrollArea className="h-[clamp(350px,45vh,400px)] pr-3">
            <div className="space-y-3">
              {studies.map((study) => (
                <ResultCard key={study.gse_id} study={study} />
              ))}
              {samples.map((sample) => (
                <SampleCard key={sample.gsm_id} sample={sample} />
              ))}
            </div>
          </ScrollArea>
        )}
      </CardContent>
    </Card>
  );
}