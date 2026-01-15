import asyncio
from playwright.async_api import async_playwright
from typing import List, Dict
import re
import json

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

PRICE_RANGES = [
    {"min": 2500000, "max": 3500000}
]

SEARCH_URL_TEMPLATE = "https://albertoalvarez.com/inmuebles/arrendamientos/apartamento/envigado/envigado/{barrio}/?rentFrom={min_price}&rentTo={max_price}&roomsFrom=1&roomsTo=3"

async def scrape():
    """
    Scrapes Alberto Alvarez using dynamic barrio and price filters.
    """
    url_to_barrio = {}
    for barrio_name, barrio_slug in BARRIOS.items():
        for price_range in PRICE_RANGES:
            url = SEARCH_URL_TEMPLATE.format(
                barrio=barrio_slug,
                min_price=price_range["min"],
                max_price=price_range["max"]
            )
            print(f"Generating search URL for {barrio_name}: {url}")
            
            async with async_playwright() as p:
                browser = await p.chromium.launch(headless=True)
                context = await browser.new_context(
                    user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
                )
                page = await context.new_page()
                
                try:
                    links = await get_search_results_links(page, url)
                    for href in links:
                         if href not in url_to_barrio:
                             url_to_barrio[href] = barrio_name
                except Exception as e:
                    print(f"Error searching in {barrio_name}: {e}")
                finally:
                    await browser.close()
            
    all_links = list(url_to_barrio.keys())
    print(f"Found {len(all_links)} total properties across all barrios.")
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        # Parallelize detail scraping with a semaphore
        sem = asyncio.Semaphore(8)  # Scrape 8 pages concurrently
        
        async def scrape_task(url, barrio_name):
            async with sem:
                task_page = await context.new_page()
                try:
                    return await scrape_detail_page(task_page, url, barrio_name)
                except Exception as e:
                    print(f"Error scraping {url}: {e}")
                    return None
                finally:
                    await task_page.close()

        # Create tasks for each link
        tasks = [scrape_task(link, url_to_barrio[link]) for link in all_links[:50]]
        
        # Gather all results
        results_raw = await asyncio.gather(*tasks)
        
        # Filter out None results
        results = [r for r in results_raw if r]
        
        await browser.close()
    return results

async def get_search_results_links(page, url):
    """
    Navigates to a search URL and returns a list of property detail links.
    """
    print(f"Navigating to {url}...")
    try:
        await page.goto(url, wait_until="networkidle", timeout=30000)
    except:
        print(f"Timeout loading {url}, attempting partial content scrape")
    
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
    # Identify links to detail pages
    property_elements = await page.locator("a[href*='/inmuebles/detalle/']").all()
    for el in property_elements:
        href = await el.get_attribute("href")
        if href:
            if not href.startswith("http"):
                href = ALBERTO_ALVAREZ_BASE_URL + href
            links.append(href)
            
    return list(set(links))

async def scrape_detail_page(page, url, barrio_name=None):
    """
    Scrapes the detail page for a single property.
    """
    try:
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
        except:
             print(f"Timeout loading detail page {url}, attempting partial content scrape")
        
        # 1. Try to extract from Hidden JSON (Most Reliable)
        try:
            # The inspection script found data in textarea with class 'field-property'
            json_el = page.locator("textarea.field-property").first
            if await json_el.count() > 0:
                # Textareas usually store content in value property
                json_text = await json_el.input_value()
                if not json_text:
                    json_text = await json_el.inner_text()
                
                if json_text:
                    try:
                        data = json.loads(json_text)
                        
                        code = data.get("code", "")
                        title = f"{data.get('propertyType', 'Inmueble')} EN ARRIENDO"
                        
                        # Location Logic: Prefer sectorName > zoneName > fallback
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
                        
                        print(f"DEBUG: Successfully extracted JSON data for {url}")

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
                            "link": url,
                            "source": "alberto_alvarez"
                        }
                    except json.JSONDecodeError:
                        print(f"Failed to decode JSON for {url}")
        except Exception as e:
            print(f"JSON extraction failed for {url}, falling back to DOM scraping: {e}")

        # 2. DOM Scraping (Fallback)
        print(f"Fallback: DOM scraping for {url}")
        
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
            # Fallback for price
            try:
                price = await page.evaluate("() => document.querySelector('.price')?.innerText || ''")
            except:
                pass
       
        # Location extraction
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

        # Prioritize on-page location. Use fallback only if empty.
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
             # Last resort fallbacks
             if barrio_name:
                location = barrio_name
                print(f"DEBUG: url={url}, final_fallback_location={location}")

        # Features
        try:
            await page.wait_for_selector(".elementor-icon-box-title, .property-features, .features", timeout=5000)
        except:
            pass

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

        # Images (Gallery)
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
                
                # Try to open gallery
                if await img_el.is_visible():
                    try:
                        await img_el.click()
                        await page.wait_for_selector(".lb-image", state="visible", timeout=2000)
                        
                        for _ in range(25):
                            current_img = page.locator(".lb-image")
                            if await current_img.count() > 0:
                                src = await current_img.get_attribute("src")
                                if src:
                                    if not src.startswith("http"):
                                        src = ALBERTO_ALVAREZ_BASE_URL + src
                                    
                                    if src not in images:
                                        images.append(src)
                                    elif len(images) > 1 and src == images[0]:
                                        break
                            
                            next_btn = page.locator(".lb-next")
                            if await next_btn.is_visible():
                                await next_btn.click()
                                await asyncio.sleep(0.3)
                            else:
                                break
                    except:
                        pass
        except Exception as e:
            print(f"Error extracting images: {e}")

        # Extract code from URL
        code = ""
        try:
            code_match = re.search(r'/AA-(\d+)', url)
            if code_match:
                code = f"AA-{code_match.group(1)}"
        except:
            pass

        def extract_number(text):
            if not text:
                return ""
            match = re.search(r'(\d+)', text)
            return match.group(1) if match else ""

        bedrooms_clean = extract_number(bedrooms)
        bathrooms_clean = extract_number(bathrooms)
        parking_clean = extract_number(parking)
        area_clean = extract_number(area)

        # Final Validation
        if "NO DISPONIBLE" in title.upper() or not price:
            print(f"Skipping {url} - validation failed (Title: {title}, Price: {price})")
            return None

        return {
            "code": code,
            "title": title.strip(),
            "location": location.strip(),
            "price": price.strip(),
            "area": area_clean if area_clean else area.strip(),
            "bedrooms": bedrooms_clean,
            "bathrooms": bathrooms_clean,
            "parking": parking_clean,
            "estrato": estrato.strip(),
            "image_url": image_url,
            "images": images,
            "link": url,
            "source": "alberto_alvarez"
        }
    except Exception as e:
        print(f"Error scraping detail page {url}: {e}")
        return None
