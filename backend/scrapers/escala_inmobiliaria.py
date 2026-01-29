import re
from typing import List, Tuple, Optional
from playwright.async_api import Page

from .base import BaseScraper, ScraperConfig
from .types import Property

# Constants
BASE_URL = "https://escalainmobiliaria.com.co/"
SEARCH_URL_TEMPLATE = "https://escalainmobiliaria.com.co/inmuebles/g/arriendo/t/apartamentos/c/envigado/n/{barrios_slug}/?precioMin={min_price}&precioMax={max_price}"

# Normalized keys to standardized display names
BARRIOS_LIST = [
    "El Portal",
    "Jardines",
    "La Abadia",
    "La Frontera",
    "La Magnolia",
    "Las Flores",
    "Las Vegas",
    "Loma Benedictinos",
    "Pontevedra",
    "San Marcos",
    "Villagrande",
    "Zuñiga",
]


class EscalaInmobiliariaScraper(BaseScraper):
    def __init__(self, config: ScraperConfig = None):
        default_config = ScraperConfig(
            detail_concurrency=3,
            search_concurrency=5,
            image_exclusions=ScraperConfig().image_exclusions
            | {"openstreetmap", "psenuevo", "simicrm"},
        )

        # Override price_ranges if custom config provided
        if config is not None:
            default_config.price_ranges = config.price_ranges

        super().__init__(name="Escala Inmobiliaria", config=default_config)

    async def get_search_inputs(self) -> List[Tuple[str, str]]:
        """
        Generates the single concatenated search URL.
        Returns a list with one item: (url, "Mixed")
        The specific barrio for each property will be extracted later.
        """
        # Create slug: replace spaces with _, join with -o-
        slugs = [b.lower().replace(" ", "_") for b in BARRIOS_LIST]
        barrios_slug = "-o-".join(slugs)

        inputs = []
        for price_range in self.PRICE_RANGES:
            url = SEARCH_URL_TEMPLATE.format(
                barrios_slug=barrios_slug,
                min_price=price_range["min"],
                max_price=price_range["max"],
            )
            inputs.append((url, "Mixed"))

        return inputs

    # process_search_inputs() is inherited from BaseScraper

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        await self.navigate_and_wait(
            page, search_url, wait_for_selector="a.inmueblelink"
        )

        links = []
        property_links = await page.locator("a.inmueblelink").all()

        for link_el in property_links:
            href = await link_el.get_attribute("href")
            if href:
                href = self.normalize_url(href, BASE_URL.rstrip("/"))
                links.append(href)

        return list(set(links))

    async def extract_property_details(
        self, page: Page, link: str, _meta_barrio: str
    ) -> Optional[Property]:
        await self.navigate_and_wait(page, link, wait_for_selector="h1")

        # Extract title
        title = ""
        try:
            title_el = page.locator("h1").first
            if await title_el.count() > 0:
                title = await title_el.inner_text()
            else:
                title = await page.title()
        except:
            pass

        # Determine location from URL
        location = "Envigado"  # Default
        normalized_link = link.lower()
        for barrio in BARRIOS_LIST:
            slug = barrio.lower().replace(" ", "-")
            slug_underscore = barrio.lower().replace(" ", "_")
            if slug in normalized_link or slug_underscore in normalized_link:
                location = barrio
                break

        # Extract features from full page text
        price = ""
        area = ""
        bedrooms = ""
        bathrooms = ""
        parking = ""
        estrato = ""
        description = ""

        # Price from specific selector
        try:
            price_el = page.locator(".precio-inmueble, .price").first
            if await price_el.count() > 0:
                price = await price_el.inner_text()
        except:
            pass

        # Get full text and extract features
        full_text = await page.locator("body").inner_text()

        if not price:
            price_match = re.search(r"\$\s*([\d\.\,]+)", full_text)
            if price_match:
                price = price_match.group(1)

        # Use base class feature extraction
        features = self.extract_features_from_text(full_text)
        area = features["area"] or area
        bedrooms = features["bedrooms"] or bedrooms
        bathrooms = features["bathrooms"] or bathrooms
        parking = features["parking"] or parking
        estrato = features["estrato"] or estrato

        # Description
        try:
            desc_el = page.locator(
                "#descripcion, .descripcion, .description, .detalle-inmueble"
            ).first
            if await desc_el.count() > 0:
                description = await desc_el.inner_text()
            else:
                desc_label = (
                    page.locator("h2, h3, strong, b")
                    .filter(has_text="Descripción")
                    .first
                )
                if await desc_label.count() > 0:
                    description = await desc_label.locator(
                        "xpath=following-sibling::*[1]"
                    ).inner_text()
        except:
            pass

        # Images using filter utility
        images = []
        try:
            try:
                await page.wait_for_selector(".itemslider", timeout=4000)
            except:
                pass

            raw_images = []
            imgs = await page.locator(".itemslider").all()
            for img in imgs:
                src = await img.get_attribute("src")
                if src:
                    raw_images.append(src)

            images = self.filter_property_images(raw_images)
        except:
            pass

        # Code extraction from URL
        code = ""
        match = re.search(r"[_-](\d+-\d+|\d+)$", link.rstrip("/"))
        if match:
            code = match.group(1)

        # GPS Location using base utilities
        latitude, longitude = await self.extract_gps_coordinates(
            page,
            full_text=full_text,
            window_var="VISUALINMUEBLE_INMUEBLE",
        )

        return {
            "code": code,
            "title": title.strip(),
            "location": location,
            "price": price.strip() if price else "",
            "area": area.strip() if area else "",
            "estrato": estrato.strip() if estrato else "",
            "bedrooms": bedrooms.strip() if bedrooms else "",
            "bathrooms": bathrooms.strip() if bathrooms else "",
            "parking": parking.strip() if parking else "",
            "description": description.replace("Descripción", "").strip(),
            "images": images,
            "image_url": images[0] if images else "",
            "link": link,
            "source": "escala_inmobiliaria",
            "latitude": latitude,
            "longitude": longitude,
        }
