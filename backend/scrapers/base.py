import asyncio
from typing import List, Dict, Optional, Any
from playwright.async_api import async_playwright, Page, BrowserContext
from abc import ABC, abstractmethod
from .types import Property

class BaseScraper(ABC):
    PRICE_RANGES = [
        {"min": 2500000, "max": 3500000}
    ]

    def __init__(self, name: str, concurrency: int = 4):
        self.name = name
        self.semaphore = asyncio.Semaphore(concurrency)
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
                
                print(f"[{self.name}] Found {len(all_links)} total properties to scrape.")
                
                # 3. Scrape details for each link
                tasks = [self._scrape_single_property(context, link, meta) for link, meta in all_links]
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

    @abstractmethod
    async def process_search_inputs(self, context: BrowserContext, inputs: List[Any]) -> List[tuple[str, Any]]:
        """
        Takes the search inputs and returns a list of (property_url, metadata) tuples.
        """
        pass

    async def _scrape_single_property(self, context: BrowserContext, link: str, metadata: Any) -> Optional[Property]:
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
    async def extract_property_details(self, page: Page, link: str, metadata: Any) -> Optional[Property]:
        """
        Extracts details from a specific property page.
        """
        pass
