"use client";

import { Button } from "@/components/ui/button";
import type { AnalyticsPeriod } from "@/lib/types";

const PERIODS: { value: AnalyticsPeriod; label: string }[] = [
  { value: "1h", label: "1h" },
  { value: "6h", label: "6h" },
  { value: "24h", label: "24h" },
  { value: "7d", label: "7d" },
  { value: "30d", label: "30d" },
];

interface PeriodSelectorProps {
  period: AnalyticsPeriod;
  onChange: (period: AnalyticsPeriod) => void;
}

export function PeriodSelector({ period, onChange }: PeriodSelectorProps) {
  return (
    <div className="flex gap-1">
      {PERIODS.map((p) => (
        <Button
          key={p.value}
          variant={period === p.value ? "default" : "outline"}
          size="sm"
          className="h-7 px-2.5 text-xs"
          onClick={() => onChange(p.value)}
        >
          {p.label}
        </Button>
      ))}
    </div>
  );
}
