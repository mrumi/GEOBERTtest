"use client";

import * as React from "react";
import { Copy, ExternalLink, Check } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { DatasetDetailDialog } from "./dataset-detail-dialog";
import type { SampleResult } from "@/lib/types";

interface SampleCardProps {
  sample: SampleResult;
}

function relevanceVariant(score: number): "success" | "warning" | "destructive" {
  if (score >= 0.7) return "success";
  if (score >= 0.4) return "warning";
  return "destructive";
}

export function SampleCard({ sample }: SampleCardProps) {
  const [copied, setCopied] = React.useState(false);
  const [detailOpen, setDetailOpen] = React.useState(false);

  // No biosample_url in the trimmed schema — always construct the link.
  const openLink = `https://www.ncbi.nlm.nih.gov/geo/query/acc.cgi?acc=${sample.gsm_id}`;

  function handleCopy() {
    navigator.clipboard.writeText(sample.gsm_id);
    setCopied(true);
    setTimeout(() => setCopied(false), 1200);
  }

  return (
    <div className="rounded-lg border p-4 overflow-hidden">
      <div className="flex items-start justify-between gap-3 min-w-0">
        <div className="flex items-center gap-2 flex-wrap min-w-0">
          <span className="font-semibold text-sm shrink-0">{sample.gsm_id}</span>
          {typeof sample.relevance_score === "number" && (
            <Badge variant={relevanceVariant(sample.relevance_score)} className="shrink-0">
              Score {sample.relevance_score.toFixed(2)}
            </Badge>
          )}
          <Badge variant="secondary" className="shrink-0">{sample.gse_id}</Badge>
        </div>

        <div className="flex items-center gap-1 shrink-0">
          <Button variant="ghost" size="sm" className="h-7 gap-1" onClick={handleCopy}>
            {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
            <span className="hidden sm:inline">Copy ID</span>
          </Button>
          <Button variant="ghost" size="sm" className="h-7 gap-1" asChild>
            <a href={openLink} target="_blank" rel="noopener noreferrer">
              <ExternalLink className="size-3.5" />
              <span className="hidden sm:inline">Open</span>
            </a>
          </Button>
        </div>
      </div>

      <div className="mt-2 flex flex-wrap gap-1.5 text-xs min-w-0">
        {sample.organism && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.organism}
          </Badge>
        )}
        {sample.tissue && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.tissue}
          </Badge>
        )}
        {sample.disease && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.disease}
          </Badge>
        )}
        {sample.genotype && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.genotype}
          </Badge>
        )}
        {sample.cell_type && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.cell_type}
          </Badge>
        )}
        {sample.cell_line && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.cell_line}
          </Badge>
        )}
        {sample.library_strategy && (
          <Badge variant="secondary" className="whitespace-normal break-words max-w-full">
            {sample.library_strategy}
          </Badge>
        )}
      </div>

      <div className="mt-3 flex items-center justify-end">
        <Button variant="outline" size="sm" className="h-7" onClick={() => setDetailOpen(true)}>
          Study Details
        </Button>
      </div>

      <DatasetDetailDialog gseId={sample.gse_id} open={detailOpen} onOpenChange={setDetailOpen} />
    </div>
  );
}