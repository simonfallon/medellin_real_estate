import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()
        # Problematic URL
        url = "https://inmobiliariaproteger.com/apartamento-alquiler-san-marcos-envigado/9637563"
        print(f"Navigating to {url}...")
        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded")
        
        # Test finding Garaje
        # User says it's not interpretable or huge text
        
        # Details Extraction with Parent Fallback logic from scraper
        async def get_value(label_text):
            # Try specific list item structure common in real estate sites
            # <li><strong>Label:</strong> Value</li>
            # or <div><span>Label</span><span>Value</span></div>
            print(f"Looking for {label_text}...")
            try:
                # Strategy 1: Text contains label, get text
                # We iterate elements to find one that starts with label
                el = page.locator(f"xpath=//*[contains(text(), '{label_text}')]")
                count = await el.count()
                print(f"  Found {count} occurrences.")
                
                for i in range(count):
                    txt = await el.nth(i).inner_text()
                    print(f"   Occurence {i}: '{txt}'")
                    
                    # 1. Check if the element text itself has the value (e.g. "Alcoba: 3")
                    clean_txt = txt.replace(":", " ").replace(".", " ")
                    if any(c.isdigit() for c in txt) and len(txt) < 50:
                        val = txt.replace(label_text, "").replace(":", "").replace(".", "").strip()
                        print(f"   --> Derived value (Strategy 1): '{val}'")
                        
                    # 2. Check Parent Text (often "Label: Value" is in parent)
                    parent = el.nth(i).locator("xpath=..")
                    p_txt = await parent.inner_text()
                    print(f"   Parent Text: '{p_txt}'")
                    
                    # Same strategy, remove label and separators
                    val = p_txt.replace(label_text, "").replace(":", "").replace(".", "").strip()
                    if val:
                        print(f"   --> Derived value (Strategy 2): '{val}'")
            except Exception as e:
                print(e)
            return ""
            
        await get_value("Garaje")
        await get_value("Parqueadero")

        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
