// Utility Functions

function getBarrioFromLocation(location) {
    if (!location) return '';
    const parts = location.split(/,| - /).map(s => s.trim());
    const specificParts = parts.filter(part => {
        const lower = part.toLowerCase();
        return lower !== 'medellin' &&
            lower !== 'medellín' &&
            lower !== 'envigado' &&
            lower !== 'antioquia' &&
            lower !== 'colombia';
    });
    return specificParts.length > 0 ? specificParts[0] : '';
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

const BARRIOS_LIST = [
    "El Portal", "Jardines", "La Abadia", "La Frontera",
    "La Magnolia", "Las Flores", "Las Vegas", "Loma Benedictinos",
    "Otra Parte", "Pontevedra", "San Marcos", "Villagrande", "Zuñiga"
];

const SOURCE_NAME_MAP = {
    'alberto_alvarez': 'Alberto Álvarez',
    'arrendamientos_envigado': 'Arrendamientos Envigado',
    'arrendamientosenvigadosa': 'Arrendamientos Envigado',
    'proteger': 'Inmobiliaria Proteger',
    'arrendamientos_las_vegas': 'Arrendamientos Las Vegas'
};

function getSourceName(slug) {
    return SOURCE_NAME_MAP[slug] || slug || 'Inmobiliaria';
}
