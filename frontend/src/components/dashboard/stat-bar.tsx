import { Database, Users, Share2, Dna } from "lucide-react";
import { Card } from "@/components/ui/card";
import type { StatsOverview } from "@/lib/types";

interface StatBarProps {
  stats: StatsOverview | null;
}

function StatItem({
  icon,
  value,
  label,
}: {
  icon: React.ReactNode;
  value: number;
  label: string;
}) {
  return (
    <div className="flex items-center gap-3">
      <div className="flex size-9 items-center justify-center rounded-full bg-muted text-foreground">
        {icon}
      </div>
      <div>
        <div className="text-lg font-semibold leading-tight">{value}</div>
        <div className="text-xs text-muted-foreground">{label}</div>
      </div>
    </div>
  );
}

export function StatBar({ stats }: StatBarProps) {
  const overview = stats ?? {
    dataset_count: 0,
    sample_count: 0,
    platform_count: 0,
    tissue_count: 0,
    platform_distribution: [],
  };

  return (
    <Card className="flex flex-row flex-wrap items-center gap-6 px-6 py-4">
      <StatItem icon={<Database className="size-4" />} value={overview.dataset_count} label="Datasets" />
      <StatItem icon={<Users className="size-4" />} value={overview.sample_count} label="Samples" />
      <StatItem icon={<Share2 className="size-4" />} value={overview.platform_count} label="Platforms" />
      <StatItem icon={<Dna className="size-4" />} value={overview.tissue_count} label="Tissues" />
    </Card>
  );
}
