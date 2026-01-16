import asyncio
import re
from typing import List, Tuple
from playwright.async_api import Page, BrowserContext

from .base import BaseScraper
from .types import Property

# Constants for Inmobiliaria Proteger
PROTEGER_BASE_URL = "https://inmobiliariaproteger.com"

# Search URL with placeholders
# Note: min_price and max_price need dots (e.g. 2.500.000)
SEARCH_URL_TEMPLATE = (
    "https://inmobiliariaproteger.com/s?"
    "id_country=1&id_region=2&id_city=291&id_location=&"
    "id_zone={zone_id}&"
    "id_property_type=2&id_property_condition=&"
    "business_type%5B%5D=for_rent&"
    "bedrooms=&bathrooms=&"
    "min_price={min_price}&max_price={max_price}"
)

# Zone IDs discovered
BARRIOS = {
    "Abadia": "388040",
    "Beneditinos": "377268",
    "El Portal": "377212",
    "La Abadía": "388041",
    "La Magnolia": "377213",
    "Otra Parte": "667091",
    "Pontevedra": "377215",
    "San Marcos": "377214",
    "Zuniga": "377226" # Using Zuñiga ID
}

class ProtegerScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Inmobiliaria Proteger", concurrency=3)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        inputs = []
        for barrio_name, zone_id in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                # Format prices with dots
                min_p = f"{price_range['min']:,}".replace(",", ".")
                max_p = f"{price_range['max']:,}".replace(",", ".")
                
                url = SEARCH_URL_TEMPLATE.format(
                    zone_id=zone_id,
                    min_price=min_p,
                    max_price=max_p
                )
                inputs.append((url, barrio_name))
        return inputs

    async def process_search_inputs(self, context: BrowserContext, inputs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        all_links = []
        sem = asyncio.Semaphore(5)

        async def process_single_search(url, barrio_name):
            async with sem:
                page = await context.new_page()
                try:
                    links = await self._extract_links_from_search_page(page, url)
                    return [(link, barrio_name) for link in links]
                except Exception as e:
                    print(f"[{self.name}] Error searching {barrio_name}: {e}")
                    return []
                finally:
                    await page.close()

        tasks = [process_single_search(url, barrio) for url, barrio in inputs]
        results = await asyncio.gather(*tasks)
        
        seen = set()
        for r_list in results:
            for link, barrio in r_list:
                if link not in seen:
                    all_links.append((link, barrio))
                    seen.add(link)
        
        return all_links

    async def _extract_links_from_search_page(self, page: Page, search_url: str) -> List[str]:
        # print(f"[{self.name}] Navigating to {search_url}")
        await page.goto(search_url)
        try:
             await page.wait_for_load_state("networkidle", timeout=20000)
        except:
             pass

        links = []
        anchors = await page.locator("a").all()
        for a in anchors:
            href = await a.get_attribute("href")
            if href:
                # Filter valid property links
                # Must NOT contain /s/ (search), ? (query params), or other known non-property paths
                if "/s/" in href or "?" in href or "search?" in href or "business_type" in href:
                    continue
                
                # Must match typical property structure
                # https://inmobiliariaproteger.com/apartamento-alquiler-la-magnolia-envigado/9420502
                is_valid = False
                if "apartamento" in href and "alquiler" in href:
                    is_valid = True
                elif re.search(r'/\d+$', href) and "inmobiliariaproteger.com" in href:
                    is_valid = True
                    
                if is_valid:
                    if not href.startswith("http"):
                        href = PROTEGER_BASE_URL + href if href.startswith("/") else f"{PROTEGER_BASE_URL}/{href}"
                    
                    if href not in links and href != search_url:
                        links.append(href)
                        
        return list(set(links))

    async def extract_property_details(self, page: Page, link: str, barrio_name: str) -> Property:
        await page.goto(link)
        await page.wait_for_load_state("domcontentloaded")
        
        # Defaults
        title = ""
        price = ""
        area = ""
        bedrooms = ""
        bathrooms = ""
        parking = ""
        estrato = ""
        description = ""
        image_url = ""
        images = []
        code = ""
        
        # Title
        try:
            title = await page.title()
            title = title.split("-")[0].strip()
        except: pass
        
        # Details Extraction with Parent Fallback
        async def get_value(label_text):
            # Try to find element containing label
            try:
                # XPath to find ANY element containing the text
                # We want to iterate through them because the word might appear in description
                elements = await page.locator(f"xpath=//*[contains(text(), '{label_text}')]").all()
                
                for el in elements:
                    # Helper to validate and clean value
                    def clean_val(v):
                        # Remove label, colons, dots
                        v = v.replace(label_text, "").replace(":", "").replace(".", "").strip()
                        # Limit length to avoid capturing full paragraphs
                        # 50 chars should be enough for "120 m2", "3", "Parqueadero cubierto"
                        if len(v) > 50: 
                            return ""
                        return v

                    # 1. Check if the element text itself has the value (e.g. "Alcoba: 3")
                    txt = await el.inner_text()
                    val = clean_val(txt)
                    if val: return val
                        
                    # 2. Check Parent Text (often "Label: Value" is in parent)
                    parent = el.locator("xpath=..")
                    p_txt = await parent.inner_text()
                    val = clean_val(p_txt)
                    if val: return val
                    
                    # 3. Check Next Sibling
                    sibling = el.locator("xpath=following-sibling::*[1]")
                    if await sibling.count() > 0:
                        s_txt = await sibling.inner_text()
                        if len(s_txt) < 50:
                             return s_txt.strip()
            except: pass
            return ""

        # Price extraction
        try:
            # Try multiple selectors
            price_el = page.locator(".price, .precio, .property-price, .precio-inmueble").first
            if await price_el.count() > 0:
                price = await price_el.inner_text()
            else:
                 # Look for h2/h3/h4 with price format
                 headers = await page.locator("h1, h2, h3, h4, strong, span").all()
                 for h in headers:
                     txt = await h.inner_text()
                     if "$" in txt and any(c.isdigit() for c in txt) and "COP" in txt:
                         clean_p = txt.strip()
                         if len(clean_p) < 40:
                             price = clean_p
                             break
        except: pass

        if not price:
             # Try from title again
             try:
                 t_str = await page.title()
                 if "-" in t_str:
                     parts = t_str.split("-")
                     for p in reversed(parts):
                         if "$" in p or "COP" in p:
                             price = p.strip()
                             break
             except: pass

        code = await get_value("Código")
        area = await get_value("Área Construida") or await get_value("Área Privada") or await get_value("Área")
        bedrooms = await get_value("Alcoba") or await get_value("Habitaciones")
        bathrooms = await get_value("Baños")
        parking = await get_value("Garaje") or await get_value("Parqueadero")
        estrato = await get_value("Estrato")
        
        # Description
        try:
            # Look for a paragraph with description
            desc_el = page.locator("#description, .description").first
            if await desc_el.count() > 0:
                description = await desc_el.inner_text()
        except: pass
        
        # Images
        try:
            # The gallery uses Swiper. Images are in .swiper-slide elements.
            # We want all images, not just the visible one.
            # They are usually direct img children or nested.
            
            # Wait for swiper to load
            try:
                await page.wait_for_selector(".swiper-slide", timeout=5000)
            except:
                pass
                
            imgs = await page.locator(".swiper-slide img").all()
            for img in imgs:
                src = await img.get_attribute("src")
                
                # Validating src
                # If it's in the main gallery (swiper-slide), it's likely a property image.
                # We just want to filter out obvious garbage if any.
                if src and "logo" not in src:
                    # Some src might be relative or just need cleanup
                    if src not in images:
                        images.append(src)
        except: pass
        
        if images:
            image_url = images[0]
            
        # Refine Code 
        if not code:
            # Try from URL
            match = re.search(r'/(\d+)$', link)
            if match:
                code = match.group(1)
                
        # Refine Price
        if not price:
             # Try from title
             try:
                 t_str = await page.title()
                 if "-" in t_str:
                     parts = t_str.split("-")
                     for p in reversed(parts):
                         if "$" in p or "COP" in p:
                             price = p.strip()
                             break
             except: pass

        if not price:
             # Try searching specifically for price pattern in H2 or H1
             try:
                 price = await page.evaluate("""() => {
                     const headers = Array.from(document.querySelectorAll('h1, h2, h3, .price, .precio'));
                     for (const h of headers) {
                        if (h.innerText.includes('$')) return h.innerText;
                     }
                     return '';
                 }""")
             except: pass

        return {
            "code": code,
            "title": title or "Apartamento en Arriendo",
            "location": barrio_name,
            "price": price,
            "area": area,
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "parking": parking,
            "estrato": estrato,
            "image_url": image_url,
            "images": images,
            "link": link,
            "source": "proteger",
            "description": description
        }
