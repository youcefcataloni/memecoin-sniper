import asyncio
from playwright.async_api import async_playwright

async def main():
    async with async_playwright() as p:
        print("[*] Lancement de Chromium (Fenêtre réelle)...")
        chr_browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
        chr_context = await chr_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR'
        )
        
        # On force un token connu (BONK) pour tester RugChecker directement
        token = {"name": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"}
        print(f"[*] Test RugChecker direct pour {token['name']}...")
        url = "https://rugchecker.com/fr"
        
        rug_page = await chr_context.new_page()
        await rug_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        try:
            await rug_page.goto(url, wait_until="domcontentloaded", timeout=30000)
            await asyncio.sleep(3)
            
            # Fermer le pop-up "Get Started"
            try:
                get_started_btn = rug_page.locator("button:has-text('Get Started')")
                await get_started_btn.click(timeout=3000)
                print("[+] Pop-up 'Get Started' fermé.")
                await asyncio.sleep(2)
            except:
                print("[*] Pas de pop-up.")
                
            # Taper l'adresse
            search_input = rug_page.locator("input[placeholder*='Adresse du jeton']")
            if not await search_input.count():
                search_input = rug_page.locator("input[type='text']").first
                
            await search_input.wait_for(timeout=10000)
            await search_input.fill(token['address'])
            
            # Cliquer sur "Rug Check"
            check_button = rug_page.locator("button:has-text('Rug Check')")
            await check_button.click()
            print("[*] Clic sur 'Rug Check' effectué. Attente de 15 secondes...")
            
            await asyncio.sleep(15)
            
            # Prendre une capture d'écran
            await rug_page.screenshot(path="rugchecker_result.png", full_page=True)
            print("[+] Capture d'écran 'rugchecker_result.png' sauvegardée.")
            
            # Lire le texte
            body_text = await rug_page.evaluate("document.body.innerText")
            print("\n--- TEXTE DE LA PAGE RUGCHECKER ---")
            print(body_text[:2000])
            print("------------------------------------\n")
                
        except Exception as e:
            print(f"Error: {e}")
            
        await chr_browser.close()

if __name__ == "__main__":
    asyncio.run(main())
