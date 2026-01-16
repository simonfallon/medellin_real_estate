import asyncio
import re
from typing import List, Dict, Any, Tuple
from playwright.async_api import Page, BrowserContext

from .base import BaseScraper
from .types import Property

# Constants for Arrendamientos Envigado
ARRENDAMIENTOS_ENVIGADO_BASE_URL = "https://www.arrendamientosenvigadosa.com.co/"
SEARCH_URL_TEMPLATE = "https://www.arrendamientosenvigadosa.com.co/busqueda.html?servicio=Arriendo&tipo=1&ciudad=25999&barrio={barrio_id}&valmin={min_price}&valmax={max_price}"

# Filter Configuration
BARRIOS = {
    "El Portal": "6822",
    "Jardines": "6824",
    "La Abadia": "8807",
    "La Frontera": "8808",
    "La Magnolia": "6843",
    "Las Flores": "6848",
    "Las Vegas": "6816",
    "Loma Benedictinos": "8585",
    "Pontevedra": "6844",
    "San Marcos": "6823",
    "Villagrande": "6825",
    "Zuñiga": "8579"
}

PRICE_RANGES = [
    {"min": 2500000, "max": 3500000}
]

class ArrendamientosEnvigadoScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Arrendamientos Envigado", concurrency=3)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        """
        Generates the list of search URLs and their associated barrio names.
        """
        urls_to_scrape = []
        for barrio_name, barrio_id in BARRIOS.items():
            for price_range in PRICE_RANGES:
                url = SEARCH_URL_TEMPLATE.format(
                    barrio_id=barrio_id,
                    min_price=price_range["min"],
                    max_price=price_range["max"]
                )
                urls_to_scrape.append((url, barrio_name))
        return urls_to_scrape

    async def process_search_inputs(self, context: BrowserContext, inputs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        Visits each search URL and extracts property links.
        """
        # We can parallelize the search page processing too if we want, 
        # but for now let's keep it simple or use a smaller semaphore if needed.
        # The base class doesn't enforce how we process these, but returns a flat list.
        
        # We'll use a local semaphore for search pages
        sem = asyncio.Semaphore(5)
        
        async def process_single_search(url, barrio_name):
            async with sem:
                page = await context.new_page()
                try:
                    links = await self._extract_links_from_search_page(page, url)
                    return [(link, barrio_name) for link in links]
                except Exception as e:
                    print(f"[{self.name}] Error processing search {url}: {e}")
                    return []
                finally:
                    await page.close()

        tasks = [process_single_search(url, barrio) for url, barrio in inputs]
        results_lists = await asyncio.gather(*tasks)
        
        # Flatten results
        all_links = []
        seen_links = set()
        for r_list in results_lists:
            for link, barrio in r_list:
                if link not in seen_links:
                    seen_links.add(link)
                    all_links.append((link, barrio))
                    
        return all_links

    async def _extract_links_from_search_page(self, page: Page, search_url: str) -> List[str]:
        await page.goto(search_url)
        try:
            await page.wait_for_load_state("networkidle", timeout=10000)
        except:
            pass
        
        try:
            await page.wait_for_selector("a.link-footer-black", timeout=10000)
        except:
            print(f"[{self.name}] No results or timeout for {search_url}")
            return []

        links = []
        cards = await page.locator("a.link-footer-black").all()
        for card in cards:
            href = await card.get_attribute("href")
            if href and "inmueble.html" in href:
                if not href.startswith("http"):
                    href = ARRENDAMIENTOS_ENVIGADO_BASE_URL + href.lstrip("/")
                links.append(href)
        
        return list(set(links))

    async def extract_property_details(self, page: Page, link: str, barrio_name: str) -> Property:
        await page.goto(link)
        await page.wait_for_load_state("domcontentloaded")
        
        # Scrape details
        title = ""
        try:
            await page.wait_for_selector("div.lux-grey.bold", timeout=5000)
            title_el = page.locator("div.lux-grey.bold > span.bold").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
        except Exception:
            pass
        
        async def get_list_value(label):
            try:
                item = page.locator("li.list-group-item", has=page.locator(f"span", has_text=label))
                if await item.count() > 0:
                    spans = item.locator("span")
                    count = await spans.count()
                    if count >= 2:
                        return await spans.nth(1).inner_text()
            except:
                pass
            return ""

        price = await get_list_value("Precio")
        area = await get_list_value("Área")
        estrato = await get_list_value("Estrato")
        bedrooms = await get_list_value("Alcobas")
        bathrooms = await get_list_value("Baños")
        parking = await get_list_value("Parqueadero")
        
        description = ""
        try:
            desc_header = page.locator("p", has_text="DESCRIPCIÓN")
            if await desc_header.count() > 0:
                description = await desc_header.locator("xpath=following-sibling::p[1]").inner_text()
        except:
            pass

        # Icon fallback
        async def get_value_by_icon(icon_keyword):
            try:
                xpath = f"//img[contains(@src, '{icon_keyword}')]/following-sibling::span"
                el = page.locator(xpath).first
                if await el.count() > 0:
                    return await el.inner_text()
            except:
                 pass
            return ""

        if not bedrooms: bedrooms = await get_value_by_icon("bed")
        if not bathrooms: bathrooms = await get_value_by_icon("bathtub")
        if not parking: parking = await get_value_by_icon("car")

        # Regex fallback
        if not bedrooms:
            match = re.search(r"(\d+)\s*(?:alcobas|habitaciones)", description, re.IGNORECASE)
            if match: bedrooms = match.group(1)
                
        if not bathrooms:
            match = re.search(r"(\d+)\s*baños", description, re.IGNORECASE)
            if match: bathrooms = match.group(1)
                
        if not parking:
            match = re.search(r"(\d+)\s*parqueaderos?", description, re.IGNORECASE)
            if match: parking = match.group(1)
            elif "parqueadero" in description.lower(): parking = "1"
        
        images = []
        carousel_imgs = await page.locator(".carousel-item img").all()
        for img in carousel_imgs:
            src = await img.get_attribute("src")
            if src:
                if "logo-ae-new.png" in src or "assets/" in src:
                    continue
                images.append(src)
                
        # Extract code from URL
        code = ""
        try:
            code_match = re.search(r'(?:codigo|inmueble)=(\d+)', link)
            if code_match:
                code = code_match.group(1)
        except:
            pass
        
        # Default image if none found
        image_url = images[0] if images else ""

        return {
            "code": code,
            "title": title.strip() if title else "",
            "location": barrio_name.strip(),
            "price": price.strip() if price else "",
            "area": area.strip() if area else "",
            "estrato": estrato.strip() if estrato else "",
            "bedrooms": bedrooms.strip() if bedrooms else "",
            "bathrooms": bathrooms.strip() if bathrooms else "",
            "parking": parking.strip() if parking else "",
            "description": description.strip(),
            "images": images,
            "image_url": image_url,
            "link": link,
            "source": "arrendamientos_envigado"
        }

# Facade for backward compatibility
async def scrape() -> List[Property]:
    scraper = ArrendamientosEnvigadoScraper()
    return await scraper.scrape()

# Expose helper functions for tests if needed
# Note: Since tests called 'process_search_page' and 'scrape_page_details' directly, 
# we might need to expose them or update tests. 
# For now, let's expose wrappers that mimic the old API for testing purposes, 
# or rewrite tests. The prompt asked to "improve maintainability", so updating tests is better.
# But "Verify functionality with test_arrendamientos_envigado.py" implies keeping tests working.
# Let's see if we can expose static methods or just update the test file later.
# Actually, the user's plan said "Verify functionality with test_arrendamientos_envigado.py".
# I should probably update the test file to use the class methods or make these static.
# But 'process_search_page' takes a 'page' object. 
# Let's add them as module-level wrappers that delegate to an instance for now, solely for tests.

async def process_search_page(page, search_url, barrio_name):
    scraper = ArrendamientosEnvigadoScraper()
    # 1. Get links from the search page
    links = await scraper._extract_links_from_search_page(page, search_url)
    
    # 2. Scrape details for each link
    # The old test expects us to use the passed 'page' but the old logic created NEW pages for details.
    # We can reuse the scraper's method. However, scraper methods usually manage their own pages or take a page.
    # extract_property_details takes a page.
    # We should create a new page for each detail to be safe and consistent with the legacy behavior's robustness,
    # or better yet, use the scraper's semaphore-managed logic if possible.
    # But here we are in a simple function with a passed 'page' (which is probably the search page).
    # The loop in the old code used 'context.new_page()'.
    
    context = page.context
    results = []
    
    # We can't easily use the scraper's tasks because they might expect internal state or manage their own browsing context.
    # But extract_property_details is stateless regarding the browser, it just needs a page.
    
    for link in links:
        try:
            detail_page = await context.new_page()
            prop = await scraper.extract_property_details(detail_page, link, barrio_name)
            if prop:
                results.append(prop)
            await detail_page.close()
        except Exception as e:
            print(f"Error in facade scraping {link}: {e}")
            
    return results

async def scrape_page_details(page, url, barrio_name):
    scraper = ArrendamientosEnvigadoScraper()
    return await scraper.extract_property_details(page, url, barrio_name)
