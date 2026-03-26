"use client";

import { MonitorCog, MoonStar, SunMedium } from "lucide-react";
import { ThemeMode, useTheme } from "./ThemeProvider";

import styles from "./ThemeToggle.module.css";

type ThemeToggleProps = {
  floating?: boolean;
};

const labels: Record<ThemeMode, string> = {
  light: "Claro",
  dark: "Escuro",
  system: "Sistema",
};

const options: ThemeMode[] = ["light", "dark", "system"];

export default function ThemeToggle({ floating = false }: ThemeToggleProps) {
  const { theme, setTheme } = useTheme();

  return (
    <div className={`${styles.group} ${floating ? styles.floating : ""}`}>
      {options.map((option) => {
        const active = theme === option;
        const icon =
          option === "light" ? (
            <SunMedium size={16} />
          ) : option === "dark" ? (
            <MoonStar size={16} />
          ) : (
            <MonitorCog size={16} />
          );

        return (
          <button
            key={option}
            type="button"
            className={`${styles.button} ${active ? styles.buttonActive : ""}`}
            onClick={() => setTheme(option)}
            aria-pressed={active}
            title={`Tema ${labels[option]}`}
          >
            {icon}
            <span>{labels[option]}</span>
          </button>
        );
      })}
    </div>
  );
}
