import re
from typing import List, Tuple
from playwright.async_api import Page

from .base import BaseScraper, ScraperConfig
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
    "Zuñiga": "8579",
}


class ArrendamientosEnvigadoScraper(BaseScraper):
    def __init__(self, config: ScraperConfig = None):
        default_config = ScraperConfig(
            detail_concurrency=3,
            search_concurrency=5,
        )

        # Override price_ranges if custom config provided
        if config is not None:
            default_config.price_ranges = config.price_ranges

        super().__init__(name="Arrendamientos Envigado", config=default_config)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        """
        Generates the list of search URLs and their associated barrio names.
        """
        urls_to_scrape = []
        for barrio_name, barrio_id in BARRIOS.items():
            for price_range in self.PRICE_RANGES:
                url = SEARCH_URL_TEMPLATE.format(
                    barrio_id=barrio_id,
                    min_price=price_range["min"],
                    max_price=price_range["max"],
                )
                urls_to_scrape.append((url, barrio_name))
        return urls_to_scrape

    # process_search_inputs() is inherited from BaseScraper

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        """Extract property links from search results page."""
        await self.navigate_and_wait(
            page,
            search_url,
            load_state="domcontentloaded",
            wait_for_selector="a.link-footer-black",
        )

        links = []
        cards = await page.locator("a.link-footer-black").all()
        for card in cards:
            href = await card.get_attribute("href")
            if href and "inmueble.html" in href:
                href = self.normalize_url(href, ARRENDAMIENTOS_ENVIGADO_BASE_URL)
                links.append(href)

        return list(set(links))

    async def extract_property_details(
        self, page: Page, link: str, barrio_name: str
    ) -> Property:
        await self.navigate_and_wait(page, link, wait_for_selector="div.lux-grey.bold")

        # Scrape title
        title = ""
        try:
            title_el = page.locator("div.lux-grey.bold > span.bold").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
        except Exception:
            pass

        async def get_list_value(label):
            try:
                item = page.locator(
                    "li.list-group-item", has=page.locator("span", has_text=label)
                )
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
                description = await desc_header.locator(
                    "xpath=following-sibling::p[1]"
                ).inner_text()
        except:
            pass

        # Icon fallback
        async def get_value_by_icon(icon_keyword):
            try:
                xpath = (
                    f"//img[contains(@src, '{icon_keyword}')]/following-sibling::span"
                )
                el = page.locator(xpath).first
                if await el.count() > 0:
                    return await el.inner_text()
            except:
                pass
            return ""

        if not bedrooms:
            bedrooms = await get_value_by_icon("bed")
        if not bathrooms:
            bathrooms = await get_value_by_icon("bathtub")
        if not parking:
            parking = await get_value_by_icon("car")

        # Regex fallback from description
        if not bedrooms:
            match = re.search(
                r"(\d+)\s*(?:alcobas|habitaciones)", description, re.IGNORECASE
            )
            if match:
                bedrooms = match.group(1)

        if not bathrooms:
            match = re.search(r"(\d+)\s*baños", description, re.IGNORECASE)
            if match:
                bathrooms = match.group(1)

        if not parking:
            match = re.search(r"(\d+)\s*parqueaderos?", description, re.IGNORECASE)
            if match:
                parking = match.group(1)
            elif "parqueadero" in description.lower():
                parking = "1"

        # Extract images using filter utility
        raw_images = []
        carousel_imgs = await page.locator(".carousel-item img").all()
        for img in carousel_imgs:
            src = await img.get_attribute("src")
            if src:
                raw_images.append(src)

        images = self.filter_property_images(
            raw_images, additional_exclusions={"logo-ae-new.png", "assets/"}
        )

        # Extract code from URL
        code = ""
        try:
            code_match = re.search(r"(?:codigo|inmueble)=(\d+)", link)
            if code_match:
                code = code_match.group(1)
        except:
            pass

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
            "source": "arrendamientos_envigado",
            "latitude": None,
            "longitude": None,
        }
