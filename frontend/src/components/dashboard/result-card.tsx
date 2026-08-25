"use client";

import * as React from "react";
import { Copy, ExternalLink, ChevronDown, ChevronUp, Check, Layers } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DatasetDetailDialog } from "./dataset-detail-dialog";
import type { StudyResult } from "@/lib/types";

interface ResultCardProps {
  study: StudyResult;
}

function relevanceVariant(score: number): "success" | "warning" | "destructive" {
  if (score >= 0.7) return "success";
  if (score >= 0.4) return "warning";
  return "destructive";
}

export function ResultCard({ study }: ResultCardProps) {
  const [copied, setCopied] = React.useState(false);
  const [expanded, setExpanded] = React.useState(false);
  const [detailOpen, setDetailOpen] = React.useState(false);

  function handleCopy() {
    navigator.clipboard.writeText(study.gse_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  const hasSeriesRelationship = study.is_superseries || study.is_subseries;

  return (
    <div className="rounded-lg border p-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3 min-w-0">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="font-semibold text-sm shrink-0">{study.gse_id}</span>
          <Badge variant={relevanceVariant(study.relevance_score)} className="shrink-0">
            Score {study.relevance_score.toFixed(2)}
          </Badge>
          {hasSeriesRelationship && (
            <Badge variant="outline" className="gap-1 shrink-0">
              <Layers className="size-3" />
              {study.is_superseries ? "SuperSeries" : "SubSeries"}
            </Badge>
          )}
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button variant="ghost" size="sm" className="h-7 gap-1" onClick={handleCopy}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            <span className="hidden sm:inline">Copy ID</span>
          </Button>
          <Button variant="ghost" size="sm" className="h-7 gap-1" asChild>
            <a href={study.geo_link} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-3.5" />
              <span className="hidden sm:inline">Open</span>
            </a>
          </Button>
        </div>
      </div>

      {/* organism/tissue/library_strategy can occasionally be long,
          multi-value strings (e.g. "Homo sapiens, Mus musculus, ...").
          whitespace-normal + break-words lets long badge text wrap
          onto multiple lines within its own badge instead of pushing
          the card wider than its container — this is the fix for the
          "breaks out of the card" bug. */}
      <div className="mt-2 flex flex-wrap gap-1.5 text-xs min-w-0">
        {study.organism && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {study.organism}
          </Badge>
        )}
        {study.tissue && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {study.tissue}
          </Badge>
        )}
        {study.library_strategy && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {study.library_strategy}
          </Badge>
        )}
      </div>

      {hasSeriesRelationship && (
        <p className="mt-2 text-xs text-muted-foreground break-words">
          {study.is_superseries && study.subseries_ids.length > 0 && (
            <>SuperSeries · {study.subseries_ids.length} subseries — see Details</>
          )}
          {study.is_subseries && study.parent_series_id && (
            <>SubSeries of {study.parent_series_id}</>
          )}
        </p>
      )}

      <div className="mt-3 flex items-center justify-between">
        <button
          onClick={() => setExpanded((v) => !v)}
          className="flex items-center gap-1 text-xs text-muted-foreground hover:text-foreground"
        >
          {expanded ? <ChevronUp className="size-3.5" /> : <ChevronDown className="size-3.5" />}
          {study.fields_found.length} field{study.fields_found.length === 1 ? "" : "s"} matched
        </button>

        <Button variant="outline" size="sm" className="h-7" onClick={() => setDetailOpen(true)}>
          Details
        </Button>
      </div>

      {expanded && (
        <div className="mt-2 flex flex-wrap gap-1">
          {study.fields_found.map((field) => (
            <Badge key={field} variant="outline" className="text-[10px]">
              {field.replace(/_/g, " ")}
            </Badge>
          ))}
        </div>
      )}

      <DatasetDetailDialog gseId={study.gse_id} open={detailOpen} onOpenChange={setDetailOpen} />
    </div>
  );
}
