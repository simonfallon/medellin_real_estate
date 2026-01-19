
const API_URL = '/api';

export async function fetchProperties(limit = 200) {
    const response = await fetch(`${API_URL}/properties?limit=${limit}`);
    if (!response.ok) {
        throw new Error('Failed to fetch properties');
    }
    return await response.json();
}

export async function fetchLocations() {
    const response = await fetch(`${API_URL}/properties/locations`);
    if (!response.ok) throw new Error('Error fetching locations');
    return await response.json();
}

export async function scrapeSource(source, force = false) {
    const endpoint = `/api/scrape/batch?source=${source}&force=${force}`;
    const res = await fetch(endpoint, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json'
        }
    });
    const data = await res.json();

    if (!res.ok) {
        throw new Error(data.detail || 'Error scraping source');
    }
    return data;
}
