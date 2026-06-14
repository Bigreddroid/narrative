import React from "react";
import ReactDOM from "react-dom/client";
import { BrowserRouter } from "react-router-dom";
import App from "./App.jsx";
import { ThemeProvider } from "./contexts/ThemeContext.jsx";
import { FollowingProvider } from "./contexts/FollowingContext.jsx";
import "./index.css";

// Apply saved theme before React paints — prevents flash of wrong theme
const saved = localStorage.getItem("narrative_theme") || "light";
const _root = document.documentElement;
_root.setAttribute("data-theme", saved);
if (saved === "dark") {
  _root.style.setProperty("--paper-rgb", "17,17,17");
  _root.style.setProperty("--ink-rgb",   "232,228,220");
  _root.style.setProperty("--paper",     "17 17 17");
  _root.style.setProperty("--ink",       "232 228 220");
} else {
  _root.style.setProperty("--paper-rgb", "245,241,235");
  _root.style.setProperty("--ink-rgb",   "26,26,26");
  _root.style.setProperty("--paper",     "245 241 235");
  _root.style.setProperty("--ink",       "26 26 26");
}
_root.style.setProperty("--crimson-rgb", "200,0,40");
_root.style.setProperty("--crimson",     "200 0 40");

ReactDOM.createRoot(document.getElementById("root")).render(
  <React.StrictMode>
    <BrowserRouter>
      <ThemeProvider>
        <FollowingProvider>
          <App />
        </FollowingProvider>
      </ThemeProvider>
    </BrowserRouter>
  </React.StrictMode>
);
