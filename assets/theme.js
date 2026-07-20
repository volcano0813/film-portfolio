(function () {
  const STORAGE_KEY = "elia-theme";
  const root = document.documentElement;

  function readTheme() {
    try {
      return localStorage.getItem(STORAGE_KEY) === "darkroom" ? "darkroom" : "day";
    } catch (_) {
      return "day";
    }
  }

  function applyTheme(theme, persist) {
    const nextTheme = theme === "darkroom" ? "darkroom" : "day";
    root.dataset.theme = nextTheme;
    root.style.colorScheme = nextTheme === "darkroom" ? "dark" : "light";
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      const dark = nextTheme === "darkroom";
      button.setAttribute("aria-pressed", String(dark));
      button.setAttribute("aria-label", dark ? "切换到日间模式" : "切换到暗房模式");
      const label = button.querySelector("[data-theme-label]");
      if (label) label.textContent = dark ? "DAY" : "DARKROOM";
    });
    if (persist) {
      try {
        localStorage.setItem(STORAGE_KEY, nextTheme);
      } catch (_) {
        // The visual theme still works when storage is unavailable.
      }
    }
    window.dispatchEvent(new CustomEvent("elia:themechange", { detail: { theme: nextTheme } }));
    return nextTheme;
  }

  function toggleTheme() {
    return applyTheme(root.dataset.theme === "darkroom" ? "day" : "darkroom", true);
  }

  applyTheme(readTheme(), false);

  document.addEventListener("DOMContentLoaded", () => {
    applyTheme(root.dataset.theme, false);
    document.querySelectorAll("[data-theme-toggle]").forEach((button) => {
      button.addEventListener("click", toggleTheme);
    });
  });

  window.EliaTheme = { apply: applyTheme, toggle: toggleTheme, current: () => root.dataset.theme };
})();
