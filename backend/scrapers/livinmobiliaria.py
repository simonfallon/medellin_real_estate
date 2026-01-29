import re
from typing import List, Tuple, Optional
from playwright.async_api import Page

from .base import BaseScraper, ScraperConfig
from .types import Property

# Constants for Livinmobiliaria
BASE_URL = "https://www.livinmobiliaria.com"
# Searching for Apartments in Envigado broadly, then filtering by barrio text
SEARCH_URL_TEMPLATE = "https://www.livinmobiliaria.com/resultados?gestion=Arriendo&tipo=Apartamentos&s=municipio-en-envigado&rango-precio={min_price}-{max_price}"

# Unified Barrio Mapping
UNIFIED_BARRIOS = {
    "El Portal": "El Portal",
    "Jardines": "Jardines",
    "La Abadía": "La Abadia",
    "La Abadia": "La Abadia", 
    "La Frontera": "La Frontera",
    "La Magnolia": "La Magnolia",
    "Las Flores": "Las Flores",
    "Las Vegas": "Las Vegas",
    "Loma Benedictinos": "Loma Benedictinos",
    "Otra Parte": "Otra Parte",
    "Pontevedra": "Pontevedra",
    "San Marcos": "San Marcos",
    "Villagrande": "Villagrande",
    "Zuñiga": "Zuñiga",
    # Add variations found on site if any
}

class LivinmobiliariaScraper(BaseScraper):
    def __init__(self, config: ScraperConfig = None):
        default_config = ScraperConfig(
            detail_concurrency=4,
            search_concurrency=3,
            detail_load_state="domcontentloaded",
        )
        if config:
            default_config.price_ranges = config.price_ranges
        
        super().__init__(name="Livinmobiliaria", config=default_config)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        """
        Generates search URLs. Since we can't filter by barrio in the URL easily,
        we search by price range + Envigado and filter later.
        The 'barrio_name' in the tuple will be 'Envigado' initially, 
        but we'll override it during link extraction if we find a match.
        """
        inputs = []
        for price_range in self.PRICE_RANGES:
            url = SEARCH_URL_TEMPLATE.format(
                min_price=price_range["min"],
                max_price=price_range["max"],
            )
            # Pass "Envigado" as generic context; specific barrio detected in _extract_links
            inputs.append((url, "Envigado"))
        return inputs

    async def _extract_links_from_search_page(self, page: Page, search_url: str) -> List[str]:
        """
        Extracts property links, stopping before the "También te puede interesar" section.
        """
        # Navigate with domcontentloaded (faster than networkidle)
        await page.goto(search_url, wait_until="domcontentloaded", timeout=60000)
        # Give JS time to render
        await page.wait_for_timeout(5000)

        # Use evaluate to extract candidates with position filtering
        candidates = await page.evaluate("""() => {
            const results = [];
            const seenHrefs = new Set();
            
            // 1. Find the stop element ("También te puede interesar")
            const headerCandidates = Array.from(document.querySelectorAll('h2, h3, h4, h5, div, span, p'));
            const stopEl = headerCandidates.find(el => {
                if (el.children.length > 3) return false;
                const txt = el.innerText ? el.innerText.trim().toLowerCase() : '';
                return txt.includes('también te puede interesar') || txt.includes('tambien te puede interesar');
            });

            // 2. Find all property detail links
            const links = Array.from(document.querySelectorAll('a[href*="detalle-propiedad"]'));
            
            for (const link of links) {
                // Skip if after stop element
                if (stopEl && (stopEl.compareDocumentPosition(link) & Node.DOCUMENT_POSITION_FOLLOWING)) {
                    continue;
                }
                
                // Skip duplicates
                if (seenHrefs.has(link.href)) {
                    continue;
                }
                
                // Find the parent card container (go up the DOM tree)
                let card = link;
                let depth = 0;
                while (card && depth < 10) {
                    // Look for a container that has substantial text content
                    const text = card.innerText || card.textContent || '';
                    if (text.length > 50) {  // Card should have meaningful content
                        break;
                    }
                    card = card.parentElement;
                    depth++;
                }
                
                if (card && link.href) {
                    const cardText = card.innerText || card.textContent || '';
                    seenHrefs.add(link.href);
                    results.push({
                        href: link.href,
                        text: cardText
                    });
                }
            }
            
            return results;
        }""")

        links = []
        
        for item in candidates:
            href = item['href']
            
            # Normalize
            href = self.normalize_url(href, BASE_URL)
            
            # Extract barrio from URL (e.g., "apartamento-en-la-magnolia-123" -> "la magnolia")
            # The URL pattern is: /detalle-propiedad/apartamento-[tipo]-en-[barrio]-[code]
            url_parts = href.split('/')[-1].lower()  # Get last part of URL
            
            # Check if any target barrio appears in the URL
            matched_barrio = False
            for barrio_name in UNIFIED_BARRIOS.keys():
                # Normalize barrio name for URL matching (remove accents, spaces to hyphens)
                barrio_normalized = barrio_name.lower().replace('í', 'i').replace('ñ', 'n').replace(' ', '-')
                if barrio_normalized in url_parts or barrio_name.lower() in url_parts:
                    matched_barrio = True
                    break
            
            if matched_barrio:
                links.append(href)

        return list(set(links))

    async def extract_property_details(self, page: Page, link: str, barrio_name: str) -> Optional[Property]:
        await self.navigate_and_wait(page, link, wait_for_selector="h1", timeout=30000)
        
        full_text = await page.locator("body").inner_text()

        # 1. Title
        title = ""
        try:
            title_el = page.locator("h1").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
        except:
            pass

        # 2. Location/Barrio Detection (Re-verify)
        location = None
        full_text_lower = full_text.lower()
        title_lower = title.lower()
        
        for name, unified in UNIFIED_BARRIOS.items():
            if name.lower() in title_lower or name.lower() in full_text_lower:
                location = unified
                break
        
        if not location:
             # Strict filtering: if not in our target list, skip it.
             return None
        
        # 3. Features
        features = self.extract_features_from_text(full_text)
        
        # 4. Price (Attempt specific selector first)
        price = features["price"]
        try:
            price_el = page.locator(".price, .precio, .inmueble-precio").first
            if await price_el.count() > 0:
                raw_price = await price_el.inner_text()
                # Simple cleanup
                if "$" in raw_price:
                    price = raw_price.strip()
        except:
            pass

        # 5. Images
        raw_images = []
        # Try common gallery selectors
        imgs = await page.locator(".gallery img, .carousel img, .slider-pro img, .fotorama__img").all()
        for img in imgs:
            src = await img.get_attribute("src")
            if src:
                raw_images.append(src)
        
        # Fallback: look for all large images
        if not raw_images:
            all_imgs = await page.locator("img").all()
            for img in all_imgs:
                src = await img.get_attribute("src")
                if src and "http" in src:
                    raw_images.append(src)

        images = self.filter_property_images(raw_images)

        # 6. GPS
        latitude, longitude = await self.extract_gps_coordinates(page, full_text)

        # 7. Code
        code = ""
        # Often in URL or text
        match = re.search(r"(\d+)$", link) # ID at end of URL usually
        if match:
            code = f"LIV-{match.group(1)}"
        else:
            # Try finding "Código: X" in text
            code_match = re.search(r"C[óo]digo[:\s]+(\d+)", full_text, re.IGNORECASE)
            if code_match:
                code = f"LIV-{code_match.group(1)}"

        return {
            "code": code,
            "title": title.strip(),
            "location": location,
            "price": price,
            "area": features["area"],
            "bedrooms": features["bedrooms"],
            "bathrooms": features["bathrooms"],
            "parking": features["parking"],
            "estrato": features["estrato"],
            "images": images,
            "image_url": images[0] if images else "",
            "link": link,
            "source": "livinmobiliaria",
            "description": "",
            "latitude": latitude,
            "longitude": longitude,
        }
