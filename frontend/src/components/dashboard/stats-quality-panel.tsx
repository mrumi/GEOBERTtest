import { BarChart3 } from "lucide-react";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { Progress } from "@/components/ui/progress";
import { Separator } from "@/components/ui/separator";
import type { DashboardStats } from "@/lib/types";

interface StatsQualityPanelProps {
  stats: DashboardStats | null;
}

function MatchRow({ label, value }: { label: string; value: number | null }) {
  return (
    <div className="space-y-1">
      <div className="flex items-center justify-between text-xs">
        <span className="text-muted-foreground">{label}</span>
        <span className="font-medium">{value === null ? "N/A" : `${Math.round(value * 100)}%`}</span>
      </div>
      <Progress value={value === null ? 0 : value * 100} className="h-1.5" />
    </div>
  );
}

export function StatsQualityPanel({ stats }: StatsQualityPanelProps) {
  const overview = stats?.stats_overview;
  const relevance = stats?.relevance_quality;
  const topFields = stats?.top_fields_matched ?? [];

  return (
    <Card className="flex h-full flex-col">
      <CardHeader className="shrink-0 flex flex-row items-center gap-2">
        <BarChart3 className="size-4" />
        <CardTitle className="text-base">Stats & Quality</CardTitle>
      </CardHeader>

      <CardContent className="min-h-0 flex-1 space-y-5 overflow-y-auto">
        {/* Stats Overview — platform distribution */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
            Platforms
          </p>
          {!overview || overview.platform_distribution.length === 0 ? (
            <p className="text-xs text-muted-foreground">No results yet</p>
          ) : (
            <div className="space-y-2">
              {overview.platform_distribution.map((p) => (
                <div key={p.name} className="space-y-1">
                  <div className="flex items-center justify-between text-xs">
                    <span>{p.name}</span>
                    <span className="text-muted-foreground">
                      {p.count} ({p.percent}%)
                    </span>
                  </div>
                  <Progress value={p.percent} className="h-1.5" />
                </div>
              ))}
            </div>
          )}
        </div>

        <Separator />

        {/* Relevance & Quality */}
        <div className="space-y-3">
          <p className="text-xs font-semibold uppercase text-muted-foreground">
            Relevance & Quality
          </p>
          <MatchRow label="Query Match" value={relevance?.query_match ?? null} />
          <MatchRow label="Metadata Match" value={relevance?.metadata_match ?? null} />
        </div>

        <Separator />

        {/* Top Fields Matched */}
        <div>
          <p className="mb-2 text-xs font-semibold uppercase text-muted-foreground">
            Top Fields Matched
          </p>
          {topFields.length === 0 ? (
            <p className="text-xs text-muted-foreground">No results yet</p>
          ) : (
            <div className="flex flex-wrap gap-1.5">
              {topFields.map((field) => (
                <Badge key={field} variant="outline">
                  {field.replace(/_/g, " ")}
                </Badge>
              ))}
            </div>
          )}
        </div>
      </CardContent>
    </Card>
  );
}
