(function () {
  const searchInput = document.getElementById("global-search");
  const navItems = Array.from(document.querySelectorAll("[data-nav-item]"));
  const favButtons = Array.from(document.querySelectorAll("[data-fav-toggle]"));
  const quickAccess = document.getElementById("quick-access");
  const navToggle = document.getElementById("nav-toggle");
  const sidebar = document.getElementById("console-sidebar");
  const overlay = document.getElementById("console-overlay");
  const copyButtons = Array.from(document.querySelectorAll("[data-copy-endpoint]"));
  const favStorageKey = "uav-console-favorites-v1";
  const mobileBreakpoint = 1100;

  function loadFavorites() {
    try {
      const raw = window.localStorage.getItem(favStorageKey);
      const rows = raw ? JSON.parse(raw) : [];
      if (!Array.isArray(rows)) {
        return new Set();
      }
      return new Set(rows.filter((item) => typeof item === "string"));
    } catch (_err) {
      return new Set();
    }
  }

  function saveFavorites(favorites) {
    try {
      window.localStorage.setItem(favStorageKey, JSON.stringify(Array.from(favorites)));
    } catch (_err) {
      // Ignore localStorage failures.
    }
  }

  function renderFavorites(favorites) {
    favButtons.forEach((btn) => {
      const key = btn.getAttribute("data-fav-key") || "";
      if (favorites.has(key)) {
        btn.classList.add("on");
      } else {
        btn.classList.remove("on");
      }
    });

    if (!quickAccess) {
      return;
    }
    quickAccess.innerHTML = "";
    const favoriteLinks = navItems
      .map((item) => {
        const link = item.querySelector("[data-nav-link]");
        if (!link) {
          return null;
        }
        const key = item.querySelector("[data-fav-toggle]")?.getAttribute("data-fav-key") || "";
        return favorites.has(key) ? link : null;
      })
      .filter((item) => item !== null);

    if (!favoriteLinks.length) {
      quickAccess.innerHTML = '<li class="hint">Use "Fav" to pin entries.</li>';
      return;
    }
    favoriteLinks.forEach((link) => {
      const li = document.createElement("li");
      const anchor = document.createElement("a");
      anchor.href = link.getAttribute("href") || "#";
      anchor.textContent = link.textContent || "";
      anchor.className = "console-link";
      li.appendChild(anchor);
      quickAccess.appendChild(li);
    });
  }

  function applySearch(term) {
    const normalized = (term || "").trim().toLowerCase();
    navItems.forEach((node) => {
      const label = (node.getAttribute("data-nav-label") || "").toLowerCase();
      const visible = !normalized || label.includes(normalized);
      node.style.display = visible ? "" : "none";
    });
  }

  function setSidebarOpen(open) {
    if (!sidebar || !overlay) {
      return;
    }
    sidebar.classList.toggle("mobile-open", open);
    overlay.classList.toggle("active", open);
    if (navToggle) {
      navToggle.setAttribute("aria-expanded", open ? "true" : "false");
    }
    document.body.classList.toggle("nav-open", open);
  }

  function isMobile() {
    return window.innerWidth <= mobileBreakpoint;
  }

  const favorites = loadFavorites();
  renderFavorites(favorites);
  applySearch(searchInput ? searchInput.value : "");

  favButtons.forEach((btn) => {
    btn.addEventListener("click", () => {
      const key = btn.getAttribute("data-fav-key") || "";
      if (!key) {
        return;
      }
      if (favorites.has(key)) {
        favorites.delete(key);
      } else {
        favorites.add(key);
      }
      saveFavorites(favorites);
      renderFavorites(favorites);
    });
  });

  if (searchInput) {
    searchInput.addEventListener("input", () => {
      applySearch(searchInput.value);
    });
  }

  if (navToggle && sidebar && overlay) {
    navToggle.addEventListener("click", () => {
      const currentlyOpen = sidebar.classList.contains("mobile-open");
      setSidebarOpen(!currentlyOpen);
    });

    overlay.addEventListener("click", () => {
      setSidebarOpen(false);
    });

    window.addEventListener("resize", () => {
      if (!isMobile()) {
        setSidebarOpen(false);
      }
    });

    document.addEventListener("keydown", (event) => {
      if (event.key !== "Escape") {
        return;
      }
      if (!sidebar.classList.contains("mobile-open")) {
        return;
      }
      setSidebarOpen(false);
      navToggle.focus();
    });
  }

  copyButtons.forEach((btn) => {
    btn.addEventListener("click", async () => {
      const endpoint = btn.getAttribute("data-copy-endpoint") || "";
      if (!endpoint) {
        return;
      }
      try {
        await navigator.clipboard.writeText(endpoint);
        btn.textContent = "Copied";
      } catch (_err) {
        btn.textContent = "Failed";
      }
      setTimeout(() => {
        btn.textContent = "Copy";
      }, 1200);
    });
  });
})();
