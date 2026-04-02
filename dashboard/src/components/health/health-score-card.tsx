"use client";

import { Card, CardContent } from "@/components/ui/card";
import { cn } from "@/lib/utils";

interface HealthScoreCardProps {
  successRate: number;
  trend: number;
  totalRuns: number;
}

export function HealthScoreCard({
  successRate,
  trend,
  totalRuns,
}: HealthScoreCardProps) {
  const pct = Math.round(successRate * 100);
  const trendPp = Math.abs(Math.round(trend * 100));

  const rateColor =
    successRate > 0.9
      ? "text-green-600 dark:text-green-400"
      : successRate >= 0.7
        ? "text-amber-600 dark:text-amber-400"
        : "text-red-600 dark:text-red-400";

  const trendColor =
    trend > 0
      ? "text-green-600 dark:text-green-400"
      : trend < 0
        ? "text-red-600 dark:text-red-400"
        : "text-muted-foreground";

  return (
    <Card>
      <CardContent className="flex items-center gap-6 pt-6">
        <div className="flex flex-col items-center">
          <span className={cn("text-5xl font-bold tabular-nums", rateColor)}>
            {totalRuns > 0 ? `${pct}%` : "\u2014"}
          </span>
          <span className="mt-1 text-sm text-muted-foreground">
            Success Rate
          </span>
        </div>
        <div className="flex flex-col gap-1 text-sm">
          {trend !== 0 && (
            <span className={cn("font-medium", trendColor)}>
              {trend > 0 ? "\u2191" : "\u2193"} {trendPp}pp vs previous period
            </span>
          )}
          <span className="text-muted-foreground">
            {totalRuns.toLocaleString()} total runs
          </span>
        </div>
      </CardContent>
    </Card>
  );
}
