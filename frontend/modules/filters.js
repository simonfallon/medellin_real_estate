
import { parsePrice, parseArea, getBarrioFromLocation } from '/static/utils.js?v=1';

export function sortProperties(properties, sortBy) {
    // Create a shallow copy to avoid mutating original array
    return [...properties].sort((a, b) => {
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

export function filterProperties(properties, filters) {
    const {
        priceMin = 0,
        priceMax = Infinity,
        areaMin = 0,
        areaMax = Infinity,
        bedsMin = 0,
        bedsMax = Infinity,
        parkingMin = 0,
        selectedWebsite,
        selectedBarrios
    } = filters;

    return properties.filter(p => {
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
            matchesBarrio = selectedBarrios.some(b => pLoc.includes(b.toLowerCase()));
        }

        return matchesPrice && matchesArea && matchesBeds && matchesParking && matchesSource && matchesBarrio;
    });
}
