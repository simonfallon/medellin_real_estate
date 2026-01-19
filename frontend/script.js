const API_URL = '/api';

document.addEventListener('DOMContentLoaded', () => {
    loadProperties();
    setupEventListeners();
});

function setupEventListeners() {
    document.getElementById('scrapeBtn').addEventListener('click', triggerScrape);

    // Filters
    ['filterPriceMin', 'filterPriceMax', 'filterAreaMin', 'filterAreaMax', 'filterBedroomsMin', 'filterBedroomsMax', 'filterParkingMin', 'websiteSelect'].forEach(id => {
        const el = document.getElementById(id);
        if (id === 'websiteSelect') {
            el.addEventListener('change', () => loadProperties());
        } else if (el) {
            el.addEventListener('input', debounce(loadProperties, 500));
        }
    });

    // Sort listener
    const sortSelect = document.getElementById('sortSelect');
    if (sortSelect) {
        sortSelect.addEventListener('change', () => loadProperties());
    }

    // Modal listeners
    document.querySelector('.modal-close').addEventListener('click', closeModal);
    document.querySelector('.modal-nav.prev').addEventListener('click', (e) => {
        e.stopPropagation();
        prevModalImage();
    });
    document.querySelector('.modal-nav.next').addEventListener('click', (e) => {
        e.stopPropagation();
        nextModalImage();
    });
    document.getElementById('imageModal').addEventListener('click', (e) => {
        if (e.target.id === 'imageModal' || e.target.classList.contains('modal-content')) {
            closeModal();
        }
    });

    // Multi-select Barrios Logic
    setupBarrioFilter();

    // Close dropdowns when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.multi-select-container')) {
            document.getElementById('barrioDropdown').classList.remove('show');
        }
    });

    document.addEventListener('keydown', (e) => {
        if (!document.getElementById('imageModal').classList.contains('show')) return;
        if (e.key === 'Escape') closeModal();
        if (e.key === 'ArrowLeft') prevModalImage();
        if (e.key === 'ArrowRight') nextModalImage();
    });

    // Map Button Logic (Static HTML now)
    const mapBtn = document.getElementById('mapViewButton');
    if (mapBtn) {
        mapBtn.addEventListener('click', openAllMapsModal);
    }
}

// Standardized Barrios List
// Standardized Barrios List imported from utils.js

let selectedBarrios = ['all'];

function setupBarrioFilter() {
    const btn = document.getElementById('barrioSelectBtn');
    const dropdown = document.getElementById('barrioDropdown');
    const container = dropdown.querySelector('.dropdown-content');

    // Populate options
    BARRIOS_LIST.sort().forEach(barrio => {
        const label = document.createElement('label');
        label.className = 'checkbox-item';
        label.innerHTML = `<input type="checkbox" value="${barrio}"> ${barrio}`;
        dropdown.appendChild(label);
    });

    // Toggle dropdown
    btn.addEventListener('click', () => {
        dropdown.classList.toggle('show');
    });

    // Checkbox logic
    const checkboxes = dropdown.querySelectorAll('input[type="checkbox"]');
    checkboxes.forEach(cb => {
        cb.addEventListener('change', (e) => {
            const val = e.target.value;

            if (val === 'all') {
                if (e.target.checked) {
                    // Uncheck others
                    checkboxes.forEach(c => {
                        if (c.value !== 'all') c.checked = false;
                    });
                    selectedBarrios = ['all'];
                } else {
                    // Prevent unchecking 'All' if it's the only one
                    if (selectedBarrios.length === 1 && selectedBarrios.includes('all')) {
                        e.target.checked = true;
                    } else {
                        selectedBarrios = selectedBarrios.filter(b => b !== 'all');
                    }
                }
            } else {
                // If specific barrio checked, uncheck 'All'
                const allCb = dropdown.querySelector('input[value="all"]');
                allCb.checked = false;

                selectedBarrios = Array.from(checkboxes)
                    .filter(c => c.checked && c.value !== 'all')
                    .map(c => c.value);

                // If none selected, check 'All'
                if (selectedBarrios.length === 0) {
                    allCb.checked = true;
                    selectedBarrios = ['all'];
                } else {
                    // Ensure 'all' is removed from logic array
                    selectedBarrios = selectedBarrios.filter(b => b !== 'all');
                }
            }

            updateBarrioButtonText();
            loadProperties();
        });
    });
}

function updateBarrioButtonText() {
    const textSpan = document.getElementById('barrioSelectText');
    if (selectedBarrios.includes('all')) {
        textSpan.innerText = 'Todos';
    } else {
        if (selectedBarrios.length === 1) {
            textSpan.innerText = selectedBarrios[0];
        } else {
            textSpan.innerText = `${selectedBarrios.length} seleccionados`;
        }
    }
}


async function loadProperties() {
    const grid = document.getElementById('propertiesGrid');
    grid.innerHTML = '<div class="loading-state"><i class="fa-solid fa-circle-notch fa-spin"></i><p>Cargando propiedades...</p></div>';

    try {
        const response = await fetch(`${API_URL}/properties?limit=200`);
        const properties = await response.json();

        // Client-side filtering
        let filtered = applyFilters(properties);

        // Client-side sorting
        filtered = sortProperties(filtered);

        renderProperties(filtered);
    } catch (error) {
        console.error('Error loading properties:', error);
        grid.innerHTML = '<div class="loading-state"><p>Error al cargar propiedades. Intenta nuevamente.</p></div>';
    }
}

function sortProperties(properties) {
    const sortBy = document.getElementById('sortSelect').value;

    return properties.sort((a, b) => {
        switch (sortBy) {
            case 'price_asc':
                return parsePrice(a.price) - parsePrice(b.price);
            case 'price_desc':
                return parsePrice(b.price) - parsePrice(a.price);
            case 'area_asc':
                return parseArea(a.area) - parseArea(b.area);
            case 'area_desc':
                return parseArea(b.area) - parseArea(a.area);
            case 'created_asc':
                return new Date(a.created_at) - new Date(b.created_at);
            case 'barrio_asc':
                return getBarrioFromLocation(a.location).localeCompare(getBarrioFromLocation(b.location));
            case 'barrio_desc':
                return getBarrioFromLocation(b.location).localeCompare(getBarrioFromLocation(a.location));
            case 'created_desc':
            default:
                return new Date(b.created_at) - new Date(a.created_at);
        }
    });
}

function applyFilters(properties) {
    const priceMin = parseFloat(document.getElementById('filterPriceMin').value) || 0;
    const priceMax = parseFloat(document.getElementById('filterPriceMax').value) || Infinity;
    const areaMin = parseFloat(document.getElementById('filterAreaMin').value) || 0;
    const areaMax = parseFloat(document.getElementById('filterAreaMax').value) || Infinity;
    const bedsMin = parseFloat(document.getElementById('filterBedroomsMin').value) || 0;
    const bedsMax = parseFloat(document.getElementById('filterBedroomsMax').value) || Infinity;
    const parkingMin = parseFloat(document.getElementById('filterParkingMin').value) || 0;
    const selectedWebsite = document.getElementById('websiteSelect').value;

    const filtered = properties.filter(p => {
        // Parse property values
        const pPrice = parsePrice(p.price);
        const pArea = parseArea(p.area);
        const pBeds = parseInt(p.bedrooms) || 0;
        const pParking = parseInt(p.parking) || 0;

        const matchesPrice = pPrice >= priceMin && pPrice <= priceMax;
        const matchesArea = pArea >= areaMin && pArea <= areaMax;
        const matchesBeds = pBeds >= bedsMin && pBeds <= bedsMax;
        const matchesParking = pParking >= parkingMin;

        // Website Source filtering
        let matchesSource = true;
        if (selectedWebsite && selectedWebsite !== 'all') {
            const pSource = (p.source || '').toLowerCase().trim();
            const selected = selectedWebsite.toLowerCase().trim();

            if (selected === 'arrendamientos_envigado') {
                matchesSource = (pSource === 'arrendamientos_envigado' || pSource === 'arrendamientosenvigadosa');
            } else {
                matchesSource = (pSource === selected);
            }
        }

        // Barrio Filtering
        let matchesBarrio = true;
        if (selectedBarrios && !selectedBarrios.includes('all')) {
            const pLoc = (p.location || '').toLowerCase().trim();
            // Check if any selected barrio matches the location partially or fully
            // Since we standardized keys, we expect good matches, but let's be flexible
            matchesBarrio = selectedBarrios.some(b => pLoc.includes(b.toLowerCase()));
        }

        return matchesPrice && matchesArea && matchesBeds && matchesParking && matchesSource && matchesBarrio;
    });

    console.log(`Filtering complete: Source="${selectedWebsite}", Before=${properties.length}, After=${filtered.length}`);
    return filtered;
}

function renderProperties(properties) {
    const grid = document.getElementById('propertiesGrid');

    // Update banner with count
    updateResultsCount(properties.length);

    grid.innerHTML = '';

    if (properties.length === 0) {
        grid.innerHTML = '<div class="loading-state"><p>No se encontraron propiedades con estos filtros.</p></div>';
        return;
    }

    properties.forEach((p, index) => {
        const card = document.createElement('div');
        card.className = 'property-card';
        card.style.animationDelay = `${index * 0.05}s`;

        // Parse images
        let images = [];
        try {
            if (p.images) {
                images = JSON.parse(p.images);
            }
        } catch (e) {
            console.error("Error parsing images JSON", e);
        }

        if (images.length === 0 && p.image_url) {
            images = [p.image_url];
        }
        if (images.length === 0) {
            const fallback = `https://images.unsplash.com/photo-1560518883-ce09059eeffa?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60`;
            images = [fallback];
        }

        const hasMultipleImages = images.length > 1;

        // Extract location badge
        let locationBadge = getBarrioFromLocation(p.location);

        let normalizedSource = p.source;
        if (p.source === 'arrendamientosenvigadosa') normalizedSource = 'arrendamientos_envigado';


        const sourceName = getSourceName(p.source);

        card.innerHTML = `
            <div class="card-image-wrapper">
                ${locationBadge ? `<div class="card-badge">${locationBadge}</div>` : ''}
                <img class="card-image" src="${images[0]}" alt="${p.code || p.title}" loading="lazy">
                ${hasMultipleImages ? `
                    <button class="carousel-btn prev" aria-label="Anterior"><i class="fa-solid fa-chevron-left"></i></button>
                    <button class="carousel-btn next" aria-label="Siguiente"><i class="fa-solid fa-chevron-right"></i></button>
                    <div class="image-counter" style="position: absolute; bottom: 10px; right: 10px; background: rgba(0,0,0,0.6); color: white; padding: 2px 8px; border-radius: 10px; font-size: 0.7rem; z-index: 20;">1/${images.length}</div>
                ` : ''}
            </div>
            <div class="card-content">
                <div class="card-price">${formatPrice(p.price)}</div>
                <div class="card-title">
                    <img class="source-icon" src="/static/assets/images/icons/${normalizedSource}.png" alt="${sourceName}" onerror="this.style.display='none'">
                    ${sourceName}
                </div>
                <div class="card-code">
                    <div style="display: flex; align-items: center; gap: 0.4rem;"><i class="fa-solid fa-hashtag"></i> ${p.code || '--'}</div>
                    ${(p.latitude && p.longitude) ? `
                    <button class="map-btn" style="background: transparent; border: 1px solid var(--primary); color: var(--primary); padding: 5px 15px; border-radius: 8px; cursor: pointer; font-size: 0.9rem; display: inline-flex; align-items: center; gap: 5px; transition: all 0.2s;">
                        <i class="fa-solid fa-map-location-dot"></i> Ver Ubicacion
                    </button>
                    ` : ''}
                </div>
                
                <div class="card-features">
                    <div class="feature-item" title="Área"><i class="fa-solid fa-ruler-combined"></i> ${parseArea(p.area) || '--'} m²</div>
                    <div class="feature-item" title="Habitaciones"><i class="fa-solid fa-bed"></i> ${p.bedrooms || '--'}</div>
                    <div class="feature-item" title="Baños"><i class="fa-solid fa-bath"></i> ${p.bathrooms || '--'}</div>
                    <div class="feature-item" title="Parqueaderos"><i class="fa-solid fa-car"></i> ${p.parking || '--'}</div>
                </div>
            </div>
        `;

        // Map Button Logic
        if (p.latitude && p.longitude) {
            const mapBtn = card.querySelector('.map-btn');
            if (mapBtn) {
                mapBtn.addEventListener('click', (e) => {
                    e.stopPropagation();
                    const barrio = getBarrioFromLocation(p.location);
                    openMapModal(p.latitude, p.longitude, sourceName, barrio);
                });
            }
        }

        card.addEventListener('click', (e) => {
            if (!e.target.closest('.card-image-wrapper')) {
                window.open(p.link, '_blank');
            }
        });

        // Carousel Logic
        if (hasMultipleImages) {
            const imgEl = card.querySelector('.card-image');
            const prevBtn = card.querySelector('.carousel-btn.prev');
            const nextBtn = card.querySelector('.carousel-btn.next');
            const counterEl = card.querySelector('.image-counter');
            let currentIndex = 0;

            const updateImage = () => {
                imgEl.src = images[currentIndex];
                counterEl.innerText = `${currentIndex + 1}/${images.length}`;
            };

            prevBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                currentIndex = (currentIndex - 1 + images.length) % images.length;
                updateImage();
            });

            nextBtn.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                currentIndex = (currentIndex + 1) % images.length;
                updateImage();
            });

            // Open modal logic for multiple images
            imgEl.addEventListener('click', (e) => {
                e.stopPropagation(); // Avoid card click
                openModal(images, currentIndex);
            });
        } else {
            // Open modal logic for single image
            const imgEl = card.querySelector('.card-image');
            imgEl.addEventListener('click', (e) => {
                e.stopPropagation(); // Avoid card click
                openModal(images, 0);
            });
        }

        grid.appendChild(card);
    });
}

// Modal State
let modalImages = [];
let modalCurrentIndex = 0;

function openModal(images, startIndex) {
    if (!images || images.length === 0) return;
    modalImages = images;
    modalCurrentIndex = startIndex;

    updateModalImage();

    const modal = document.getElementById('imageModal');
    modal.classList.remove('hidden');
    // small delay to allow transition
    setTimeout(() => modal.classList.add('show'), 10);
    document.body.style.overflow = 'hidden'; // Prevent scrolling
}

function closeModal() {
    const modal = document.getElementById('imageModal');
    modal.classList.remove('show');
    setTimeout(() => modal.classList.add('hidden'), 300);
    document.body.style.overflow = '';
}

function updateModalImage() {
    const img = document.getElementById('modalImage');
    const counter = document.querySelector('.modal-counter');

    img.src = modalImages[modalCurrentIndex];
    counter.innerText = `${modalCurrentIndex + 1}/${modalImages.length}`;
}

function nextModalImage() {
    modalCurrentIndex = (modalCurrentIndex + 1) % modalImages.length;
    updateModalImage();
}

function prevModalImage() {
    modalCurrentIndex = (modalCurrentIndex - 1 + modalImages.length) % modalImages.length;
    updateModalImage();
}


async function triggerScrape() {
    const btn = document.getElementById('scrapeBtn');
    const icon = btn.querySelector('i');
    const websiteSelect = document.getElementById('websiteSelect');
    const selectedWebsite = websiteSelect.value;

    btn.disabled = true;
    icon.classList.add('fa-spin');

    let endpoint = '/api/scrape';
    let body = {};
    let method = 'POST';

    if (selectedWebsite === 'arrendamientos_envigado' || selectedWebsite === 'alberto_alvarez' || selectedWebsite === 'proteger' || selectedWebsite === 'arrendamientos_las_vegas' || selectedWebsite === 'all') {
        const forceUpdate = document.getElementById('forceUpdate').checked;
        endpoint = `/api/scrape/batch?source=${selectedWebsite}&force=${forceUpdate}`;
        if (forceUpdate) {
            showNotification('Iniciando escaneo masivo con actualización forzada...');
        } else {
            showNotification('Iniciando escaneo masivo (usando caché si es reciente)...');
        }
    } else {
        // Fallback or generic URL input logic if we re-enable it
        showNotification('Sitio no soportado.');
        btn.disabled = false;
        icon.classList.remove('fa-spin');
        return;
    }

    try {
        const res = await fetch(endpoint, {
            method: method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: Object.keys(body).length > 0 ? JSON.stringify(body) : undefined
        });
        const data = await res.json();

        if (res.ok) {
            if (data.cached) {
                showNotification(`Datos recientes cargados. Última actualización: ${data.message.split('Last updated: ')[1] || 'Reciente'}`);
            } else {
                showNotification(`Búsqueda completada. ${data.new_properties} nuevas propiedades encontradas.`);
            }
            loadProperties();
        } else {
            throw new Error(data.detail);
        }
    } catch (e) {
        showNotification('Error en la búsqueda: ' + e.message);
    } finally {
        btn.disabled = false;
        icon.classList.remove('fa-spin');
    }
}

// Helpers - now imported from utils.js

function updateResultsCount(count) {
    const banner = document.getElementById('resultsBanner');
    const countSpan = document.getElementById('resultsCount');
    let mapBtn = document.getElementById('mapViewButton');

    if (count > 0) {
        banner.classList.remove('hidden');
        countSpan.innerHTML = `<i class="fa-solid fa-sparkles"></i> Se encontraron <span style="color: white; font-weight: 700; margin: 0 4px;">${count}</span> propiedades excelentes`;

        // Robustness: If mapBtn is missing (e.g. old HTML cache), create it dynamically
        if (!mapBtn) {
            console.warn('Map button not found in DOM, creating dynamically...');
            mapBtn = document.createElement('button');
            mapBtn.id = 'mapViewButton';
            mapBtn.className = 'premium-btn';
            mapBtn.style.marginLeft = '1rem';
            mapBtn.style.padding = '0.4rem 1rem';
            mapBtn.style.fontSize = '0.9rem';
            mapBtn.innerHTML = '<i class="fa-solid fa-map"></i> Ver ubicaciones en mapa';
            mapBtn.onclick = openAllMapsModal;
            // Append as sibling to countSpan
            if (countSpan.parentNode) {
                countSpan.parentNode.appendChild(mapBtn);
            }
        } else {
            mapBtn.onclick = openAllMapsModal;
            // Ensure it has text content if it was empty
            if (mapBtn.innerHTML.trim() === "") {
                mapBtn.innerHTML = '<i class="fa-solid fa-map"></i> Ver ubicaciones en mapa';
            }
        }

        if (mapBtn) {
            mapBtn.classList.remove('hidden');
            console.log('Map button should be visible now.');
        }
    } else {
        banner.classList.add('hidden');
        if (mapBtn) mapBtn.classList.add('hidden');
    }
}

// Make global for inline access if needed
window.openAllMapsModal = openAllMapsModal;

async function openAllMapsModal() {
    try {
        showNotification('Cargando ubicaciones...');
        const res = await fetch(`${API_URL}/properties/locations`);
        if (!res.ok) throw new Error('Error fetching locations');
        const locations = await res.json();

        if (locations.length === 0) {
            showNotification('No hay ubicaciones con GPS disponibles.');
            return;
        }

        const modal = document.getElementById('mapModal');
        const mapTitle = document.getElementById('mapTitle');
        mapTitle.innerText = `Mapa de Propiedades (${locations.length})`;

        modal.classList.remove('hidden');
        setTimeout(() => modal.classList.add('show'), 10);
        document.body.style.overflow = 'hidden';

        // Initialize map
        if (!map) {
            if (typeof L === 'undefined') {
                console.error('Leaflet is not loaded');
                return;
            }
            // Default center Medellin
            map = L.map('mapContainer').setView([6.2442, -75.5812], 12);

            L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
                attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
                subdomains: 'abcd',
                maxZoom: 20
            }).addTo(map);
        } else {
            setTimeout(() => map.invalidateSize(), 300);
        }

        // Clear existing markers
        map.eachLayer((layer) => {
            if (layer instanceof L.Marker) {
                map.removeLayer(layer);
            }
        });

        // Add markers
        const markers = L.featureGroup();
        locations.forEach(p => {
            let normalizedSource = p.source;
            if (p.source === 'arrendamientosenvigadosa') normalizedSource = 'arrendamientos_envigado';

            let images = [];
            try {
                if (p.images) {
                    images = JSON.parse(p.images);
                }
            } catch (e) { console.error("Error parsing images for map", e); }

            if (images.length === 0 && p.image_url) images = [p.image_url];
            if (images.length === 0) images = ['/static/assets/images/sherlock_homes.png'];

            const hasMultiple = images.length > 1;
            const uniqueId = `popup-carousel-${p.id || Math.random().toString(36).substr(2, 9)}`;

            const marker = L.marker([p.latitude, p.longitude]);

            const popupContent = `
                    <div style="min-width: 300px; font-family: 'Plus Jakarta Sans', sans-serif;">
                        <div style="width: 100%; height: 160px; overflow: hidden; border-radius: 8px 8px 0 0; margin-bottom: 10px; background: #eee; position: relative;">
                            <img id="${uniqueId}-img" src="${images[0]}" style="width: 100%; height: 100%; object-fit: cover;" onerror="this.src='/static/assets/images/sherlock_homes.png'">
                            ${hasMultiple ? `
                                <button onclick="window.prevPopupImage('${uniqueId}', ${JSON.stringify(images).replace(/"/g, '&quot;')})" style="position: absolute; left: 5px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.5); color: white; border: none; width: 24px; height: 24px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center;"><i class="fa-solid fa-chevron-left" style="font-size: 0.7em;"></i></button>
                                <button onclick="window.nextPopupImage('${uniqueId}', ${JSON.stringify(images).replace(/"/g, '&quot;')})" style="position: absolute; right: 5px; top: 50%; transform: translateY(-50%); background: rgba(0,0,0,0.5); color: white; border: none; width: 24px; height: 24px; border-radius: 50%; cursor: pointer; display: flex; align-items: center; justify-content: center;"><i class="fa-solid fa-chevron-right" style="font-size: 0.7em;"></i></button>
                                <div id="${uniqueId}-count" style="position: absolute; bottom: 8px; right: 8px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: 600;">1/${images.length}</div>
                            ` : `
                                <div style="position: absolute; top: 8px; right: 8px; background: rgba(0,0,0,0.7); color: white; padding: 2px 6px; border-radius: 4px; font-size: 0.75em; font-weight: 600;">${p.code || ''}</div>
                            `}
                        </div>
                        <div style="padding: 0 4px;">
                            <div style="margin-bottom: 4px; font-weight: 800; color: #2ecc71; font-size: 1.25em;">${formatPrice(p.price)}</div>
                            <div style="margin-bottom: 12px; font-size: 0.95em; color: #555; display: flex; align-items: center; gap: 6px;">
                                <i class="fa-solid fa-location-dot" style="color: #7c8db5;"></i> ${p.location || 'Ubicación desconocida'}
                            </div>

                            <div style="display: flex; justify-content: space-between; align-items: center; border-top: 1px solid #eee; padding-top: 10px;">
                                <div style="font-size: 0.9em; display: flex; align-items: center; gap: 6px; color: #444; font-weight: 500;">
                                    <img src="/static/assets/images/icons/${normalizedSource}.png" alt="icon" style="width: 20px; height: 20px; object-fit: contain; border-radius: 4px;" onerror="this.style.display='none'">
                                    ${getSourceName(p.source)}
                                </div>
                                <a href="${p.link}" target="_blank" style="background: #1a1f3a; color: white; padding: 8px 16px; text-decoration: none; border-radius: 8px; font-size: 0.85em; font-weight: 600; transition: all 0.2s; box-shadow: 0 2px 5px rgba(0,0,0,0.1);">
                                    Ver Inmueble <i class="fa-solid fa-arrow-right" style="margin-left: 4px; font-size: 0.8em;"></i>
                                </a>
                            </div>
                        </div>
                    </div>
                `;

            marker.bindPopup(popupContent);
            markers.addLayer(marker);
        });

        markers.addTo(map);

        // Fit bounds to show all markers
        try {
            map.fitBounds(markers.getBounds(), { padding: [50, 50] });
        } catch (e) {
            console.log("Error fitting bounds", e);
            map.setView([6.2442, -75.5812], 12);
        }

        // Close logic
        const closeBtn = modal.querySelector('.modal-close');
        const closeHandler = () => {
            const modal = document.getElementById('mapModal');
            modal.classList.remove('show');
            setTimeout(() => modal.classList.add('hidden'), 300);
            document.body.style.overflow = '';
        };
        closeBtn.onclick = closeHandler;
        modal.onclick = (e) => {
            if (e.target.id === 'mapModal') closeHandler();
        }

    } catch (e) {
        console.error("Error opening map", e);
        showNotification('Error al cargar el mapa.');
    }
}


// Map Modal Logic
let map = null;
let marker = null;

function openMapModal(lat, lng, sourceName, locationName) {
    const modal = document.getElementById('mapModal');
    const mapTitle = document.getElementById('mapTitle');
    mapTitle.innerText = sourceName || 'Ubicación';

    modal.classList.remove('hidden');
    setTimeout(() => modal.classList.add('show'), 10);
    document.body.style.overflow = 'hidden';

    // Initialize map if not already done, or invalidate size
    if (!map) {
        if (typeof L === 'undefined') {
            console.error('Leaflet is not loaded');
            return;
        }
        map = L.map('mapContainer').setView([lat, lng], 16);

        // CartoDB Positron (Light colored map)
        L.tileLayer('https://{s}.basemaps.cartocdn.com/light_all/{z}/{x}/{y}{r}.png', {
            attribution: '&copy; <a href="https://www.openstreetmap.org/copyright">OpenStreetMap</a> contributors &copy; <a href="https://carto.com/attributions">CARTO</a>',
            subdomains: 'abcd',
            maxZoom: 20
        }).addTo(map);
    } else {
        map.setView([lat, lng], 16);
        setTimeout(() => map.invalidateSize(), 300); // Important for modal resize
    }

    if (marker) map.removeLayer(marker);

    const popupContent = locationName ? `Apartamento en ${locationName}` : 'Ubicación Exacta';
    marker = L.marker([lat, lng]).addTo(map)
        .bindPopup(popupContent)
        .openPopup();

    // Close logic
    const closeBtn = modal.querySelector('.modal-close');
    const closeHandler = () => {
        const modal = document.getElementById('mapModal');
        modal.classList.remove('show');
        setTimeout(() => modal.classList.add('hidden'), 300);
        document.body.style.overflow = '';
    };
    closeBtn.onclick = closeHandler;
}


// Popup Carousel Logic
window.popupStates = {};

window.nextPopupImage = function (id, images) {
    if (!window.popupStates[id]) window.popupStates[id] = 0;
    window.popupStates[id] = (window.popupStates[id] + 1) % images.length;
    updatePopupImage(id, images);
};

window.prevPopupImage = function (id, images) {
    if (!window.popupStates[id]) window.popupStates[id] = 0;
    window.popupStates[id] = (window.popupStates[id] - 1 + images.length) % images.length;
    updatePopupImage(id, images);
};

function updatePopupImage(id, images) {
    const imgElement = document.getElementById(`${id}-img`);
    const countElement = document.getElementById(`${id}-count`);
    const index = window.popupStates[id];

    if (imgElement) imgElement.src = images[index];
    if (countElement) countElement.innerText = `${index + 1}/${images.length}`;
}

