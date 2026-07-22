import type { Metadata } from "next";
import { Plus_Jakarta_Sans, Jost } from "next/font/google";
import "./globals.css";
import AppShell from "./components/AppShell";
import { ThemeProvider } from "./components/ThemeProvider";

const plusJakartaSans = Plus_Jakarta_Sans({
  subsets: ["latin"],
  weight: ["400", "500", "600", "700", "800"],
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
  title: "Hagendei | Painel de Gestão",
  description: "Hagendei — plataforma de gestão de agendamentos para negócios e profissionais",
  openGraph: {
    title: "Hagendei | Painel de Gestão",
    description: "Hagendei — plataforma de gestão de agendamentos para negócios e profissionais",
  },
};

const themeScript = `
  (function () {
    try {
      var savedTheme = localStorage.getItem("hagendei:theme") || "system";
      var systemTheme = window.matchMedia("(prefers-color-scheme: dark)").matches ? "dark" : "light";
      var resolvedTheme = savedTheme === "system" ? systemTheme : savedTheme;
      document.documentElement.dataset.theme = resolvedTheme;
      document.documentElement.style.colorScheme = resolvedTheme;
    } catch (error) {
      document.documentElement.dataset.theme = "light";
      document.documentElement.style.colorScheme = "light";
    }
    try {
      var raw = localStorage.getItem("hagendei_auth_session");
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
      <body className={`antialiased ${plusJakartaSans.variable} ${jost.variable}`} suppressHydrationWarning>
        <script dangerouslySetInnerHTML={{ __html: themeScript }} />
        <ThemeProvider>
          <AppShell>{children}</AppShell>
        </ThemeProvider>
      </body>
    </html>
  );
}
