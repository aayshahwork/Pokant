"use client";

import { useState } from "react";
import {
  AlertTriangle,
  ChevronDown,
  ChevronRight,
  Lightbulb,
  Search,
} from "lucide-react";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { cn } from "@/lib/utils";
import type { RunAnalysis } from "@/lib/types";

const TIER_CONFIG: Record<number, { label: string; className: string }> = {
  1: {
    label: "Rule",
    className:
      "bg-gray-100 text-gray-700 dark:bg-gray-800 dark:text-gray-300",
  },
  2: {
    label: "History",
    className:
      "bg-blue-100 text-blue-700 dark:bg-blue-900/50 dark:text-blue-300",
  },
  3: {
    label: "AI",
    className:
      "bg-purple-100 text-purple-700 dark:bg-purple-900/50 dark:text-purple-300",
  },
};

function TierBadge({ tier }: { tier: number }) {
  const config = TIER_CONFIG[tier] ?? TIER_CONFIG[1];
  return (
    <span
      className={cn(
        "inline-flex items-center rounded px-1.5 py-0.5 text-[10px] font-medium",
        config.className,
      )}
    >
      T{tier} {config.label}
    </span>
  );
}

function ConfidenceBar({ confidence }: { confidence: number }) {
  return (
    <div className="h-1 w-16 rounded-full bg-muted overflow-hidden">
      <div
        className="h-full rounded-full bg-foreground/40"
        style={{ width: `${Math.round(confidence * 100)}%` }}
      />
    </div>
  );
}

interface AnalysisPanelProps {
  analysis: RunAnalysis;
  status: string;
}

export function AnalysisPanel({ analysis, status }: AnalysisPanelProps) {
  const isFailed = status === "failed";
  const [findingsOpen, setFindingsOpen] = useState(
    isFailed && analysis.findings.length <= 3,
  );

  const hasSuggestion =
    analysis.primary_suggestion && analysis.primary_suggestion.length > 0;
  const hasWaste = analysis.wasted_steps > 0;
  const looksLikeCode =
    hasSuggestion && /[/\\`{}()]/.test(analysis.primary_suggestion);

  return (
    <Card
      className={cn(
        isFailed
          ? "border-amber-500/50 bg-amber-50/50 dark:bg-amber-950/20"
          : "border-yellow-500/30 bg-yellow-50/30 dark:bg-yellow-950/10",
      )}
    >
      <CardHeader className="pb-3">
        <div className="flex items-center gap-2">
          <Search className="size-4 text-muted-foreground" />
          <CardTitle className="text-sm">Run Analysis</CardTitle>
          {analysis.tiers_executed.length > 0 && (
            <div className="ml-auto flex gap-1">
              {analysis.tiers_executed.map((t) => (
                <TierBadge key={t} tier={t} />
              ))}
            </div>
          )}
        </div>
      </CardHeader>
      <CardContent className="space-y-4 pt-0">
        {/* Summary */}
        {analysis.summary && <p className="text-sm">{analysis.summary}</p>}

        {/* Primary suggestion */}
        {hasSuggestion && (
          <div className="flex gap-2 rounded-md border bg-background/80 p-3">
            <Lightbulb className="mt-0.5 size-4 shrink-0 text-amber-500" />
            <p className={cn("text-sm", looksLikeCode && "font-mono text-xs")}>
              {analysis.primary_suggestion}
            </p>
          </div>
        )}

        {/* Waste stats */}
        {hasWaste && (
          <div className="flex items-center gap-2 text-sm text-amber-600 dark:text-amber-400">
            <AlertTriangle className="size-4" />
            <span>
              Wasted: {analysis.wasted_steps} step
              {analysis.wasted_steps !== 1 ? "s" : ""} ($
              {(analysis.wasted_cost_cents / 100).toFixed(4)})
            </span>
          </div>
        )}

        {/* Findings */}
        {analysis.findings.length > 0 && (
          <div>
            <button
              type="button"
              className="flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
              onClick={() => setFindingsOpen((prev) => !prev)}
            >
              {findingsOpen ? (
                <ChevronDown className="size-3.5" />
              ) : (
                <ChevronRight className="size-3.5" />
              )}
              All findings ({analysis.findings.length})
            </button>

            {findingsOpen && (
              <div className="mt-2 space-y-2">
                {analysis.findings.map((f, i) => (
                  <div
                    key={i}
                    className="space-y-1.5 rounded-md border bg-background/60 p-3"
                  >
                    <div className="flex items-center gap-2">
                      <TierBadge tier={f.tier} />
                      <span className="text-xs font-medium">{f.category}</span>
                      <div className="ml-auto flex items-center gap-1.5">
                        <ConfidenceBar confidence={f.confidence} />
                        <span className="text-[10px] tabular-nums text-muted-foreground">
                          {Math.round(f.confidence * 100)}%
                        </span>
                      </div>
                    </div>
                    <p className="text-sm text-muted-foreground">{f.summary}</p>
                    <p className="text-sm">
                      <span className="text-muted-foreground">&rarr;</span>{" "}
                      {f.suggestion}
                    </p>
                  </div>
                ))}
              </div>
            )}
          </div>
        )}
      </CardContent>
    </Card>
  );
}
