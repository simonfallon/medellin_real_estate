import {
  getSourceName,
  formatPrice,
  getBarrioFromLocation,
} from "/static/utils.js?v=1";

let map = null;
let marker = null;

// Expose popup navigation globally because event handlers in HTML strings need global access
window.popupStates = {};

window.nextPopupImage = function (id, images) {
  if (!window.popupStates[id]) window.popupStates[id] = 0;
  window.popupStates[id] = (window.popupStates[id] + 1) % images.length;
  updatePopupImage(id, images);
};

window.prevPopupImage = function (id, images) {
  if (!window.popupStates[id]) window.popupStates[id] = 0;
  window.popupStates[id] =
    (window.popupStates[id] - 1 + images.length) % images.length;
  updatePopupImage(id, images);
};

function updatePopupImage(id, images) {
  const imgElement = document.getElementById(`${id}-img`);
  const countElement = document.getElementById(`${id}-count`);
  const index = window.popupStates[id];

  if (imgElement) imgElement.src = images[index];
  if (countElement) countElement.innerText = `${index + 1}/${images.length}`;
}

export function openAllMapsModal(locations) {
  const modal = document.getElementById("mapModal");
  const mapTitle = document.getElementById("mapTitle");
  mapTitle.innerText = `Mapa de Propiedades (${locations.length})`;

  modal.classList.remove("hidden");
  setTimeout(() => modal.classList.add("show"), 10);
  document.body.style.overflow = "hidden";

  // Initialize map
  initMap([6.2442, -75.5812], 12);

  // Add markers
  const markers = L.featureGroup();
  locations.forEach((p) => {
    const marker = L.marker([p.latitude, p.longitude]);
    marker.bindPopup(getMapPopupContent(p));
    markers.addLayer(marker);
  });

  markers.addTo(map);

  try {
    map.fitBounds(markers.getBounds(), { padding: [50, 50] });
  } catch (e) {
    map.setView([6.2442, -75.5812], 12);
  }

  setupModalClose(modal);
}

export function openSingleMapModal(p, allLocations = []) {
  const modal = document.getElementById("mapModal");
  const mapTitle = document.getElementById("mapTitle");
  const sourceName = getSourceName(p.source);
  mapTitle.innerText = sourceName || "Ubicación";

  modal.classList.remove("hidden");
  setTimeout(() => modal.classList.add("show"), 10);
  document.body.style.overflow = "hidden";

  // Highlight marker icon (Red)
  const redIcon = new L.Icon({
    iconUrl:
      "https://raw.githubusercontent.com/pointhi/leaflet-color-markers/master/img/marker-icon-2x-red.png",
    shadowUrl:
      "https://cdnjs.cloudflare.com/ajax/libs/leaflet/0.7.7/images/marker-shadow.png",
    iconSize: [25, 41],
    iconAnchor: [12, 41],
    popupAnchor: [1, -34],
    shadowSize: [41, 41],
  });

  initMap([p.latitude, p.longitude], 16);

  // Context markers
  if (allLocations.length > 0) {
    const markers = L.featureGroup();
    allLocations.forEach((loc) => {
      const isTarget =
        (loc.id && loc.id === p.id) ||
        (loc.latitude === p.latitude && loc.longitude === p.longitude);
      if (isTarget) return;

      const m = L.marker([loc.latitude, loc.longitude]);
      m.bindPopup(getMapPopupContent(loc));
      markers.addLayer(m);
    });
    markers.addTo(map);
  }

  // Target marker
  marker = L.marker([p.latitude, p.longitude], { icon: redIcon })
    .addTo(map)
    .bindPopup(getMapPopupContent(p));

  setupModalClose(modal);
}

function initMap(center, zoom) {
  if (!map) {
    if (typeof L === "undefined") {
      console.error("Leaflet is not loaded");
      return;
    }
    map = L.map("mapContainer").setView(center, zoom);

    L.tileLayer(
      "https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png",
      {
        attribution:
          '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
        subdomains: "abcd",
        maxZoom: 20,
      },
    ).addTo(map);
  } else {
    map.setView(center, zoom);
    // Clear layers
    map.eachLayer((layer) => {
      if (layer instanceof L.Marker) {
        map.removeLayer(layer);
      }
    });
    setTimeout(() => map.invalidateSize(), 300);
  }
}

function setupModalClose(modal) {
  const closeBtn = modal.querySelector(".modal-close");
  const closeHandler = () => {
    modal.classList.remove("show");
    setTimeout(() => modal.classList.add("hidden"), 300);
    document.body.style.overflow = "";
  };
  closeBtn.onclick = closeHandler;
  modal.onclick = (e) => {
    if (e.target.id === "mapModal") closeHandler();
  };
}

function getMapPopupContent(p) {
  let normalizedSource = p.source;
  if (p.source === "arrendamientosenvigadosa")
    normalizedSource = "arrendamientos_envigado";

  const sourceName = getSourceName(p.source);

  let images = [];
  try {
    if (p.images) {
      images = typeof p.images === "string" ? JSON.parse(p.images) : p.images;
    }
  } catch (e) {
    console.error("Error parsing images for map", e);
  }

  if (!images || images.length === 0) {
    if (p.image_url) images = [p.image_url];
    else images = ["/static/assets/images/sherlock_homes.png"];
  }

  const hasMultiple = images.length > 1;
  const uniqueId = `popup-carousel-${p.id || Math.random().toString(36).substr(2, 9)}`;
  const imagesJson = JSON.stringify(images).replace(/"/g, "&quot;");

  return `
        <div style="min-width: 300px; font-family: 'Plus Jakarta Sans', sans-serif;">
            <div style="width: 100%; height: 160px; overflow: hidden; border-radius: 8px 8px 0 0; margin-bottom: 10px; background: #eee; position: relative;">
                <img id="${uniqueId}-img" src="${images[0]}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='/static/assets/images/sherlock_homes.png'">
                ${
                  hasMultiple
                    ? `
                    <button onclick="window.prevPopupImage('${uniqueId}', ${imagesJson})" style="position: absolute; left: 5px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.5); color: white; border: none; width: 24px; height: 24px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center;"><i class="fa-solid fa-chevron-left" style="font-size: 0.7em;"></i></button>
                    <button onclick="window.nextPopupImage('${uniqueId}', ${imagesJson})" style="position: absolute; right: 5px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.5); color: white; border: none; width: 24px; height: 24px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center;"><i class="fa-solid fa-chevron-right" style="font-size: 0.7em;"></i></button>
                    <div id="${uniqueId}-count" style="position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: 600;">1/${images.length}</div>
                `
                    : `
                    <div style="position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: 600;">${p.code || ""}</div>
                `
                }
            </div>
            <div style="padding: 0 4px;">
                <div style="margin-bottom: 4px; font-weight: 800; color: #2ecc71; font-size: 1.25em;">${formatPrice(p.price)}</div>
                <div style="margin-bottom: 12px; font-size: 0.95em; color: #555; display: flex; align-items: center; gap: 6px;">
                    <i class="fa-solid fa-location-dot" style="color: #7c8db5;"></i> ${p.location || "Ubicación desconocida"}
                </div>

                <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #eee; padding-top: 10px;">
                    <div style="font-size: 0.9em; display: flex; align-items: center; gap: 6px; color: #444; font-weight: 500;">
                        <img src="/static/assets/images/icons/${normalizedSource}.png" alt="icon" style="width: 20px; height: 20px; object-fit: contain; border-radius: 4px;" onerror="this.style.display='none'">
                        ${sourceName}
                    </div>
                    <a href="${p.link}" target="_blank" style="background: #1a1f3a; color: white; padding: 8px 16px; text-decoration: none; border-radius: 8px; font-size: 0.85em; font-weight: 600; transition: all 0.2s; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                        Ver Inmueble <i class="fa-solid fa-arrow-right" style="margin-left: 4px; font-size: 0.8em;"></i>
                    </a>
                </div>
            </div>
        </div>
    `;
}
