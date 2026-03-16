"use client";

import { ReactNode } from "react";
import { usePathname } from "next/navigation";
import Header from "./Header";
import ThemeToggle from "./ThemeToggle";

type AppShellProps = {
  children: ReactNode;
};

const TOKEN_ACTION_PREFIXES = ["/confirmar/", "/cancelar/", "/reagendar/"];

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const inLogin = pathname === "/login";
  const isPublicBookingById = pathname.startsWith("/agendar/");
  const isTokenActionPage = TOKEN_ACTION_PREFIXES.some((p) => pathname.startsWith(p));
  const isPublicBookingPath =
    !isPublicBookingById &&
    !isTokenActionPage &&
    /^\/[^/]+$/.test(pathname) &&
    !["/login", "/admin", "/agenda", "/gestao"].includes(pathname);

  const hideHeader = inLogin || isPublicBookingPath || isPublicBookingById || isTokenActionPage;

  return (
    <>
      {!hideHeader && <Header />}
      {(inLogin || isPublicBookingPath || isPublicBookingById) && <ThemeToggle floating />}
      {children}
    </>
  );
}
