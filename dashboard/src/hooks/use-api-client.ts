"use client";

import { useMemo } from "react";
import { useAuth } from "@/contexts/auth-context";
import { ApiClient, ApiError } from "@/lib/api-client";

// Single source of truth: reads API key from AuthContext, returns memoized ApiClient.
// Auto-clears auth state on 401 so AuthGuard can redirect to login.
export function useApiClient(): ApiClient | null {
  const { apiKey, logout } = useAuth();
  return useMemo(() => {
    if (!apiKey) return null;
    const client = new ApiClient(apiKey);
    return new Proxy(client, {
      get(target, prop, receiver) {
        const value = Reflect.get(target, prop, receiver);
        if (typeof value !== "function") return value;
        return async (...args: unknown[]) => {
          try {
            return await (value as (...a: unknown[]) => unknown).apply(target, args);
          } catch (error) {
            if (error instanceof ApiError && error.status === 401) {
              logout();
            }
            throw error;
          }
        };
      },
    });
  }, [apiKey, logout]);
}
