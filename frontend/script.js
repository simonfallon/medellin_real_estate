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
    document.addEventListener('keydown', (e) => {
        if (!document.getElementById('imageModal').classList.contains('show')) return;
        if (e.key === 'Escape') closeModal();
        if (e.key === 'ArrowLeft') prevModalImage();
        if (e.key === 'ArrowRight') nextModalImage();
    });
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

        return matchesPrice && matchesArea && matchesBeds && matchesParking && matchesSource;
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
        let locationBadge = '';
        if (p.location) {
            const parts = p.location.split(/,| - /).map(s => s.trim());
            const specificParts = parts.filter(part => {
                const lower = part.toLowerCase();
                return lower !== 'medellin' &&
                    lower !== 'medellín' &&
                    lower !== 'envigado' &&
                    lower !== 'antioquia' &&
                    lower !== 'colombia';
            });
            if (specificParts.length > 0) {
                locationBadge = specificParts[0];
            }
        }

        const sourceMap = {
            'alberto_alvarez': 'Alberto Álvarez',
            'arrendamientos_envigado': 'Arrendamientos Envigado',
            'arrendamientosenvigadosa': 'Arrendamientos Envigado'
        };
        const sourceName = sourceMap[p.source] || p.source || 'Inmobiliaria';

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
                <div class="card-title">${sourceName}</div>
                <div class="card-code">
                    <i class="fa-solid fa-hashtag"></i> ${p.code || '--'}
                </div>
                
                <div class="card-features">
                    <div class="feature-item" title="Área"><i class="fa-solid fa-ruler-combined"></i> ${parseArea(p.area) || '--'} m²</div>
                    <div class="feature-item" title="Habitaciones"><i class="fa-solid fa-bed"></i> ${p.bedrooms || '--'}</div>
                    <div class="feature-item" title="Baños"><i class="fa-solid fa-bath"></i> ${p.bathrooms || '--'}</div>
                    <div class="feature-item" title="Parqueaderos"><i class="fa-solid fa-car"></i> ${p.parking || '--'}</div>
                </div>
            </div>
        `;

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

    if (selectedWebsite === 'arrendamientos_envigado' || selectedWebsite === 'alberto_alvarez' || selectedWebsite === 'all') {
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

// Helpers
function updateResultsCount(count) {
    const banner = document.getElementById('resultsBanner');
    const countSpan = document.getElementById('resultsCount');

    if (count > 0) {
        banner.classList.remove('hidden');
        countSpan.innerHTML = `<i class="fa-solid fa-sparkles"></i> Se encontraron <span style="color: white; font-weight: 700; margin: 0 4px;">${count}</span> propiedades excelentes`;
    } else {
        banner.classList.add('hidden');
    }
}

function formatPrice(price) {
    const value = parsePrice(price);
    // Format with ' as thousand separator
    return '$' + value.toString().replace(/\B(?=(\d{3})+(?!\d))/g, "'");
}

function parsePrice(str) {
    if (typeof str === 'number') return str;
    if (!str) return 0;
    // Remove non-numeric except dots if used as thousands separator
    // Assuming format $1.200.000 -> 1200000
    const clean = str.toString().replace(/[^\d]/g, '');
    return parseInt(clean) || 0;
}

function parseArea(str) {
    if (!str) return 0;
    // Allow digits and dots for decimals (e.g. "72.00 m2")
    const clean = str.toString().replace(/[^\d.]/g, '');
    const num = parseFloat(clean) || 0;
    return Math.round(num);
}

function showNotification(msg) {
    const notif = document.getElementById('notification');
    document.getElementById('notifMessage').innerText = msg;
    notif.classList.remove('hidden');
    notif.classList.add('show');

    setTimeout(() => {
        notif.classList.remove('show');
        setTimeout(() => notif.classList.add('hidden'), 300);
    }, 5000);
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}
