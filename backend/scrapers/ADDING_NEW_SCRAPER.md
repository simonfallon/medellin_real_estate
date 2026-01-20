# How to Add a New Real Estate Scraper

This document serves as a comprehensive guide for adding a new real estate website to the scraping engine. It covers backend implementation, testing strategy, image validation, and frontend integration.

**Use this document as a context/prompt when asking an AI Agent to implement a new scraper.**

---

## 0. Information Requirements (Placeholders)

Before starting, gather the following information. Fill in these details when requesting a new scraper implementation.

**2. Neighborhood Mapping (BARRIOS):**
How does the website encode neighborhoods in its search URL?
`[https://uribienes.com/inmuebles/arriendo?city=5266&type=1&pcmin=2500000&pcmax=3500000&neighborhood=Jardines+]`
Just plan barrio name separated with + and ending with + 

**3. Sample Property for Testing:**
A URL to a specific, active property listing to use for the single-property test.
`[https://uribienes.com/inmuebles/215327]`

**4. Search Results URL Pattern:**
The pattern used to filter by price, neighborhood, etc.
`[https://uribienes.com/inmuebles/arriendo?city=5266&type=1&pcmin=2500000&pcmax=3500000&neighborhood=Jardines+&minarea=50&maxarea=100]`

**5. Explicit Data for Verification:**
3 Habitaciones
2 Baños
1 Parqueadero
90 m²
Precio total: $ 3.500.00

Sample image address: https://s3-us-west-2.amazonaws.com/pictures.domus.la/inmobiliaria_871/wm/215327_1_1766532444.jpg

HAS GPS LOCATION

---

## 1. Backend: Implement the Scraper Logic

Create a new file in `backend/scrapers/` (e.g., `backend/scrapers/my_new_site.py`).

### Key Requirements:
1.  **Inheritance**: The class must inherit from `BaseScraper`.
2.  **Concurrency**: Define `concurrency` in `__init__` (usually 3-5).
3.  **Methods to Implement**:
    *   `get_search_inputs()`: Generates tuples of (search_url, barrio_name).
    *   `process_search_inputs()`: Orchestrates the search (often generic enough in Base, but usually needs `_extract_links_from_search_page`).
    *   `_extract_links_from_search_page(page, url)`: Parses the search result page to find property links.
    *   `extract_property_details(page, link, barrio_name)`: The core logic. Extracts title, price, area, description, images, etc.

### Unified Neighborhood Logic:
To ensure the "Barrio" filter works correctly on the frontend, we must standardize neighborhood names.
1.  **Define `UNIFIED_BARRIOS`**: A dictionary that maps the scraper's internal search keys (from `BARRIOS`) to the standardized display names (e.g., "La Abadia", "Zuñiga", "Loma Benedictinos").
2.  **Standardize in `get_search_inputs`**:
    ```python
    # Inside the loop
    unified_name = UNIFIED_BARRIOS.get(barrio_name, barrio_name)
    inputs.append((url, unified_name))
    ```
    This ensures that even if you search using a specific ID or code, the property is stored with a standardized `location` string (e.g., "La Abadia").
3.  **Target Names**: Reference the `BARRIOS_LIST` in `frontend/script.js` to know which names to map to.

### Strict Image Validation Checklist:
*   [ ] **Filter Extraneous Images**: Explicitly exclude "logo", "icon", "whatsapp", "facebook", etc.
*   [ ] **Container Targeting**: If the page has "Suggested Properties" at the bottom, **do not** scrape images from there. Identify the specific CSS container for the main gallery (e.g., `.main-carousel` or `.no-scroll`).
*   [ ] **High-Res Source**: If the site hosts low-res thumbnails and high-res versions (e.g., on a separate CDN like `pictures.domus.la`), try to capture the high-res URLs.
*   [ ] **Uniqueness**: Ensure the list of images has no duplicates.

### Data Completeness:
*   [ ] **GPS Extraction**: Check `window` objects (e.g., `window.inmueble`), map iframes, or "Waze/Google Maps" buttons for latitude/longitude.
*   [ ] **Name Mapping**: Ensure the scraper source name is mapped to a human-readable format in `frontend/utils.js` (e.g., `escala_inmobiliaria` -> "Escala Inmobiliaria").

---

## 2. Backend: Add Testing Logic

Create a new test file in `backend/tests/` (e.g., `backend/tests/test_my_new_site.py`).

### Required Tests:
1.  **`test_search_results`**: Verifies that the scraper can find links on a search page.
2.  **`test_single_property`**: Verifies strict data extraction from the sample URL using `unittest`.

### Strict Assertions Example:
```python
# Image Validation
self.assertIsInstance(result['images'], list)
self.assertTrue(len(result['images']) >= 5, f"Should capture at least 5 images (found {len(result['images'])})")

for img in result['images']:
    self.assertTrue(img.startswith('http'), f"Invalid image URL: {img}")
    self.assertFalse("logo" in img.lower(), f"Image should not be a logo: {img}")
    
# Uniqueness
self.assertEqual(len(result['images']), len(set(result['images'])), "Images must be unique")
```

---

## 3. Backend: Register the Scraper

1.  **Update `backend/scraper.py`**:
    *   Import the new scraper class.
    *   Add a `scrape_new_site_batch()` helper function.
    *   Update `scrape_all_batch()` to include the new scraper in `asyncio.gather()`.

2.  **Update `backend/main.py`**:
    *   Add an `elif source == "new_site_name":` block in the `/api/scrape/batch` endpoint.

---

## 4. Frontend: Add UI Support

1.  **Update `frontend/index.html`**:
    *   Add a new `<option>` to the `#websiteSelect` dropdown.
    ```html
    <option value="new_site_name">Fancy New Agency</option>
    ```

2.  **Update `frontend/script.js`**:
    *   Update the `sourceMap` object in `renderProperties` (or global) to map the code name to a display name.
    *   Update the `if` condition in `triggerScrape` to allow the new source value.
    *   Update the `applyFilters` function if special source filtering logic is needed (usually generic).

---

## 5. Frontend: Add Website Icon

To ensure the new source looks premium in the UI, download its favicon using the Google Shared Stuff (S2) service.

1.  **Run the following command** (replace `DOMAIN` and `FILENAME`):
    *   **Note**: Use `-L` to follow redirects and a User-Agent to avoid blocking.
    ```bash
    curl -L -A "Mozilla/5.0" "https://www.google.com/s2/favicons?domain=YOUR_DOMAIN.com&sz=64" -o frontend/assets/images/icons/new_site_name.png
    ```
2.  **Verify the File**:
    *   Run `file frontend/assets/images/icons/new_site_name.png` to ensure it says "PNG image data" and not "HTML document".
3.  **Naming Convention**:
    *   The filename MUST match the `source` string exactly (e.g., `new_site_name.png`). If the scraper returns `proteger`, the file must be `proteger.png`.

---

## Summary Checklist for Implementation

- [ ] Scraper Class created (`backend/scrapers/monitor.py`)
- [ ] Unified Barrios mapped and implemented
- [ ] Image extraction is strict (no logos, no suggested props)
- [ ] Test file created (`backend/tests/test_monitor.py`)
- [ ] `test_single_property` passes with strict assertions
- [ ] `backend/scraper.py` updated
- [ ] `backend/main.py` updated
- [ ] `frontend/index.html` updated
- [ ] `frontend/script.js` updated
- [ ] Verified manually via localhost UI
- [ ] Website icon added and verified
