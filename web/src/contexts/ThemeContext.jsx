import { createContext, useContext, useState, useCallback, useEffect } from "react";

const ThemeContext = createContext(null);

export function ThemeProvider({ children }) {
  const [theme, setTheme] = useState(
    () => localStorage.getItem("narrative_theme") || "dark"   // dark terminal default for desktop/enterprise
  );

  useEffect(() => {
    const root = document.documentElement;
    if (theme === "dark") {
      root.setAttribute("data-theme", "dark");
      root.style.setProperty("--paper-rgb", "17,17,17");
      root.style.setProperty("--ink-rgb",   "232,228,220");
      root.style.setProperty("--paper",     "17 17 17");
      root.style.setProperty("--ink",       "232 228 220");
    } else {
      root.setAttribute("data-theme", "light");
      root.style.setProperty("--paper-rgb", "245,241,235");
      root.style.setProperty("--ink-rgb",   "26,26,26");
      root.style.setProperty("--paper",     "245 241 235");
      root.style.setProperty("--ink",       "26 26 26");
    }
    localStorage.setItem("narrative_theme", theme);
  }, [theme]);

  const toggle = useCallback(() => {
    setTheme(t => t === "light" ? "dark" : "light");
  }, []);

  return (
    <ThemeContext.Provider value={{ theme, isDark: theme === "dark", toggle }}>
      {children}
    </ThemeContext.Provider>
  );
}

export function useTheme() {
  return useContext(ThemeContext);
}
