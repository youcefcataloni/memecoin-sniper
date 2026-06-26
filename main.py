import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

async def get_new_solana_tokens(page):
    print("[*] Scraping DexScreener avec l'URL magique (0-72h)...")
    url = "https://dexscreener.com/solana?rankBy=trendingScoreH6&order=desc&minLiq=20000&minMarketCap=100000&maxAge=72&profile=1"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    
    tokens = []
    rows = await page.query_selector_all("a[href*='/solana/']")
    for row in rows[:10]:
        try:
            href = await row.get_attribute("href")
            if href and "/solana/" in href:
                address = href.split("/solana/")[1].split("?")[0]
                if len(address) >= 32:
                    row_text = await row.inner_text()
                    text_parts = row_text.split('\n')
                    name = text_parts[1] if len(text_parts) > 1 else "Unknown"
                    tokens.append({"name": name, "address": address})
                    if len(tokens) >= 1:
                        return tokens
        except:
            continue
    return tokens

async def main():
    async with async_playwright() as p:
        print("[*] Lancement de Chromium (Fenêtre réelle)...")
        chr_browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
        chr_context = await chr_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR'
        )
        dex_page = await chr_context.new_page()
        await dex_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        tokens = await get_new_solana_tokens(dex_page)
        await dex_page.close()
        
        if not tokens:
            print("[-] Aucun token trouvé.")
            return

        token = tokens[0]
        print(f"[*] Test RugChecker pour {token['name']} ({token['address'][:8]}...)")
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
