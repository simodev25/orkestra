"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Sun, Moon } from "lucide-react";

export function ThemeToggle() {
  const { theme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  // Évite le mismatch d'hydration SSR :
  // côté serveur, on ne sait pas quel thème sera actif →
  // on rend un placeholder invisible jusqu'au montage client.
  useEffect(() => {
    setMounted(true);
  }, []);

  if (!mounted) {
    // Placeholder de même taille pour éviter le layout shift
    return <div className="w-7 h-7" />;
  }

  const isLight = theme === "light";

  return (
    <button
      onClick={() => setTheme(isLight ? "dark" : "light")}
      className="flex items-center justify-center w-7 h-7 rounded text-ork-muted hover:text-ork-text hover:bg-ork-hover transition-colors"
      title={isLight ? "Passer en mode sombre" : "Passer en mode clair"}
      aria-label={isLight ? "Passer en mode sombre" : "Passer en mode clair"}
    >
      {isLight
        ? <Moon className="w-3.5 h-3.5" />
        : <Sun className="w-3.5 h-3.5" />
      }
    </button>
  );
}
