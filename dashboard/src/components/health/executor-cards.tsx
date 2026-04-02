"use client";

import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn, formatCost } from "@/lib/utils";
import type { ExecutorBreakdown } from "@/lib/types";

interface ExecutorCardsProps {
  data: ExecutorBreakdown;
}

export function ExecutorCards({ data }: ExecutorCardsProps) {
  const modes = [
    { key: "browser_use" as const, label: "Browser Use", stats: data.browser_use },
    { key: "native" as const, label: "Native", stats: data.native },
    { key: "sdk" as const, label: "SDK", stats: data.sdk },
  ];

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Executor Performance</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <div className="grid gap-4 sm:grid-cols-3">
          {modes.map(({ key, label, stats }) => (
            <div
              key={key}
              className={cn(
                "space-y-2 rounded-lg border p-4",
                stats.count === 0 && "opacity-50",
              )}
            >
              <div className="text-sm font-medium">{label}</div>
              <div className="space-y-1 text-sm">
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Success Rate</span>
                  <span className="font-medium">
                    {stats.count > 0
                      ? `${Math.round(stats.success_rate * 100)}%`
                      : "\u2014"}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Avg Cost</span>
                  <span className="font-medium">
                    {formatCost(stats.avg_cost)}
                  </span>
                </div>
                <div className="flex justify-between">
                  <span className="text-muted-foreground">Tasks</span>
                  <span className="font-medium">{stats.count}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      </CardContent>
    </Card>
  );
}
