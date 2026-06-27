import asyncio
from playwright.async_api import async_playwright
import os

async def main():
    async with async_playwright() as p:
        print("[*] Lancement de Chromium (Fenêtre réelle)...")
        chr_browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
        chr_context = await chr_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR'
        )
        page = await chr_context.new_page()
        await page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        # On force un token connu pour tester
        token = {"name": "PENSION", "address": "EenPHcGVx8s7vL3WfYgHq8k3J8u2Y5zN9pM4qR1sT6vX"} # Remplacez par une vraie adresse si besoin
        print(f"[*] Test SolanaTracker pour {token['name']}...")
        url = "https://www.solanatracker.io/rugcheck"
        
        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)
            
            # Prendre une capture d'écran de la page d'accueil
            await page.screenshot(path="st_home.png", full_page=False)
            print("[+] Capture d'écran 'st_home.png' sauvegardée.")
            
            # Trouver la barre de recherche
            search_input = page.locator("input[type='text']").first
            if not await search_input.count():
                search_input = page.locator("input[type='search']").first
                
            await search_input.wait_for(timeout=10000)
            await search_input.fill(token['address'])
            await page.keyboard.press("Enter")
            
            print("    -> Attente de 15 secondes pour le chargement...")
            await asyncio.sleep(15)
            
            # Prendre une capture d'écran du résultat
            await page.screenshot(path="st_result.png", full_page=True)
            print("[+] Capture d'écran 'st_result.png' sauvegardée.")
            
            # Lire le texte
            body_text = await page.evaluate("document.body.innerText")
            print("\n--- TEXTE DE LA PAGE SOLANATRACKER ---")
            print(body_text[:2000])
            print("--------------------------------------\n")
                
        except Exception as e:
            print(f"Error: {e}")
            
        await chr_browser.close()

if __name__ == "__main__":
    asyncio.run(main())
