"use client";

import { Activity, TrendingUp, DollarSign, Clock } from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatCost, formatDuration } from "@/lib/utils";
import type { HealthAnalyticsResponse } from "@/lib/types";

interface MetricsBarProps {
  data: HealthAnalyticsResponse;
}

export function MetricsBar({ data }: MetricsBarProps) {
  const pct = Math.round(data.success_rate * 100);
  const rateColor =
    data.success_rate > 0.9
      ? "text-green-600 dark:text-green-400"
      : data.success_rate >= 0.7
        ? "text-amber-600 dark:text-amber-400"
        : "text-red-600 dark:text-red-400";

  return (
    <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Runs
            </CardTitle>
            <Activity className="size-4 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          <span className="text-2xl font-bold">{data.total_runs}</span>
          <span className="ml-2 text-sm text-muted-foreground">
            {data.completed} ok / {data.failed} fail
          </span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Success Rate
            </CardTitle>
            <TrendingUp className="size-4 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          <span className={cn("text-2xl font-bold", data.total_runs > 0 ? rateColor : "")}>
            {data.total_runs > 0 ? `${pct}%` : "\u2014"}
          </span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Total Cost
            </CardTitle>
            <DollarSign className="size-4 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          <span className="text-2xl font-bold">
            {formatCost(data.total_cost_cents)}
          </span>
        </CardContent>
      </Card>

      <Card>
        <CardHeader className="pb-2">
          <div className="flex items-center justify-between">
            <CardTitle className="text-sm font-medium text-muted-foreground">
              Avg Duration
            </CardTitle>
            <Clock className="size-4 text-muted-foreground" />
          </div>
        </CardHeader>
        <CardContent>
          <span className="text-2xl font-bold">
            {data.total_runs > 0 ? formatDuration(data.avg_duration_ms) : "\u2014"}
          </span>
        </CardContent>
      </Card>
    </div>
  );
}
