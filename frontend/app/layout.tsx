import type { Metadata } from "next";
import { Libre_Baskerville, Jost } from "next/font/google";
import "./globals.css";
import AppShell from "./components/AppShell";
import { ThemeProvider } from "./components/ThemeProvider";

const libreBaskerville = Libre_Baskerville({
  subsets: ["latin"],
  weight: ["400", "700"],
  style: ["normal", "italic"],
  variable: "--font-display",
  display: "swap",
});

const jost = Jost({
  subsets: ["latin"],
  weight: ["300", "400", "500", "600", "700"],
  variable: "--font-body",
  display: "swap",
});

export const metadata: Metadata = {
  title: "VirtualBarber — Painel de Gestão",
  description: "Plataforma de gestão de agendamentos para estabelecimentos",
};

const themeScript = `
  (function () {
    try {
      var savedTheme = localStorage.getItem("virtualbarber:theme") || "system";
      var systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      var resolvedTheme = savedTheme === "system" ? systemTheme : savedTheme;
      document.documentElement.dataset.theme = resolvedTheme;
      document.documentElement.style.colorScheme = resolvedTheme;
    } catch (error) {
      document.documentElement.dataset.theme = "light";
      document.documentElement.style.colorScheme = "light";
    }
    try {
      var raw = localStorage.getItem("barbershop_auth_session");
      if (raw) {
        var s = JSON.parse(raw);
        if (s.accentColor) document.documentElement.style.setProperty("--accent", s.accentColor);
        if (s.accentColor) document.documentElement.style.setProperty("--accent-tenant", s.accentColor);
        if (s.bgColor) document.documentElement.style.setProperty("--bg-tenant", s.bgColor);
      }
    } catch (e) {}
  })();
`;

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="pt-BR" suppressHydrationWarning>
      <body className={`antialiased ${libreBaskerville.variable} ${jost.variable}`} suppressHydrationWarning>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
