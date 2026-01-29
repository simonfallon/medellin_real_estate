# How to Add a New Real Estate Scraper

This document serves as a comprehensive guide for adding a new real estate website to the scraping engine. It covers backend implementation, testing strategy, image validation, and frontend integration.

**Use this document as a context/prompt when asking an AI Agent to implement a new scraper.**

---

## 0. Information Requirements (Placeholders)

Before starting, gather the following information. Fill in these details when requesting a new scraper implementation.

**2. Neighborhood Mapping (BARRIOS):**
How does the website encode neighborhoods in its search URL?
This does not work properly for this website. We have to go to 
`https://www.livinmobiliaria.com/resultados?gestion=Arriendo&tipo=Apartamentos&s=municipio-en-envigado&rango-precio=2000000-2600000&rango-area=50-100`
and scrape only the properties that have the desired BARRIOs in the name of the card, for instance:
`Apartamento en Arriendo - La Magnolia`

**3. Sample Property for Testing:**
A URL to a specific, active property listing to use for the single-property test.
`[https://www.livinmobiliaria.com/detalle-propiedad/apartamento-enarriendo-en-la-magnolia-20167]`

**4. Search Results URL Pattern:**
The pattern used to filter by price, neighborhood, etc.
`[https://www.livinmobiliaria.com/resultados?gestion=Arriendo&tipo=Apartamentos&s=municipio-en-envigado&rango-precio=2000000-2600000&rango-area=50-100]`

**5. Explicit Data for Verification:**
Precio total (COP) $ 2.300.000
87m²
3 Alcobas
2 Baños
1 Parqueaderos

Sample image address: https://produccion-bien-raiz.s3.amazonaws.com/a0j-inmueble__c/a0jHq00000ayVLMIA2/COCINA20.jpeg

HAS GPS LOCATION: YES

---

## 1. Backend: Implement the Scraper Logic

Create a new file in `backend/scrapers/` (e.g., `backend/scrapers/my_new_site.py`).

### Key Requirements:

1. **Inheritance**: The class must inherit from `BaseScraper`.

2. **Configuration**: Use `ScraperConfig` dataclass to configure the scraper:
   ```python
   from .base import BaseScraper, ScraperConfig

   class MyNewSiteScraper(BaseScraper):
       def __init__(self):
           config = ScraperConfig(
               detail_concurrency=3,      # Concurrent detail page requests
               search_concurrency=5,      # Concurrent search page requests
               detail_load_state="domcontentloaded",  # or "networkidle" for heavy JS sites
               image_exclusions=ScraperConfig().image_exclusions | {"site_specific_exclusion"},
           )
           super().__init__(name="My New Site", config=config)
   ```

3. **Methods to Implement**:
   *   `get_search_inputs()`: Generates tuples of (search_url, barrio_name).
   *   `_extract_links_from_search_page(page, url)`: Parses the search result page to find property links.
   *   `extract_property_details(page, link, barrio_name)`: The core logic. Extracts title, price, area, description, images, etc.

   **Note**: `process_search_inputs()` is inherited from `BaseScraper` and handles concurrency automatically. Only override if you need special handling (e.g., "Load More" buttons).

### ScraperConfig Options:

| Option | Default | Description |
|--------|---------|-------------|
| `detail_concurrency` | 4 | Max concurrent detail page requests |
| `search_concurrency` | 5 | Max concurrent search page requests |
| `page_load_timeout` | 15000 | Timeout for page loads (ms) |
| `selector_timeout` | 10000 | Timeout for selector waits (ms) |
| `search_load_state` | "domcontentloaded" | Load state for search pages |
| `detail_load_state` | "domcontentloaded" | Load state for detail pages ("networkidle" for heavy JS) |
| `image_exclusions` | {"logo", "icon", ...} | Keywords to filter from image URLs |
| `max_images` | 15 | Maximum images to collect per property |

### Base Class Utility Methods:

Use these utilities instead of writing custom implementations:

| Method | Purpose |
|--------|---------|
| `navigate_and_wait(page, url, wait_for_selector=None)` | Navigate to URL with configured load strategy |
| `filter_property_images(urls, extra_exclusions=None)` | Filter logos/icons/social media images |
| `extract_gps_from_mapbox(page)` | Extract coords from Mapbox feedback link |
| `extract_gps_from_window_var(page, var_name, lat_key, lng_key)` | Extract coords from JS window variable |
| `extract_gps_coordinates(page, full_text, window_var)` | Try all GPS methods with fallbacks |
| `extract_features_from_text(text)` | Regex extraction for bedrooms/bathrooms/area/parking/estrato |
| `normalize_url(href, base_url)` | Convert relative URL to absolute |

### Example Scraper Structure:

```python
import re
from typing import List, Tuple, Optional
from playwright.async_api import Page

from .base import BaseScraper, ScraperConfig
from .types import Property

BASE_URL = "https://example.com"
SEARCH_URL_TEMPLATE = "https://example.com/search?price_min={min_price}&price_max={max_price}&barrio={barrio}"

BARRIOS = {
    "La Abadia": "la-abadia",
    "Zuñiga": "zuniga",
}

UNIFIED_BARRIOS = {
    "La Abadia": "La Abadia",
    "Zuñiga": "Zuñiga",
}

class ExampleScraper(BaseScraper):
    def __init__(self):
        config = ScraperConfig(
            detail_concurrency=3,
            search_concurrency=5,
        )
        super().__init__(name="Example Site", config=config)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        inputs = []
        for barrio_name, barrio_slug in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                url = SEARCH_URL_TEMPLATE.format(
                    min_price=price_range["min"],
                    max_price=price_range["max"],
                    barrio=barrio_slug,
                )
                unified_name = UNIFIED_BARRIOS.get(barrio_name, barrio_name)
                inputs.append((url, unified_name))
        return inputs

    # process_search_inputs() is inherited from BaseScraper

    async def _extract_links_from_search_page(self, page: Page, search_url: str) -> List[str]:
        await self.navigate_and_wait(page, search_url, wait_for_selector="a.property-link")

        links = []
        property_links = await page.locator("a.property-link").all()
        for link_el in property_links:
            href = await link_el.get_attribute("href")
            if href:
                href = self.normalize_url(href, BASE_URL)
                links.append(href)
        return list(set(links))

    async def extract_property_details(self, page: Page, link: str, barrio_name: str) -> Optional[Property]:
        await self.navigate_and_wait(page, link, wait_for_selector="h1")

        # Extract title
        title = ""
        try:
            title_el = page.locator("h1").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
        except:
            pass

        # Extract features using base class utility
        full_text = await page.locator("body").inner_text()
        features = self.extract_features_from_text(full_text)

        # Extract images using filter utility
        raw_images = []
        imgs = await page.locator(".gallery img").all()
        for img in imgs:
            src = await img.get_attribute("src")
            if src:
                raw_images.append(src)
        images = self.filter_property_images(raw_images)

        # Extract GPS using base utility
        latitude, longitude = await self.extract_gps_coordinates(page, full_text)

        return {
            "code": "",
            "title": title.strip(),
            "location": barrio_name,
            "price": features["price"],
            "area": features["area"],
            "bedrooms": features["bedrooms"],
            "bathrooms": features["bathrooms"],
            "parking": features["parking"],
            "estrato": features["estrato"],
            "images": images,
            "image_url": images[0] if images else "",
            "link": link,
            "source": "example_site",
            "description": "",
            "latitude": latitude,
            "longitude": longitude,
        }
```

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
*   [ ] **Use `filter_property_images()`**: This utility automatically filters logos, icons, social media images.
*   [ ] **Add site-specific exclusions**: Pass extra keywords to `filter_property_images(raw_images, {"site_logo", "banner"})` or add them to `ScraperConfig.image_exclusions`.
*   [ ] **Container Targeting**: If the page has "Suggested Properties" at the bottom, **do not** scrape images from there. Identify the specific CSS container for the main gallery (e.g., `.main-carousel` or `.no-scroll`).
*   [ ] **Uniqueness**: The `filter_property_images()` utility automatically ensures no duplicates.

### Data Completeness:
*   [ ] **GPS Extraction**: Use `extract_gps_coordinates(page, full_text, window_var)` which tries multiple methods automatically (window variables, Mapbox, Google Maps, regex).
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

- [ ] Scraper Class created (`backend/scrapers/new_site.py`)
- [ ] ScraperConfig configured appropriately
- [ ] Unified Barrios mapped and implemented
- [ ] Using base class utilities (navigate_and_wait, filter_property_images, etc.)
- [ ] Image extraction is strict (no logos, no suggested props)
- [ ] Test file created (`backend/tests/test_new_site.py`)
- [ ] `test_single_property` passes with strict assertions
- [ ] `backend/scraper.py` updated
- [ ] `backend/main.py` updated
- [ ] `frontend/index.html` updated
- [ ] `frontend/script.js` updated
- [ ] Verified manually via localhost UI
- [ ] Website icon added and verified
