"use client";

import { formatDistanceToNow } from "date-fns";
import { Badge } from "@/components/ui/badge";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { FailingUrl } from "@/lib/types";

interface FailureHotspotsProps {
  data: FailingUrl[];
}

function truncateUrl(url: string, maxLen = 35): string {
  try {
    const u = new URL(url);
    const display = u.hostname + u.pathname;
    return display.length > maxLen
      ? display.slice(0, maxLen) + "\u2026"
      : display;
  } catch {
    return url.length > maxLen ? url.slice(0, maxLen) + "\u2026" : url;
  }
}

export function FailureHotspots({ data }: FailureHotspotsProps) {
  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Failure Hotspots</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        {data.length === 0 ? (
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
            No failure hotspots
          </div>
        ) : (
          <div className="space-y-3">
            {data.map((item) => (
              <div
                key={item.url}
                className="flex items-center justify-between gap-2"
              >
                <span
                  className="truncate text-sm font-medium"
                  title={item.url}
                >
                  {truncateUrl(item.url)}
                </span>
                <div className="flex shrink-0 items-center gap-2">
                  <Badge variant="destructive" className="text-[10px]">
                    {item.failure_count}
                  </Badge>
                  <span className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(item.last_failure), {
                      addSuffix: true,
                    })}
                  </span>
                </div>
              </div>
            ))}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
