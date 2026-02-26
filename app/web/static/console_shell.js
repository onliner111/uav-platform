(function () {
  const searchInput = document.getElementById("global-search");
  const navItems = Array.from(document.querySelectorAll("[data-nav-item]"));
  const favButtons = Array.from(document.querySelectorAll("[data-fav-toggle]"));
  const quickAccess = document.getElementById("quick-access");
  const favStorageKey = "uav-console-favorites-v1";

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
})();
