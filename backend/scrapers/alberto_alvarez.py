import asyncio
import re
import json
from typing import List, Dict, Any, Tuple, Optional
from playwright.async_api import Page, BrowserContext

from .base import BaseScraper
from .types import Property

# Constants for Alberto Alvarez
ALBERTO_ALVAREZ_BASE_URL = "https://albertoalvarez.com"

# Barrios dictionary - maps display name to URL slug
BARRIOS = {
    "El Portal": "el-portal",
    "Jardines": "jardines",
    "La Abadia": "la-abadia",
    "La Frontera": "la-frontera",
    "La Magnolia": "la-magnolia",
    "Las Flores": "las-flores",
    "Las Vegas": "las-vegas",
    "Loma Benedictinos": "loma-benedictinos",
    "Pontevedra": "pontevedra",
    "San Marcos": "san-marcos",
    "Villagrande": "villagrande",
    "Zuñiga": "zuniga",
    "Otra Parte": "otra-parte",
}

SEARCH_URL_TEMPLATE = "https://albertoalvarez.com/inmuebles/arrendamientos/apartamento/envigado/envigado/{barrio}/?rentFrom={min_price}&rentTo={max_price}&roomsFrom=1&roomsTo=3"

class AlbertoAlvarezScraper(BaseScraper):
    def __init__(self):
        super().__init__(name="Alberto Alvarez", concurrency=8)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        """
        Generates search URLs with their barrio metadata.
        """
        inputs = []
        for barrio_name, barrio_slug in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                url = SEARCH_URL_TEMPLATE.format(
                    barrio=barrio_slug,
                    min_price=price_range["min"],
                    max_price=price_range["max"]
                )
                inputs.append((url, barrio_name))
        return inputs

    async def process_search_inputs(self, context: BrowserContext, inputs: List[Tuple[str, str]]) -> List[Tuple[str, str]]:
        """
        Visits each search URL and extracts property links.
        """
        # We process search URLs sequentially for simplicity or use a small semaphore
        # The original code did this sequentially with a fresh browser for search logic vs details.
        # Here we use the shared browser context.
        
        all_links = []
        url_to_barrio = {}
        
        # We can run these in parallel but search pages might be heavy.
        # Let's use a semaphore.
        sem = asyncio.Semaphore(4)

        async def process_search(url, barrio_name):
            async with sem:
                page = await context.new_page()
                try:
                    links = await self._get_search_results_links(page, url)
                    return [(link, barrio_name) for link in links]
                except Exception as e:
                    print(f"[{self.name}] Error searching in {barrio_name}: {e}")
                    return []
                finally:
                    await page.close()

        tasks = [process_search(url, barrio) for url, barrio in inputs]
        results = await asyncio.gather(*tasks)
        
        # Flatten and unique
        seen = set()
        for r_list in results:
            for link, barrio in r_list:
                if link not in seen:
                    all_links.append((link, barrio))
                    seen.add(link)
                    
        return all_links

    async def _get_search_results_links(self, page: Page, url: str) -> List[str]:
        print(f"[{self.name}] Navigating to {url}...")
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except:
            print(f"[{self.name}] Timeout loading {url}, attempting partial content scrape")
        
        # Handle "Load More"
        for _ in range(3): 
            await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
            await asyncio.sleep(1)
            try:
                load_more = page.locator("button:has-text('Ver más'), .load-more").first
                if await load_more.is_visible(timeout=1000):
                    await load_more.click()
                    await asyncio.sleep(1)
            except:
                break

        links = []
        property_elements = await page.locator("a[href*='/inmuebles/detalle/']").all()
        for el in property_elements:
            href = await el.get_attribute("href")
            if href:
                if not href.startswith("http"):
                    href = ALBERTO_ALVAREZ_BASE_URL + href
                links.append(href)
                
        return list(set(links))

    async def extract_property_details(self, page: Page, link: str, barrio_name: str) -> Optional[Property]:
        try:
            await page.goto(link, wait_until="networkidle", timeout=30000)
        except:
             print(f"timeout loading detail page {link}, attempting partial content scrape")
        
        # 1. Try to extract from Hidden JSON (Most Reliable)
        try:
            json_el = page.locator("textarea.field-property").first
            if await json_el.count() > 0:
                json_text = await json_el.input_value()
                if not json_text:
                    json_text = await json_el.inner_text()
                
                if json_text:
                    try:
                        data = json.loads(json_text)
                        return self._parse_json_data(data, link, barrio_name)
                    except json.JSONDecodeError:
                        print(f"Failed to decode JSON for {link}")
        except Exception as e:
            print(f"JSON extraction failed for {link}, falling back to DOM: {e}")

        # 2. DOM Scraping (Fallback)
        print(f"Fallback: DOM scraping for {link}")
        return await self._scrape_dom_details(page, link, barrio_name)

    def _parse_json_data(self, data: Dict, link: str, barrio_name: str) -> Property:
        code = data.get("code", "")
        title = f"{data.get('propertyType', 'Inmueble')} EN ARRIENDO"
        
        location = data.get("sectorName", "")
        if not location:
            location = data.get("zoneName", "")
        if not location:
            location = barrio_name or "Envigado"
            
        price = str(data.get("rentValue", ""))
        area = str(data.get("builtArea", ""))
        bedrooms = str(data.get("numberOfRooms", ""))
        
        hh = data.get("householdFeatures", {})
        bathrooms = str(hh.get("baths", "") or data.get("baths", ""))
        parking = str(hh.get("AASimpleparking", ""))
        estrato = str(data.get("stratum", "")).replace("Estrato", "").strip()
        
        images = data.get("propertyImages", [])
        image_url = images[0] if images else ""

        return {
            "code": code,
            "title": title.upper().strip(),
            "location": location.strip(),
            "price": price.strip(),
            "area": area.strip(),
            "bedrooms": bedrooms,
            "bathrooms": bathrooms,
            "parking": parking,
            "estrato": estrato,
            "image_url": image_url,
            "images": images,
            "link": link,
            "source": "alberto_alvarez",
            "description": "" # JSON might not have description easily? Add if available or empty.
        }

    async def _scrape_dom_details(self, page: Page, url: str, barrio_name: str) -> Optional[Property]:
        # Title
        title = "APARTAMENTO EN ARRIENDO"
        try:
            title_el = page.locator("h1").first
            if await title_el.count() > 0:
                title = await title_el.inner_text(timeout=2000)
        except:
            pass

        # Price
        price = ""
        try:
            price_el = page.locator(".property-price").first
            if await price_el.count() > 0:
                price = await price_el.inner_text(timeout=2000)
        except:
            try:
                price = await page.evaluate("() => document.querySelector('.price')?.innerText || ''")
            except:
                pass
       
        # Location
        location = ""
        try:
            location_el = page.locator(".property-location, .location, h1").first
            if await location_el.count() > 0:
                location = await location_el.inner_text(timeout=2000)
        except:
            pass

        if not location or location == title:
            location_match = re.search(r'EN\s+([A-Z\s]+)$', title, re.IGNORECASE)
            if location_match:
                location = location_match.group(1).strip()

        if not location:
             try:
                 barrio_text = await page.evaluate("""() => {
                     const elements = [...document.querySelectorAll('span, p, div, li')];
                     for (const el of elements) {
                         const text = el.innerText;
                         if (text.includes('Barrio:') || text.includes('Sector:')) {
                             return text;
                         }
                     }
                     return '';
                 }""")
                 if barrio_text:
                     location = barrio_text.replace('Barrio:', '').replace('Sector:', '').strip()
             except:
                 pass

        if not location:
             if barrio_name:
                location = barrio_name

        # Features
        all_text_elements = await page.evaluate("""
            () => {
                const results = [];
                const terms = ['m2', 'alcoba', 'baño', 'parqueadero', 'estrato'];
                const elements = document.querySelectorAll('span, p, div, li');
                for (const el of elements) {
                    if (el.children.length === 0) {
                        const text = el.innerText.toLowerCase();
                        if (terms.some(term => text.includes(term))) {
                            results.push(el.innerText.trim());
                        }
                    }
                }
                return results;
            }
        """)

        area, bedrooms, bathrooms, parking, estrato = "", "", "", "", ""

        for text in all_text_elements:
            lower_text = text.lower()
            if "m2" in lower_text and not area:
                area = text
            elif "alcoba" in lower_text and not bedrooms:
                bedrooms = text
            elif "baño" in lower_text and not bathrooms:
                bathrooms = text
            elif "parqueadero" in lower_text and not parking:
                parking = text
            elif "estrato" in lower_text and not estrato:
                estrato = text.replace("Estrato", "").strip()

        # Images
        images = []
        image_url = ""
        try:
            img_el = page.locator(".thumb img, .main-image img, .property-gallery img").first
            if await img_el.count() > 0:
                first_src = await img_el.get_attribute("src")
                if first_src:
                     if not first_src.startswith("http"):
                         first_src = ALBERTO_ALVAREZ_BASE_URL + first_src
                     image_url = first_src
                     images.append(first_src)
        except Exception:
            pass
        
        # Validation
        if "NO DISPONIBLE" in title.upper() or not price:
            return None

        # Clean numbers
        def extract_number(text):
            if not text: return ""
            match = re.search(r'(\d+)', text)
            return match.group(1) if match else ""

        # Code from URL
        code = ""
        try:
            code_match = re.search(r'/AA-(\d+)', url)
            if code_match:
                code = f"AA-{code_match.group(1)}"
        except:
            pass

        return {
            "code": code,
            "title": title.strip(),
            "location": location.strip(),
            "price": price.strip(),
            "area": extract_number(area) if extract_number(area) else area.strip(),
            "bedrooms": extract_number(bedrooms),
            "bathrooms": extract_number(bathrooms),
            "parking": extract_number(parking),
            "estrato": estrato.strip(),
            "image_url": image_url,
            "images": images,
            "link": url,
            "source": "alberto_alvarez",
            "description": "" # DOM scrape didn't implement description before?
        }


