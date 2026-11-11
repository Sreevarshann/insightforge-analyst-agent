"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import * as Tooltip from "@radix-ui/react-tooltip";
import { MotionConfig } from "motion/react";
import { useState } from "react";
import { ThemeProvider } from "./theme";

export function Providers({ children }: { children: React.ReactNode }) {
  const [client] = useState(
    () => new QueryClient({ defaultOptions: { queries: { staleTime: 15_000, retry: 1, refetchOnWindowFocus: false } } }),
  );
  return (
    <QueryClientProvider client={client}>
      <ThemeProvider>
        {/* reducedMotion="user" makes every motion component honour prefers-reduced-motion */}
        <MotionConfig reducedMotion="user">
          <Tooltip.Provider delayDuration={250}>{children}</Tooltip.Provider>
        </MotionConfig>
      </ThemeProvider>
    </QueryClientProvider>
  );
}
