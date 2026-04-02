"use client";

import {
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import type { AnalyticsPeriod, HourlyBucket } from "@/lib/types";

interface HourlyActivityChartProps {
  data: HourlyBucket[];
  period: AnalyticsPeriod;
}

function formatXLabel(iso: string, period: AnalyticsPeriod): string {
  const d = new Date(iso);
  if (period === "7d" || period === "30d") {
    return `${String(d.getMonth() + 1).padStart(2, "0")}-${String(d.getDate()).padStart(2, "0")}`;
  }
  return `${String(d.getHours()).padStart(2, "0")}:${String(d.getMinutes()).padStart(2, "0")}`;
}

export function HourlyActivityChart({
  data,
  period,
}: HourlyActivityChartProps) {
  const label =
    period === "7d" || period === "30d" ? "Daily Activity" : "Hourly Activity";

  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">{label}</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex h-48 items-center justify-center text-sm text-muted-foreground">
            No activity in this period
          </div>
        </CardContent>
      </Card>
    );
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">{label}</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <ResponsiveContainer width="100%" height={240}>
          <AreaChart data={data}>
            <XAxis
              dataKey="hour"
              tick={{ fontSize: 11 }}
              tickFormatter={(v: string) => formatXLabel(v, period)}
            />
            <YAxis tick={{ fontSize: 11 }} allowDecimals={false} />
            <Tooltip
              contentStyle={{
                borderRadius: "0.5rem",
                fontSize: "0.75rem",
                backgroundColor: "hsl(var(--card))",
                borderColor: "hsl(var(--border))",
              }}
              labelStyle={{ color: "hsl(var(--foreground))" }}
              labelFormatter={(v) => formatXLabel(String(v), period)}
            />
            <Area
              type="monotone"
              dataKey="completed"
              stackId="1"
              stroke="var(--chart-2)"
              fill="var(--chart-2)"
              fillOpacity={0.3}
            />
            <Area
              type="monotone"
              dataKey="failed"
              stackId="1"
              stroke="var(--chart-5)"
              fill="var(--chart-5)"
              fillOpacity={0.3}
            />
          </AreaChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
