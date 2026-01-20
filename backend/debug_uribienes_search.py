"""
Debug script to inspect Uribienes search page and understand why no links are found.
"""
import asyncio
from playwright.async_api import async_playwright


async def debug_search_page():
    url = "https://uribienes.com/inmuebles/arriendo?city=5266&neighborhood=Jardines+&type=1&pcmin=2500000&pcmax=3500000&minarea=50&maxarea=100"
    print(f"Debugging search page: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url)

        print("=" * 80)
        print("WAITING FOR PAGE TO LOAD")
        print("=" * 80)

        # Try different wait strategies
        try:
            print("\n1. Waiting for selector 'a[href^=\"/inmuebles/\"]'...")
            await page.wait_for_selector('a[href^="/inmuebles/"]', timeout=10000)
            print("   ✓ Selector found!")
        except Exception as e:
            print(f"   ✗ Timeout: {e}")

        # Wait a bit more for dynamic content
        print("\n2. Waiting 3 seconds for dynamic content...")
        await page.wait_for_timeout(3000)

        # Check what's actually on the page
        print("\n" + "=" * 80)
        print("ANALYZING PAGE CONTENT")
        print("=" * 80)

        page_info = await page.evaluate(
            r"""() => {
                // Count all links
                const allLinks = document.querySelectorAll('a');
                const inmuebleLinks = document.querySelectorAll('a[href^="/inmuebles/"]');
                
                // Get sample of links
                const sampleLinks = Array.from(inmuebleLinks).slice(0, 10).map(a => ({
                    href: a.getAttribute('href'),
                    text: a.innerText.substring(0, 50),
                    classes: a.className
                }));
                
                // Check for property cards
                const cards = document.querySelectorAll('.card, [class*="property"], [class*="listing"]');
                
                // Check page structure
                const bodyText = document.body.innerText.substring(0, 500);
                
                return {
                    totalLinks: allLinks.length,
                    inmuebleLinks: inmuebleLinks.length,
                    sampleLinks: sampleLinks,
                    cardCount: cards.length,
                    bodyPreview: bodyText,
                    title: document.title
                };
            }"""
        )

        print("\n📊 Page Statistics:")
        print(f"   Title: {page_info['title']}")
        print(f"   Total links: {page_info['totalLinks']}")
        print(f"   Links starting with '/inmuebles/': {page_info['inmuebleLinks']}")
        print(f"   Card elements: {page_info['cardCount']}")

        print("\n📝 Body preview:")
        print(page_info["bodyPreview"])

        if page_info["sampleLinks"]:
            print("\n🔗 Sample links found:")
            for i, link in enumerate(page_info["sampleLinks"][:5]):
                print(f"   {i+1}. {link['href']} - {link['text'][:40]}")
        else:
            print("\n❌ No property links found!")

        # Test the actual extraction logic
        print("\n" + "=" * 80)
        print("TESTING EXTRACTION LOGIC")
        print("=" * 80)

        links = await page.evaluate(
            r"""() => {
                const anchors = Array.from(document.querySelectorAll('a[href^="/inmuebles/"]'));
                const propertyLinks = [];
                
                for (const a of anchors) {
                    const href = a.getAttribute('href');
                    if (href && /\/inmuebles\/\d+$/.test(href)) {
                        propertyLinks.push(href);
                    }
                }
                
                return [...new Set(propertyLinks)];
            }"""
        )

        print(f"\n✅ Extracted {len(links)} unique property links")
        if links:
            print("\nFirst 5 links:")
            for link in links[:5]:
                print(f"   - {link}")

        # Take a screenshot for debugging
        await page.screenshot(path="/tmp/uribienes_search_debug.png")
        print("\n📸 Screenshot saved to /tmp/uribienes_search_debug.png")

        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_search_page())
