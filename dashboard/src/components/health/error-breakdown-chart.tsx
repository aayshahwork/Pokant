"use client";

import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
  LabelList,
} from "recharts";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { getErrorCategoryLabel } from "@/lib/utils";
import type { ErrorCategory, ErrorCategoryCount } from "@/lib/types";

const CATEGORY_COLORS: Record<string, string> = {
  transient_llm: "#f59e0b",
  rate_limited: "#a855f7",
  transient_network: "#f59e0b",
  transient_browser: "#eab308",
  permanent_llm: "#ef4444",
  permanent_browser: "#dc2626",
  permanent_task: "#b91c1c",
  unknown: "#6b7280",
};

interface ErrorBreakdownChartProps {
  data: ErrorCategoryCount[];
}

export function ErrorBreakdownChart({ data }: ErrorBreakdownChartProps) {
  if (data.length === 0) {
    return (
      <Card>
        <CardHeader>
          <CardTitle className="text-sm">Error Categories</CardTitle>
        </CardHeader>
        <CardContent className="pt-0">
          <div className="flex h-32 items-center justify-center text-sm text-muted-foreground">
            No errors in this period
          </div>
        </CardContent>
      </Card>
    );
  }

  const chartData = data.map((d) => ({
    ...d,
    label: getErrorCategoryLabel(d.category as ErrorCategory),
    color: CATEGORY_COLORS[d.category] ?? CATEGORY_COLORS.unknown,
  }));

  return (
    <Card>
      <CardHeader>
        <CardTitle className="text-sm">Error Categories</CardTitle>
      </CardHeader>
      <CardContent className="pt-0">
        <ResponsiveContainer
          width="100%"
          height={Math.max(140, data.length * 40)}
        >
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ left: 0, right: 50 }}
          >
            <XAxis type="number" tick={{ fontSize: 11 }} allowDecimals={false} />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fontSize: 11 }}
              width={130}
            />
            <Tooltip
              contentStyle={{
                borderRadius: "0.5rem",
                fontSize: "0.75rem",
                backgroundColor: "hsl(var(--card))",
                borderColor: "hsl(var(--border))",
              }}
              formatter={(value) => [
                typeof value === "number" ? value : 0,
                "Failures",
              ]}
            />
            <Bar dataKey="count" radius={[0, 4, 4, 0]}>
              <LabelList
                dataKey="count"
                position="right"
                style={{ fontSize: 11, fill: "currentColor" }}
              />
              {chartData.map((entry) => (
                <Cell key={entry.category} fill={entry.color} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </CardContent>
    </Card>
  );
}
