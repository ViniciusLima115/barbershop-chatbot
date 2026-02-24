"use client";

import Link from "next/link";
import { CalendarDays, LayoutDashboard, Scissors, Settings2, Shield } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { getAuthSession, logout } from "@/services/auth";

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const session = getAuthSession();
  const tenantName = session?.tenantName ?? "";
  const isAdmin = session?.tenantId === "admin";
  const inAdminPage = pathname.startsWith("/admin");
  const navItems = [
    { href: "/", label: "Painel", icon: LayoutDashboard },
    { href: "/agenda", label: "Agenda", icon: CalendarDays },
    { href: "/gestao", label: "Gestao", icon: Settings2 },
    ...(isAdmin && !inAdminPage ? [{ href: "/admin", label: "Admin", icon: Shield }] : []),
  ];

  function handleLogout() {
    logout();
    router.replace("/login");
  }

  return (
    <header className="sticky top-0 z-50 border-b border-gray-200 bg-white/95 backdrop-blur">
      <div className="app-container flex h-16 items-center justify-between">
        <Link href="/" className="flex items-center gap-2 font-semibold text-gray-900">
          <div className="flex h-8 w-8 items-center justify-center rounded-lg bg-blue-600 text-white">
            <Scissors size={18} />
          </div>
          <span className="hidden sm:inline">
            {tenantName ? `${tenantName} - Sistema Interno` : "Barbearia - Sistema Interno"}
          </span>
        </Link>

        <div className="flex items-center gap-2">
          {!inAdminPage && (
            <nav className="flex items-center gap-1">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={`flex items-center gap-2 rounded-lg px-3 py-2 text-sm font-medium transition-colors ${
                      isActive
                        ? "bg-blue-50 text-blue-700"
                        : "text-gray-600 hover:bg-gray-100 hover:text-gray-900"
                    }`}
                  >
                    <Icon size={16} />
                    <span className="hidden sm:inline">{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          )}

          <button type="button" className="btn btn-secondary btn-sm" onClick={handleLogout}>
            Sair
          </button>
        </div>
      </div>
    </header>
  );
}
