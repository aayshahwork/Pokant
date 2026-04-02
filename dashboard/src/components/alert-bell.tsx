"use client";

import { useState, useEffect, useCallback, useRef } from "react";
import { useRouter } from "next/navigation";
import {
  Bell,
  AlertTriangle,
  DollarSign,
  XCircle,
  RotateCcw,
  CheckCircle,
  Check,
} from "lucide-react";
import { formatDistanceToNow } from "date-fns";
import { Button } from "@/components/ui/button";
import {
  DropdownMenu,
  DropdownMenuTrigger,
  DropdownMenuContent,
  DropdownMenuItem,
  DropdownMenuSeparator,
} from "@/components/ui/dropdown-menu";
import { useApiClient } from "@/hooks/use-api-client";
import { ApiError } from "@/lib/api-client";
import type { AlertResponse } from "@/lib/types";

const POLL_INTERVAL = 30_000;
const MAX_ALERTS = 10;

const ALERT_CONFIG: Record<string, { icon: typeof AlertTriangle; className: string }> = {
  success_rate_drop: { icon: AlertTriangle, className: "text-red-500" },
  cost_spike: { icon: DollarSign, className: "text-amber-500" },
  repeated_failure: { icon: XCircle, className: "text-red-500" },
  stuck_detected: { icon: RotateCcw, className: "text-amber-500" },
};

function getAlertConfig(alertType: string) {
  return ALERT_CONFIG[alertType] ?? { icon: AlertTriangle, className: "text-muted-foreground" };
}

export function AlertBell() {
  const client = useApiClient();
  const router = useRouter();
  const [alerts, setAlerts] = useState<AlertResponse[]>([]);
  const [endpointAvailable, setEndpointAvailable] = useState(true);
  const [pulse, setPulse] = useState(false);
  const prevCountRef = useRef(0);

  const fetchAlerts = useCallback(async () => {
    if (!client) return;
    try {
      const res = await client.listAlerts({ limit: MAX_ALERTS, acknowledged: false });
      if (res.total === 0 && res.alerts.length === 0) {
        setAlerts([]);
      } else {
        setAlerts(res.alerts);
      }

      if (res.alerts.length > prevCountRef.current && prevCountRef.current !== 0) {
        setPulse(true);
        setTimeout(() => setPulse(false), 1500);
      }
      prevCountRef.current = res.alerts.length;
      setEndpointAvailable(true);
    } catch (error) {
      if (error instanceof ApiError && error.status === 404) {
        console.debug("Alerts endpoint not available");
        setEndpointAvailable(false);
      }
    }
  }, [client]);

  useEffect(() => {
    fetchAlerts();
  }, [fetchAlerts]);

  useEffect(() => {
    if (!endpointAvailable || !client) return;
    const interval = setInterval(fetchAlerts, POLL_INTERVAL);
    return () => clearInterval(interval);
  }, [endpointAvailable, client, fetchAlerts]);

  const handleAcknowledge = useCallback(
    async (e: React.MouseEvent, alertId: string) => {
      e.stopPropagation();
      if (!client) return;
      try {
        await client.acknowledgeAlert(alertId);
        setAlerts((prev) => prev.filter((a) => a.id !== alertId));
        prevCountRef.current = Math.max(0, prevCountRef.current - 1);
      } catch {
        // Silently fail — alert stays in list
      }
    },
    [client],
  );

  const count = alerts.length;

  return (
    <DropdownMenu>
      <DropdownMenuTrigger
        render={
          <Button variant="ghost" size="icon-sm" className="relative">
            <Bell className="size-4" />
            {count > 0 && (
              <span
                className={`absolute -right-1 -top-1 flex size-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white ${
                  pulse ? "animate-pulse" : ""
                }`}
              >
                {count > 9 ? "9+" : count}
              </span>
            )}
          </Button>
        }
      />
      <DropdownMenuContent align="end" sideOffset={8} className="w-80">
        <div className="px-2 py-1.5 text-sm font-semibold">
          Alerts{count > 0 ? ` (${count})` : ""}
        </div>
        <DropdownMenuSeparator />

        {count === 0 ? (
          <div className="flex flex-col items-center gap-2 py-6 text-sm text-muted-foreground">
            <CheckCircle className="size-8 text-green-500" />
            No alerts
          </div>
        ) : (
          alerts.map((alert) => {
            const config = getAlertConfig(alert.alert_type);
            const Icon = config.icon;
            return (
              <DropdownMenuItem
                key={alert.id}
                className="flex items-start gap-2 py-2"
                onClick={() => {
                  if (alert.task_id) {
                    router.push(`/tasks/${alert.task_id}`);
                  }
                }}
              >
                <Icon className={`mt-0.5 size-4 shrink-0 ${config.className}`} />
                <div className="flex-1 overflow-hidden">
                  <p className="truncate text-sm">{alert.message}</p>
                  <p className="text-xs text-muted-foreground">
                    {formatDistanceToNow(new Date(alert.created_at), { addSuffix: true })}
                  </p>
                </div>
                <Button
                  variant="ghost"
                  size="icon-xs"
                  className="shrink-0"
                  onClick={(e) => handleAcknowledge(e, alert.id)}
                >
                  <Check className="size-3" />
                </Button>
              </DropdownMenuItem>
            );
          })
        )}

        <DropdownMenuSeparator />
        <DropdownMenuItem
          className="justify-center text-xs text-muted-foreground"
          onClick={() => router.push("/health")}
        >
          View all &rarr;
        </DropdownMenuItem>
      </DropdownMenuContent>
    </DropdownMenu>
  );
}
