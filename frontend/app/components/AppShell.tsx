"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import Header from "./Header";
import ThemeToggle from "./ThemeToggle";
import { useTenantTheme } from "@/hooks/useTenantTheme";
import { NotificacoesProvider } from "./NotificacoesProvider";

type AppShellProps = {
  children: ReactNode;
};

const TOKEN_ACTION_PREFIXES = ["/confirmar/", "/cancelar/", "/reagendar/"];

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  useTenantTheme();
  const inLogin = pathname === "/login";
  const isPublicBookingById = pathname.startsWith("/agendar/");
  const isTokenActionPage = TOKEN_ACTION_PREFIXES.some((p) => pathname.startsWith(p));
  const ADMIN_PATHS = ["/login", "/admin", "/agenda", "/gestao", "/dashboard", "/configuracoes", "/upgrade", "/painel"];
  const isPublicBookingPath =
    !isPublicBookingById &&
    !isTokenActionPage &&
    /^\/[^/]+$/.test(pathname) &&
    !ADMIN_PATHS.includes(pathname);

  const hideHeader = inLogin || isPublicBookingPath || isPublicBookingById || isTokenActionPage;

  const content = (
    <>
      {!hideHeader && <Header />}
      {(isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />}
      {children}
    </>
  );

  if (hideHeader) {
    return content;
  }

  return <NotificacoesProvider>{content}</NotificacoesProvider>;
}
