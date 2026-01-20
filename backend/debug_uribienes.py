"""
Debug script to inspect Uribienes property page and understand extraction issues.
This will help identify why bedrooms is extracting "2" instead of "3".
"""
import asyncio
from playwright.async_api import async_playwright


async def debug_uribienes_property():
    url = "https://uribienes.com/inmuebles/215327"
    print(f"Debugging property: {url}\n")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        page = await browser.new_page()

        await page.goto(url)
        await page.wait_for_load_state("domcontentloaded")

        # Wait for main content
        try:
            await page.wait_for_selector("h1", timeout=10000)
        except:
            pass

        print("=" * 80)
        print("DEBUGGING PROPERTY DETAILS EXTRACTION")
        print("=" * 80)

        # Run detailed JavaScript to see what's being found
        debug_info = await page.evaluate(
            r"""() => {
                const results = {};
                
                // Find all elements containing our search terms
                const searchTerms = ['Habitaciones', 'habitaciones', 'Baños', 'baños', 'Parqueadero', 'parqueadero', 'm²', 'm2'];
                
                searchTerms.forEach(term => {
                    const elements = Array.from(document.querySelectorAll('div, span'));
                    const matches = [];
                    
                    for (const el of elements) {
                        const text = el.innerText || '';
                        if (text.length < 100 && text.includes(term)) {
                            matches.push({
                                text: text,
                                length: text.length,
                                tag: el.tagName
                            });
                        }
                    }
                    
                    results[term] = matches;
                });
                
                // Also get the description text
                const desc = document.querySelector('.text-neutral-600.text-base');
                results['description'] = desc ? desc.innerText : 'Not found';
                
                return results;
            }"""
        )

        print("\n📊 SEARCH RESULTS FOR EACH TERM:\n")
        for term, matches in debug_info.items():
            if term == "description":
                print(f"\n📝 Description text:\n{matches}\n")
                continue

            print(f"\n🔍 Searching for '{term}':")
            if isinstance(matches, list):
                if len(matches) == 0:
                    print("  ❌ No matches found")
                else:
                    for i, match in enumerate(matches[:5]):  # Show first 5 matches
                        print(f"  Match {i+1}: [{match['tag']}] {match['text'][:80]}")
            print()

        # Now test the actual extraction logic
        print("=" * 80)
        print("TESTING ACTUAL EXTRACTION LOGIC")
        print("=" * 80)

        details = await page.evaluate(
            r"""() => {
                const getByText = (searchText) => {
                    const elements = Array.from(document.querySelectorAll('div, span'));
                    for (const el of elements) {
                        const text = el.innerText || '';
                        if (text.length < 100 && text.includes(searchText)) {
                            const parts = text.split(searchText);
                            if (parts.length > 1) {
                                const afterText = parts[1];
                                const match = afterText.match(/\d+/);
                                if (match) {
                                    return {
                                        value: match[0],
                                        fullText: text,
                                        afterText: afterText.substring(0, 50)
                                    };
                                }
                            }
                        }
                    }
                    return null;
                };
                
                return {
                    bedrooms: getByText('Habitaciones') || getByText('habitaciones') || getByText('Ha.'),
                    bathrooms: getByText('Baños') || getByText('baños') || getByText('Ba.'),
                    parking: getByText('Parqueadero') || getByText('parqueadero'),
                    area: getByText('m²') || getByText('m2')
                };
            }"""
        )

        print("\n🎯 EXTRACTED VALUES:\n")
        for field, data in details.items():
            if data:
                print(f"{field.upper()}:")
                print(f"  Value: {data['value']}")
                print(f"  Full text: {data['fullText']}")
                print(f"  After search term: {data['afterText']}")
            else:
                print(f"{field.upper()}: ❌ Not found")
            print()

        await browser.close()


if __name__ == "__main__":
    asyncio.run(debug_uribienes_property())
