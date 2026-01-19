
import { formatPrice, parseArea, getSourceName, getBarrioFromLocation, BARRIOS_LIST, showNotification } from '/static/utils.js?v=1';
import { openSingleMapModal, openAllMapsModal } from '/static/modules/map.js?v=1';
import { fetchLocations } from '/static/modules/api.js?v=1';

let modalImages = [];
let modalCurrentIndex = 0;

export function setupBarrioFilter(onFilterChange) {
    const btn = document.getElementById('barrioSelectBtn');
    const dropdown = document.getElementById('barrioDropdown');

    if (!btn || !dropdown) return;

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
            let currentSelected = getSelectedBarrios(checkboxes); // helper

            if (val === 'all') {
                if (e.target.checked) {
                    checkboxes.forEach(c => { if (c.value !== 'all') c.checked = false; });
                } else {
                    // Prevent unchecking all if it's the only one, or valid logic
                    if (currentSelected.length === 0) e.target.checked = true;
                }
            } else {
                const allCb = dropdown.querySelector('input[value="all"]');
                if (e.target.checked) allCb.checked = false;

                currentSelected = getSelectedBarrios(checkboxes);
                if (currentSelected.length === 0) {
                    allCb.checked = true;
                }
            }

            updateBarrioButtonText(getSelectedBarrios(checkboxes));
            onFilterChange(getSelectedBarrios(checkboxes));
        });
    });

    // Close dropdown when clicking outside
    document.addEventListener('click', (e) => {
        if (!e.target.closest('.multi-select-container')) {
            dropdown.classList.remove('show');
        }
    });
}

function getSelectedBarrios(checkboxes) {
    const selected = Array.from(checkboxes)
        .filter(c => c.checked)
        .map(c => c.value);

    // Logic fix: if 'all' is checked, return ['all']. If specific ones are checked, return them.
    // If 'all' and others are checked (shouldn't happen with above logic), prefer 'all' or cleanup.
    if (selected.includes('all')) return ['all'];
    return selected.length > 0 ? selected : ['all'];
}

function updateBarrioButtonText(selectedBarrios) {
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

export function updateResultsCount(count) {
    const banner = document.getElementById('resultsBanner');
    const countSpan = document.getElementById('resultsCount');
    let mapBtn = document.getElementById('mapViewButton');

    if (count > 0) {
        banner.classList.remove('hidden');
        countSpan.innerHTML = `<i class="fa-solid fa-sparkles"></i> Se encontraron <span style="color: white; font-weight: 700; margin: 0 4px;">${count}</span> propiedades excelentes`;

        // Ensure map button exists/is visible
        if (!mapBtn) {
            // Re-create if missing (edge case)
            // Ideally it should be in static HTML, but handling just in case
        } else {
            mapBtn.classList.remove('hidden');
            // Re-attach listener? No, it's static in HTML or attached in script.js
            // But we should attach it if we are managing it.
            // script.js will attach the listener globally to the ID.
        }
    } else {
        banner.classList.add('hidden');
    }
}

export function renderProperties(properties) {
    const grid = document.getElementById('propertiesGrid');
    updateResultsCount(properties.length);

    grid.innerHTML = '';

    if (properties.length === 0) {
        grid.innerHTML = '<div class="loading-state"><p>No se encontraron propiedades con estos filtros.</p></div>';
        return;
    }

    properties.forEach((p, index) => {
        const card = createPropertyCard(p, index);
        grid.appendChild(card);
    });
}

function createPropertyCard(p, index) {
    const card = document.createElement('div');
    card.className = 'property-card';
    card.style.animationDelay = `${index * 0.05}s`;

    let images = [];
    try {
        if (p.images) images = typeof p.images === 'string' ? JSON.parse(p.images) : p.images;
    } catch (e) { }

    if (!images || images.length === 0) {
        if (p.image_url) images = [p.image_url];
        else images = [`https://images.unsplash.com/photo-1560518883-ce09059eeffa?ixlib=rb-4.0.3&auto=format&fit=crop&w=500&q=60`];
    }

    const hasMultipleImages = images.length > 1;
    let locationBadge = getBarrioFromLocation(p.location);
    let normalizedSource = p.source === 'arrendamientosenvigadosa' ? 'arrendamientos_envigado' : p.source;
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
            mapBtn.addEventListener('click', async (e) => {
                e.stopPropagation();
                showNotification("Cargando mapa...");
                try {
                    const locations = await fetchLocations();
                    openSingleMapModal(p, locations);
                } catch (err) {
                    console.error("Error loading map locations:", err);
                    openSingleMapModal(p); // Fallback to showing just the single property
                }
            });
        }
    }

    card.addEventListener('click', (e) => {
        if (!e.target.closest('.card-image-wrapper') && !e.target.closest('.map-btn')) {
            window.open(p.link, '_blank');
        }
    });

    // Carousel Logic
    if (hasMultipleImages) {
        setupCardCarousel(card, images);
    } else {
        const imgEl = card.querySelector('.card-image');
        imgEl.addEventListener('click', (e) => {
            e.stopPropagation();
            openImageModal(images, 0);
        });
    }

    return card;
}

function setupCardCarousel(card, images) {
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
        e.preventDefault(); e.stopPropagation();
        currentIndex = (currentIndex - 1 + images.length) % images.length;
        updateImage();
    });

    nextBtn.addEventListener('click', (e) => {
        e.preventDefault(); e.stopPropagation();
        currentIndex = (currentIndex + 1) % images.length;
        updateImage();
    });

    imgEl.addEventListener('click', (e) => {
        e.stopPropagation();
        openImageModal(images, currentIndex);
    });
}

// Image Modal Logic
export function initImageModal() {
    const modal = document.getElementById('imageModal');
    const closeBtn = modal.querySelector('.modal-close');
    const prevBtn = modal.querySelector('.modal-nav.prev');
    const nextBtn = modal.querySelector('.modal-nav.next');

    closeBtn.addEventListener('click', closeImageModal);

    prevBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        modalCurrentIndex = (modalCurrentIndex - 1 + modalImages.length) % modalImages.length;
        updateModalImage();
    });

    nextBtn.addEventListener('click', (e) => {
        e.stopPropagation();
        modalCurrentIndex = (modalCurrentIndex + 1) % modalImages.length;
        updateModalImage();
    });

    modal.addEventListener('click', (e) => {
        if (e.target.id === 'imageModal' || e.target.classList.contains('modal-content')) {
            closeImageModal();
        }
    });

    document.addEventListener('keydown', (e) => {
        if (!modal.classList.contains('show')) return;
        if (e.key === 'Escape') closeImageModal();
        if (e.key === 'ArrowLeft') {
            modalCurrentIndex = (modalCurrentIndex - 1 + modalImages.length) % modalImages.length;
            updateModalImage();
        }
        if (e.key === 'ArrowRight') {
            modalCurrentIndex = (modalCurrentIndex + 1) % modalImages.length;
            updateModalImage();
        }
    });
}

function openImageModal(images, startIndex) {
    if (!images || images.length === 0) return;
    modalImages = images;
    modalCurrentIndex = startIndex;

    updateModalImage();

    const modal = document.getElementById('imageModal');
    modal.classList.remove('hidden');
    setTimeout(() => modal.classList.add('show'), 10);
    document.body.style.overflow = 'hidden';
}

function closeImageModal() {
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
