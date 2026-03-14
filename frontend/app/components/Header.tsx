"use client";

import Link from "next/link";
import { CalendarDays, LayoutDashboard, Scissors, Settings2, Shield, LogOut } from "lucide-react";
import { usePathname, useRouter } from "next/navigation";
import { logout, useAuthSession } from "@/services/auth";
import styles from "./Header.module.css";

function cx(...values: Array<string | false | null | undefined>) {
  return values.filter(Boolean).join(" ");
}

export default function Header() {
  const pathname = usePathname();
  const router = useRouter();
  const session = useAuthSession();
  const tenantName = session?.tenantName ?? "Barbearia";
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
    <header className={styles.header}>
      <div className={cx("app-container", styles.shell)}>
        <Link href="/" className={styles.brand}>
          <div className={styles.brandIcon}>
            <Scissors size={18} />
          </div>
          <div className={styles.brandCopy}>
            <span className={styles.brandEyebrow}>Sistema interno</span>
            <span className={styles.brandTitle}>{tenantName}</span>
          </div>
        </Link>

        <div className={styles.actions}>
          {!inAdminPage ? (
            <nav className={styles.nav} aria-label="Navegacao principal">
              {navItems.map((item) => {
                const isActive = pathname === item.href;
                const Icon = item.icon;

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cx(styles.navLink, isActive && styles.navLinkActive)}
                  >
                    <Icon size={16} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </nav>
          ) : null}

          <button type="button" className={styles.logoutButton} onClick={handleLogout}>
            <LogOut size={16} />
            <span>Sair</span>
          </button>
        </div>
      </div>
    </header>
  );
}
