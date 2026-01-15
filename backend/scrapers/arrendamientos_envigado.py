import asyncio
from playwright.async_api import async_playwright
import re
from typing import List, Dict

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

async def scrape():
    """
    Scrapes Arrendamientos Envigado with the pre-defined filter combinations.
    """
    urls_to_scrape = []
    
    for barrio_name, barrio_id in BARRIOS.items():
        for price_range in PRICE_RANGES:
            url = SEARCH_URL_TEMPLATE.format(
                barrio_id=barrio_id,
                min_price=price_range["min"],
                max_price=price_range["max"]
            )
            # Store metadata to know what we are scraping
            urls_to_scrape.append((url, barrio_name))
            
    print(f"Generated {len(urls_to_scrape)} URLs to scrape for Arrendamientos Envigado.")
    
    all_results = []
    
    # Use a semaphore to limit concurrent browser contexts/tabs
    sem = asyncio.Semaphore(3) # scrape 3 URLs at a time
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        
        async def scrape_single_search_url(url_data):
            url, barrio_name = url_data
            async with sem:
                try:
                    print(f"Starting search for: {url} ({barrio_name})")
                    context = await browser.new_context(
                        user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                    )
                    page = await context.new_page()
                    # Pass the page to a helper that handles the list page + details
                    results = await process_search_page(page, url, barrio_name)
                    await context.close()
                    return results
                except Exception as e:
                    print(f"Error scraping search URL {url}: {e}")
                    return []

        tasks = [scrape_single_search_url(data) for data in urls_to_scrape]
        results_lists = await asyncio.gather(*tasks)
        
        # Deduplicate results by link
        results_dict = {}
        for r_list in results_lists:
            for item in r_list:
                # Use link as key to ensure uniqueness
                results_dict[item['link']] = item
        
        all_results = list(results_dict.values())
            
        await browser.close()
        
    return all_results

async def process_search_page(page, search_url, barrio_name):
    """
    Navigates to a search URL, extracts property links, and scraps their details.
    """
    await page.goto(search_url)
    try:
        await page.wait_for_load_state("networkidle", timeout=10000)
    except:
        pass
    
    # Wait for results or no results
    try:
        # Check for results container or specific link class
        await page.wait_for_selector("a.link-footer-black", timeout=10000)
    except:
        print(f"No results or timeout for {search_url}")
        return []

    # Extract all property links
    links = []
    # Get all matching elements
    cards = await page.locator("a.link-footer-black").all()
    for card in cards:
        href = await card.get_attribute("href")
        if href and "inmueble.html" in href:
            if not href.startswith("http"):
                href = ARRENDAMIENTOS_ENVIGADO_BASE_URL + href.lstrip("/")
            links.append(href)
    
    # Remove duplicates immediately if any
    links = list(set(links))
    print(f"Found {len(links)} properties on {search_url}")
    
    # We'll use the same context to create new pages for details
    context = page.context
    
    async def scrape_details_with_new_page(link):
        detail_page = await context.new_page()
        try:
            return await scrape_page_details(detail_page, link, barrio_name)
        except Exception as e:
            print(f"Error scraping details for {link}: {e}")
            return None
        finally:
            await detail_page.close()

    tasks = [scrape_details_with_new_page(link) for link in links]
    results = await asyncio.gather(*tasks)
    
    # Filter out None results
    return [r for r in results if r]

async def scrape_page_details(page, url, barrio_name):
    await page.goto(url)
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
            # Find span with label, get parent li, find value span
            # Structure: li > div > span(label) ... span(value)
            # XPath: //span[contains(text(), 'Label')]/../following-sibling::span
            # Or simpler: locate li that contains label
            item = page.locator("li.list-group-item", has=page.locator(f"span", has_text=label))
            if await item.count() > 0:
                # The value is usually in the second span or specific class
                # Based on previous code: await item.locator("span").nth(1).inner_text()
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
            # Assumes the next p tag has the text
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
            # Filter out the recurring logo/watermark image and ensure it's a valid property image
            if "logo-ae-new.png" in src or "assets/" in src:
                continue
            images.append(src)
            
    # Use the reliable barrio_name passed from the search context
    location = barrio_name

    # Extract code from URL (e.g., codigo=12345 or inmueble=12345)
    code = ""
    try:
        code_match = re.search(r'(?:codigo|inmueble)=(\d+)', url)
        if code_match:
            code = code_match.group(1)
    except:
        pass

    return {
        "code": code,
        "title": title.strip() if title else "",
        "location": location.strip(),
        "price": price.strip() if price else "",
        "area": area.strip() if area else "",
        "estrato": estrato.strip() if estrato else "",
        "bedrooms": bedrooms.strip() if bedrooms else "",
        "bathrooms": bathrooms.strip() if bathrooms else "",
        "parking": parking.strip() if parking else "",
        "description": description.strip(),
        "images": images,
        "link": url,
        "source": "arrendamientos_envigado"
    }
