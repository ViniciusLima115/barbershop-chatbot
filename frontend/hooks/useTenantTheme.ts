"use client";

import { useEffect } from "react";
import { useAuthSession } from "@/services/auth";

const DEFAULT_ACCENT = "#d4930a";
const DEFAULT_BG = "#ffffff";

export function useTenantTheme() {
  const session = useAuthSession();

  useEffect(() => {
    const accent = session?.accentColor || DEFAULT_ACCENT;
    const bg = session?.bgColor || DEFAULT_BG;

    document.documentElement.style.setProperty("--accent", accent);
    document.documentElement.style.setProperty("--accent-tenant", accent);
    document.documentElement.style.setProperty("--bg-tenant", bg);
  }, [session?.accentColor, session?.bgColor]);
}
