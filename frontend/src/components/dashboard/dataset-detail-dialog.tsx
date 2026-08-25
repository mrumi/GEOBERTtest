"use client";

import * as React from "react";
import { Loader2 } from "lucide-react";

import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
} from "@/components/ui/dialog";
import { Badge } from "@/components/ui/badge";
import { Separator } from "@/components/ui/separator";
import { getDatasetDetail, ApiError } from "@/lib/api";
import type { DatasetDetail } from "@/lib/types";

interface DatasetDetailDialogProps {
  gseId: string;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}

export function DatasetDetailDialog({ gseId, open, onOpenChange }: DatasetDetailDialogProps) {
  const [detail, setDetail] = React.useState<DatasetDetail | null>(null);
  const [loading, setLoading] = React.useState(false);
  const [error, setError] = React.useState<string | null>(null);

  React.useEffect(() => {
    if (!open) return;

    // eslint-disable-next-line react-hooks/set-state-in-effect -- synchronizing with the open prop to trigger a fresh fetch each time the dialog opens
    setLoading(true);
    setError(null);

    getDatasetDetail(gseId)
      .then(setDetail)
      .catch((err) => setError(err instanceof ApiError ? err.message : "Failed to load dataset"))
      .finally(() => setLoading(false));
  }, [open, gseId]);

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{gseId}</DialogTitle>
          <DialogDescription>Full dataset detail from GEO metadata</DialogDescription>
        </DialogHeader>

        {loading && (
          <div className="flex items-center justify-center py-8 text-muted-foreground">
            <Loader2 className="size-5 animate-spin" />
          </div>
        )}

        {error && <p className="text-sm text-destructive">{error}</p>}

        {detail && !loading && (
          <div className="space-y-4 text-sm">
            <div className="flex flex-wrap gap-1.5">
              {detail.organism && <Badge variant="secondary">{detail.organism}</Badge>}
              {detail.tissue && <Badge variant="secondary">{detail.tissue}</Badge>}
              {detail.library_strategy && <Badge variant="secondary">{detail.library_strategy}</Badge>}
              {detail.instrument_model && <Badge variant="outline">{detail.instrument_model}</Badge>}
            </div>

            {(detail.is_superseries || detail.is_subseries) && (
              <>
                <Separator />
                <div className="space-y-1">
                  {detail.is_superseries && detail.subseries_ids.length > 0 && (
                    <p>
                      <span className="font-medium">SuperSeries of:</span>{" "}
                      {detail.subseries_ids.join(", ")}
                    </p>
                  )}
                  {detail.is_subseries && detail.parent_series_id && (
                    <p>
                      <span className="font-medium">SubSeries of:</span> {detail.parent_series_id}
                    </p>
                  )}
                </div>
              </>
            )}

            <Separator />

            <div className="space-y-3 max-h-64 overflow-y-auto pr-1">
              {Object.entries(detail.fields).map(([fieldName, text]) => (
                <div key={fieldName}>
                  <div className="text-xs font-semibold uppercase text-muted-foreground mb-1">
                    {fieldName.replace(/_/g, " ")}
                  </div>
                  <p className="text-sm leading-relaxed">{text}</p>
                </div>
              ))}
            </div>

            <Separator />

            <p className="text-xs text-muted-foreground">
              {detail.sample_count} sample{detail.sample_count === 1 ? "" : "s"} in this study
            </p>

            <a
              href={detail.geo_link}
              target="_blank"
              rel="noopener noreferrer"
              className="text-xs text-primary underline underline-offset-2"
            >
              View on NCBI GEO ↗
            </a>
          </div>
        )}
      </DialogContent>
    </Dialog>
  );
}
