"use client";

import { ReactNode, useEffect } from "react";
import { usePathname, useRouter } from "next/navigation";
import Header from "./Header";
import { useAuthSession } from "@/services/auth";

type AppShellProps = {
  children: ReactNode;
};

export default function AppShell({ children }: AppShellProps) {
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuthSession();
  const logged = Boolean(session);
  const inLogin = pathname === "/login";
  const inAdmin = pathname.startsWith("/admin");
  const isAdmin = session?.tenantId === "admin";
  const routeState = `${logged}-${inLogin}-${inAdmin}-${isAdmin}`;

  useEffect(() => {
    if (!logged && !inLogin) {
      router.replace("/login");
    }

    if (logged && inLogin) {
      router.replace(isAdmin ? "/admin" : "/");
    }

    if (logged && inAdmin && !isAdmin) {
      router.replace("/");
    }
  }, [routeState, router, logged, inLogin, isAdmin, inAdmin]);

  if ((!logged && !inLogin) || (logged && inLogin) || (logged && inAdmin && !isAdmin)) {
    return (
      <div className="flex min-h-screen items-center justify-center bg-gray-50">
        <div className="spinner" aria-label="Carregando" />
      </div>
    );
  }

  return (
    <>
      {pathname !== "/login" && <Header />}
      {children}
    </>
  );
}
