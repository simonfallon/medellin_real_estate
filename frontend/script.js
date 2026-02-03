import {
  fetchProperties,
  scrapeSource,
  fetchLocations,
} from "/static/modules/api.js";
import { filterProperties, sortProperties } from "/static/modules/filters.js";
import {
  renderProperties,
  setupBarrioFilter,
  initImageModal,
  setupCustomDropdown,
} from "/static/modules/dom.js";
import { openAllMapsModal } from "/static/modules/map.js";
import { debounce, showNotification } from "/static/utils.js";

console.log("Script.js loaded");

let allProperties = [];

document.addEventListener("DOMContentLoaded", () => {
  loadProperties();
  setupEventListeners();
  initImageModal();
});

async function loadProperties() {
  const grid = document.getElementById("propertiesGrid");
  // Minimal loading state if grid is empty, otherwise keep showing content while filtering
  if (grid.children.length === 0 || grid.querySelector(".loading-state")) {
    grid.innerHTML =
      '<div class="loading-state"><i class="fa-solid fa-circle-notch fa-spin"></i><p>Cargando propiedades...</p></div>';
  }

  try {
    // If we haven't fetched properties yet, fetch them.
    // Optimization: In a real app we might re-fetch only on 'Update' or explicit reload.
    if (allProperties.length === 0) {
      allProperties = await fetchProperties();
    }

    // Prepare filters object
    const filters = {
      priceMin:
        parseFloat(document.getElementById("filterPriceMin").value) || 0,
      priceMax:
        parseFloat(document.getElementById("filterPriceMax").value) || Infinity,
      areaMin: parseFloat(document.getElementById("filterAreaMin").value) || 0,
      areaMax:
        parseFloat(document.getElementById("filterAreaMax").value) || Infinity,
      bedsMin:
        parseFloat(document.getElementById("filterBedroomsMin").value) || 0,
      bedsMax:
        parseFloat(document.getElementById("filterBedroomsMax").value) ||
        Infinity,
      parkingMin:
        parseFloat(document.getElementById("filterParkingMin").value) || 0,
      selectedWebsite: document.getElementById("websiteSelect").value,
      // Logic for selected barrios is handled by dom.js triggering this via callback with values
      // But here we need to READ the current state.
      // Better: setupBarrioFilter updates a state variable or we query the DOM.
      // Let's query the DOM through a helper or just rely on the callback updating a closure variable?
      // script.js needs access to selectedBarrios.
      selectedBarrios: getCurrentSelectedBarrios(),
    };

    let filtered = filterProperties(allProperties, filters);

    const sortBy = document.getElementById("sortSelect").value;
    filtered = sortProperties(filtered, sortBy);

    renderProperties(filtered);
  } catch (error) {
    console.error("Error loading properties:", error);
    grid.innerHTML =
      '<div class="loading-state"><p>Error al cargar propiedades. Corrobora que el servidor backend esté corriendo.</p></div>';
  }
}

function getCurrentSelectedBarrios() {
  // Replicate logic or expose from DOM?
  // Since dom.js puts values in checkboxes, we can read them here.
  const dropdown = document.getElementById("barrioDropdown");
  const checked = Array.from(dropdown.querySelectorAll("input:checked")).map(
    (c) => c.value,
  );
  if (checked.includes("all") || checked.length === 0) return ["all"];
  return checked;
}

function setupEventListeners() {
  // Scrape Button
  const scrapeBtn = document.getElementById("scrapeBtn");
  if (scrapeBtn) {
    scrapeBtn.addEventListener("click", handleScrape);
  }

  // Input Filters
  [
    "filterPriceMin",
    "filterPriceMax",
    "filterAreaMin",
    "filterAreaMax",
    "filterBedroomsMin",
    "filterBedroomsMax",
    "filterParkingMin",
    "websiteSelect",
  ].forEach((id) => {
    const el = document.getElementById(id);
    if (el) {
      if (id === "websiteSelect") {
        // Native select listener removed, handled by custom dropdown
      } else {
        el.addEventListener("input", debounce(loadProperties, 500));
      }
    }
  });

  // Custom Dropdown
  setupCustomDropdown(() => loadProperties());

  // Sort
  const sortSelect = document.getElementById("sortSelect");
  if (sortSelect) {
    sortSelect.addEventListener("change", () => loadProperties());
  }

  // Map Button
  const mapBtn = document.getElementById("mapViewButton");
  if (mapBtn) {
    mapBtn.addEventListener("click", async () => {
      // We need locations. Using fetchLocations from API directly or reusing properties?
      // Original used /api/properties/locations.
      // Let's use the API method.
      showNotification("Cargando ubicaciones...");
      try {
        const locations = await fetchLocations();
        if (locations.length === 0) {
          showNotification("No hay datos GPS disponibles.");
          return;
        }
        openAllMapsModal(locations);
      } catch (e) {
        showNotification("Error al cargar mapa.");
      }
    });
  }

  // Barrio Filter
  setupBarrioFilter((selectedBarrios) => {
    // Callback when barrios change
    loadProperties();
  });
  // Theme Toggle
  setupTheme();
}

function setupTheme() {
  const themeBtn = document.getElementById("themeToggle");
  if (!themeBtn) return;

  const icon = themeBtn.querySelector("i");

  // Check saved theme
  const savedTheme = localStorage.getItem("theme");
  if (savedTheme === "light") {
    document.body.setAttribute("data-theme", "light");
    icon.classList.remove("fa-sun");
    icon.classList.add("fa-moon");
  }

  themeBtn.addEventListener("click", () => {
    const currentTheme = document.body.getAttribute("data-theme");
    if (currentTheme === "light") {
      // Switch to Dark
      document.body.removeAttribute("data-theme");
      localStorage.setItem("theme", "dark");
      icon.classList.remove("fa-moon");
      icon.classList.add("fa-sun");
    } else {
      // Switch to Light
      document.body.setAttribute("data-theme", "light");
      localStorage.setItem("theme", "light");
      icon.classList.remove("fa-sun");
      icon.classList.add("fa-moon");
    }
  });
}

async function handleScrape() {
  const btn = document.getElementById("scrapeBtn");
  const icon = btn.querySelector("i");
  const websiteSelect = document.getElementById("websiteSelect");
  const selectedWebsite = websiteSelect.value;
  const forceUpdate = document.getElementById("forceUpdate").checked;

  // When force update is checked, use filter inputs for scraping
  let scrapePriceMin = null;
  let scrapePriceMax = null;

  if (forceUpdate) {
    const filterPriceMinInput = document
      .getElementById("filterPriceMin")
      .value.trim();
    const filterPriceMaxInput = document
      .getElementById("filterPriceMax")
      .value.trim();

    // Convert to integers, treating empty strings as null
    scrapePriceMin = filterPriceMinInput
      ? parseInt(filterPriceMinInput, 10)
      : null;
    scrapePriceMax = filterPriceMaxInput
      ? parseInt(filterPriceMaxInput, 10)
      : null;

    // Validation only when force update is checked and prices are provided
    if (scrapePriceMin !== null && scrapePriceMax !== null) {
      if (scrapePriceMin < 0 || scrapePriceMax < 0) {
        showNotification("Los precios deben ser positivos");
        return;
      }
      if (scrapePriceMin >= scrapePriceMax) {
        showNotification("El precio mínimo debe ser menor que el máximo");
        return;
      }
      if (scrapePriceMax > 50000000) {
        showNotification("El precio máximo excede el límite razonable (50M)");
        return;
      }
    }

    // Debug: Log what we're sending
    console.log("Force update - sending prices:", {
      scrapePriceMin,
      scrapePriceMax,
    });
  }

  const grid = document.getElementById("propertiesGrid");

  btn.disabled = true;
  icon.classList.add("fa-spin");

  // Show loading state and hide current properties
  grid.innerHTML =
    '<div class="loading-state"><i class="fa-solid fa-circle-notch fa-spin"></i><p>Actualizando propiedades...</p></div>';

  if (forceUpdate) {
    showNotification("Iniciando escaneo masivo con actualización forzada...");
  } else {
    showNotification("Iniciando escaneo masivo...");
  }

  try {
    const data = await scrapeSource(
      selectedWebsite,
      forceUpdate,
      scrapePriceMin,
      scrapePriceMax,
    );

    if (data.cached) {
      const time = data.message.split("Last updated: ")[1] || "Reciente";
      showNotification(
        `Datos recientes cargados. Última actualización: ${time}`,
      );
    } else {
      showNotification(
        `Búsqueda completada. ${data.new_properties} nuevas propiedades.`,
      );
    }

    // Reload properties
    allProperties = []; // Force refresh
    loadProperties();
  } catch (e) {
    showNotification("Error en la búsqueda: " + e.message);
    // Reload properties even on error to show what we have
    allProperties = [];
    loadProperties();
  } finally {
    btn.disabled = false;
    icon.classList.remove("fa-spin");
  }
}

