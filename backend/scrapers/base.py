import asyncio
import re
from dataclasses import dataclass, field
from typing import List, Optional, Any, Set, Tuple
from playwright.async_api import async_playwright, Page, BrowserContext
from abc import ABC, abstractmethod
from .types import Property


@dataclass
class ScraperConfig:
    """Configuration for scraper behavior and performance tuning."""

    # Concurrency settings
    detail_concurrency: int = 4  # Concurrent detail page requests
    search_concurrency: int = 5  # Concurrent search page requests

    # Timeout settings (milliseconds)
    page_load_timeout: int = 15000  # Default page load timeout
    selector_timeout: int = 10000  # Default selector wait timeout

    # Page load strategy: "domcontentloaded" (faster) or "networkidle" (slower but more complete)
    search_load_state: str = "domcontentloaded"
    detail_load_state: str = "domcontentloaded"

    # Image filtering keywords to exclude
    image_exclusions: Set[str] = field(
        default_factory=lambda: {
            "logo",
            "icon",
            "whatsapp",
            "facebook",
            "twitter",
            "instagram",
            "button",
            "arrow",
        }
    )

    # Maximum images to collect per property
    max_images: int = 15


class BaseScraper(ABC):
    PRICE_RANGES = [{"min": 2500000, "max": 3500000}]

    # Default configuration - subclasses can override
    DEFAULT_CONFIG = ScraperConfig()

    def __init__(self, name: str, config: ScraperConfig = None):
        self.name = name
        self.config = config or ScraperConfig()
        self.semaphore = asyncio.Semaphore(self.config.detail_concurrency)
        self.search_semaphore = asyncio.Semaphore(self.config.search_concurrency)
        self.browser = None

    async def scrape(self) -> List[Property]:
        """
        Main entry point for the scraper.
        """
        all_properties = []

        async with async_playwright() as p:
            self.browser = await p.chromium.launch(headless=True)
            # Create a context with a realistic user agent
            context = await self.browser.new_context(
                user_agent="Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            )

            try:
                # 1. Get initial search parameters or URLs
                search_inputs = await self.get_search_inputs()

                # 2. Process search inputs to get property links
                all_links = await self.process_search_inputs(context, search_inputs)

                print(
                    f"[{self.name}] Found {len(all_links)} total properties to scrape."
                )

                # 3. Scrape details for each link
                tasks = [
                    self._scrape_single_property(context, link, meta)
                    for link, meta in all_links
                ]
                results = await asyncio.gather(*tasks)

                # Filter out None and add to final list
                for r in results:
                    if r:
                        all_properties.append(r)

            finally:
                await self.browser.close()
                self.browser = None

        return all_properties

    @abstractmethod
    async def get_search_inputs(self) -> List[Any]:
        """
        Returns a list of inputs to be used for search.
        Could be URLs, or tuples of (url, metadata).
        """
        pass

    async def process_search_inputs(
        self, context: BrowserContext, inputs: List[Any]
    ) -> List[Tuple[str, Any]]:
        """
        Default implementation for processing search inputs.
        Visits each search URL and extracts property links using _extract_links_from_search_page().

        Subclasses can override this method entirely or just override _extract_links_from_search_page()
        for site-specific link extraction logic.
        """
        all_links: List[Tuple[str, Any]] = []
        seen_links: Set[str] = set()

        async def process_single_search(url: str, metadata: Any):
            async with self.search_semaphore:
                page = await context.new_page()
                try:
                    links = await self._extract_links_from_search_page(page, url)
                    return [(link, metadata) for link in links]
                except Exception as e:
                    print(f"[{self.name}] Error processing search {url}: {e}")
                    return []
                finally:
                    await page.close()

        tasks = [process_single_search(url, meta) for url, meta in inputs]
        results_lists = await asyncio.gather(*tasks)

        for r_list in results_lists:
            for link, meta in r_list:
                if link not in seen_links:
                    seen_links.add(link)
                    all_links.append((link, meta))

        return all_links

    async def _extract_links_from_search_page(
        self, page: Page, search_url: str
    ) -> List[str]:
        """
        Extract property links from a search results page.

        Override this method in subclasses to implement site-specific link extraction.
        The default implementation raises NotImplementedError.
        """
        raise NotImplementedError(
            f"{self.__class__.__name__} must implement _extract_links_from_search_page()"
        )

    async def _scrape_single_property(
        self, context: BrowserContext, link: str, metadata: Any
    ) -> Optional[Property]:
        """
        Internal wrapper to handle semaphore and error catching.
        """
        async with self.semaphore:
            page = await context.new_page()
            try:
                return await self.extract_property_details(page, link, metadata)
            except Exception as e:
                print(f"[{self.name}] Error scraping {link}: {e}")
                return None
            finally:
                await page.close()

    @abstractmethod
    async def extract_property_details(
        self, page: Page, link: str, metadata: Any
    ) -> Optional[Property]:
        """
        Extracts details from a specific property page.
        """
        pass

    # =========================================================================
    # UTILITY METHODS - Shared across scrapers
    # =========================================================================

    async def navigate_and_wait(
        self,
        page: Page,
        url: str,
        load_state: str = None,
        wait_for_selector: str = None,
        timeout: int = None,
    ) -> bool:
        """
        Navigate to URL with configurable load strategy.

        Args:
            page: Playwright page object
            url: URL to navigate to
            load_state: Override config load state ("domcontentloaded" or "networkidle")
            wait_for_selector: Optional selector to wait for after load
            timeout: Override config timeout (milliseconds)

        Returns:
            True if navigation succeeded, False otherwise
        """
        load_state = load_state or self.config.detail_load_state
        timeout = timeout or self.config.page_load_timeout

        try:
            await page.goto(url)
            await page.wait_for_load_state(load_state, timeout=timeout)

            if wait_for_selector:
                try:
                    await page.wait_for_selector(
                        wait_for_selector, timeout=self.config.selector_timeout
                    )
                except Exception:
                    pass  # Selector timeout is non-fatal

            return True
        except Exception as e:
            print(f"[{self.name}] Navigation error for {url}: {e}")
            return False

    def filter_property_images(
        self, image_urls: List[str], additional_exclusions: Set[str] = None
    ) -> List[str]:
        """
        Filter out non-property images (logos, icons, social media, etc.).

        Args:
            image_urls: List of image URLs to filter
            additional_exclusions: Site-specific keywords to exclude

        Returns:
            Filtered list of unique image URLs
        """
        exclusions = self.config.image_exclusions.copy()
        if additional_exclusions:
            exclusions.update(additional_exclusions)

        filtered = []
        seen = set()

        for url in image_urls:
            if not url or not url.startswith("http"):
                continue
            if url in seen:
                continue

            url_lower = url.lower()
            if any(keyword in url_lower for keyword in exclusions):
                continue

            seen.add(url)
            filtered.append(url)

            if len(filtered) >= self.config.max_images:
                break

        return filtered

    async def extract_gps_from_mapbox(
        self, page: Page
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract GPS coordinates from Mapbox feedback link in page content.
        Pattern: apps.mapbox.com/feedback/...#/-75.58847/6.17802/15

        Returns:
            Tuple of (latitude, longitude) or (None, None)
        """
        try:
            page_content = await page.content()
            match = re.search(
                r"apps\.mapbox\.com/feedback/[^#]+#/(-?\d+\.\d+)/(-?\d+\.\d+)",
                page_content,
            )
            if match:
                longitude = float(match.group(1))
                latitude = float(match.group(2))
                # Validate coordinates are in reasonable range for Colombia
                if -80 <= longitude <= -66 and -5 <= latitude <= 13:
                    return latitude, longitude
        except Exception:
            pass
        return None, None

    async def extract_gps_from_window_var(
        self,
        page: Page,
        variable_name: str = None,
        lat_key: str = "latitude",
        lng_key: str = "longitude",
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract GPS coordinates from JavaScript window variables.

        Args:
            page: Playwright page object
            variable_name: Name of window variable (e.g., "VISUALINMUEBLE_INMUEBLE")
                          If None, checks window.latitude/longitude directly
            lat_key: Key for latitude in the variable object
            lng_key: Key for longitude in the variable object

        Returns:
            Tuple of (latitude, longitude) or (None, None)
        """
        try:
            if variable_name:
                js_data = await page.evaluate(f"() => window.{variable_name} || null")
                if js_data:
                    lat = js_data.get(lat_key)
                    lng = js_data.get(lng_key)
                    if lat is not None and lng is not None:
                        return float(lat), float(lng)
            else:
                # Check common window variable patterns
                coords = await page.evaluate(
                    """() => {
                    if (window.latitude && window.longitude) {
                        return { lat: window.latitude, lon: window.longitude };
                    }
                    if (window.lat && window.lng) {
                        return { lat: window.lat, lon: window.lng };
                    }
                    return null;
                }"""
                )
                if coords and coords.get("lat") and coords.get("lon"):
                    return float(coords["lat"]), float(coords["lon"])
        except Exception:
            pass
        return None, None

    async def extract_gps_from_google_maps(
        self, page: Page
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Extract GPS coordinates from Google Maps link.
        Pattern: google.com/maps...destination=6.17426,-75.5862

        Returns:
            Tuple of (latitude, longitude) or (None, None)
        """
        try:
            maps_link = page.locator("a[href*='google.com/maps']").first
            if await maps_link.count() > 0:
                href = await maps_link.get_attribute("href")
                match = re.search(r"destination=([\d.-]+),([\d.-]+)", href)
                if match:
                    lat = float(match.group(1))
                    lng = float(match.group(2))
                    return lat, lng
        except Exception:
            pass
        return None, None

    async def extract_gps_coordinates(
        self,
        page: Page,
        full_text: str = None,
        window_var: str = None,
        window_lat_key: str = "latitud",
        window_lng_key: str = "longitud",
    ) -> Tuple[Optional[float], Optional[float]]:
        """
        Try multiple methods to extract GPS coordinates.

        Args:
            page: Playwright page object
            full_text: Pre-extracted page text (for regex fallback)
            window_var: Optional window variable name to check first
            window_lat_key: Key for latitude in window variable
            window_lng_key: Key for longitude in window variable

        Returns:
            Tuple of (latitude, longitude) or (None, None)
        """
        lat, lng = None, None

        # Method 1: Window variable (if specified)
        if window_var:
            lat, lng = await self.extract_gps_from_window_var(
                page, window_var, window_lat_key, window_lng_key
            )

        # Method 2: Direct window properties
        if lat is None:
            lat, lng = await self.extract_gps_from_window_var(page)

        # Method 3: Mapbox link
        if lat is None:
            lat, lng = await self.extract_gps_from_mapbox(page)

        # Method 4: Google Maps link
        if lat is None:
            lat, lng = await self.extract_gps_from_google_maps(page)

        # Method 5: Regex in page text (if provided)
        if lat is None and full_text:
            match_lat = re.search(r'"latitud":\s*([\d.-]+)', full_text)
            match_lng = re.search(r'"longitud":\s*([\d.-]+)', full_text)
            if match_lat and match_lng:
                lat = float(match_lat.group(1))
                lng = float(match_lng.group(1))

        return lat, lng

    # Compiled regex patterns for common property features
    _PATTERN_BEDROOMS = re.compile(
        r"(\d+)\s*(?:Alcobas?|Habitaciones?|Ha\.)", re.IGNORECASE
    )
    _PATTERN_BATHROOMS = re.compile(r"(\d+)\s*(?:Baños?|Ba\.)", re.IGNORECASE)
    _PATTERN_PARKING = re.compile(r"(\d+)\s*(?:Garajes?|Parqueaderos?)", re.IGNORECASE)
    _PATTERN_AREA = re.compile(
        r"(?:Área\s*(?:cons|privada)?\s*:?\s*)?(\d+[\.,]?\d*)\s*(?:m2|m²)",
        re.IGNORECASE,
    )
    _PATTERN_ESTRATO = re.compile(r"Estrato\s*:?\s*(\d+)", re.IGNORECASE)
    _PATTERN_PRICE = re.compile(r"\$\s*([\d\.\,]+)")

    def extract_features_from_text(self, text: str) -> dict:
        """
        Extract property features from text using regex patterns.

        Args:
            text: Full page text or description text

        Returns:
            Dictionary with extracted features:
            - bedrooms, bathrooms, parking, area, estrato, price
        """
        features = {
            "bedrooms": "",
            "bathrooms": "",
            "parking": "",
            "area": "",
            "estrato": "",
            "price": "",
        }

        patterns = {
            "bedrooms": self._PATTERN_BEDROOMS,
            "bathrooms": self._PATTERN_BATHROOMS,
            "parking": self._PATTERN_PARKING,
            "area": self._PATTERN_AREA,
            "estrato": self._PATTERN_ESTRATO,
            "price": self._PATTERN_PRICE,
        }

        for key, pattern in patterns.items():
            match = pattern.search(text)
            if match:
                features[key] = match.group(1).strip()

        return features

    @staticmethod
    def normalize_url(href: str, base_url: str) -> str:
        """
        Convert relative URL to absolute.

        Args:
            href: URL that may be relative
            base_url: Base URL to prepend if href is relative

        Returns:
            Absolute URL
        """
        if href.startswith("http"):
            return href

        base = base_url.rstrip("/")
        if href.startswith("/"):
            return base + href
        else:
            return f"{base}/{href}"
