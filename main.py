import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_MIN = 80
SCORE_MAX = 100

async def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
        print("[+] Message Telegram envoyé.")
    except:
        pass

async def get_new_solana_tokens(page):
    print("[*] Scraping DexScreener avec l'URL magique (0-72h)...")
    url = "https://dexscreener.com/solana?rankBy=trendingScoreH6&order=desc&minLiq=20000&minMarketCap=100000&maxAge=72&profile=1"
    await page.goto(url, wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    
    tokens = []
    seen_addresses = set()
    last_count = 0
    stable_scrolls = 0
    
    print("[*] Scroll mémorisé pour collecter tous les tokens filtrés...")
    for scroll_count in range(50):
        rows = await page.query_selector_all("a[href*='/solana/']")
        
        for row in rows:
            try:
                href = await row.get_attribute("href")
                if href and "/solana/" in href:
                    address = href.split("/solana/")[1].split("?")[0]
                    
                    if len(address) >= 32 and address not in seen_addresses:
                        seen_addresses.add(address)
                        row_text = await row.inner_text()
                        text_parts = row_text.split('\n')
                        name = text_parts[1] if len(text_parts) > 1 else "Unknown"
                        
                        print(f"    -> [GARDÉ] {name} | {address[:8]}...")
                        tokens.append({"name": name, "address": address})
            except:
                continue
                
        if len(tokens) >= 50:
            break
            
        if len(seen_addresses) == last_count:
            stable_scrolls += 1
            if stable_scrolls > 10:
                break
        else:
            stable_scrolls = 0
        last_count = len(seen_addresses)
        
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.5)

    print(f"[+] Found {len(tokens)} tokens valides au total.")
    return tokens

async def check_rugchecker(page, token):
    print(f"[*] Vérification RugChecker pour {token['name']}...")
    url = "https://rugchecker.com/fr"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        # Fermer le pop-up "Get Started" s'il apparaît
        try:
            get_started_btn = page.locator("button:has-text('Get Started')")
            await get_started_btn.click(timeout=3000)
            await asyncio.sleep(2)
        except:
            pass
            
        # Trouver la barre de recherche
        search_input = page.locator("input[placeholder*='Adresse du jeton']")
        if not await search_input.count():
            search_input = page.locator("input[type='text']").first
            
        await search_input.wait_for(timeout=10000)
        
        # Vider la barre de recherche avant de taper
        await search_input.fill("")
        await asyncio.sleep(1)
        await search_input.fill(token['address'])
        
        # Cliquer sur "Rug Check"
        check_button = page.locator("button:has-text('Rug Check')")
        await check_button.click()
        
        print("    -> Attente du calcul du score...")
        await asyncio.sleep(12) # Laisser 12 secondes pour l'analyse
        
        body_text = await page.evaluate("document.body.innerText")
        
        # NOUVEAU : Le score est sous "Analyse de sécurité du jeton" sur la ligne d'après
        match = re.search(r'Analyse de sécurité du jeton\s*(\d{1,3})', body_text, re.IGNORECASE)
        
        if match:
            score = int(match.group(1))
            print(f"    -> Score trouvé: {score}")
            return score
        else:
            # Fallback au cas où
            match_fallback = re.search(r'(\d{1,3})\s*RISQUE', body_text, re.IGNORECASE)
            if match_fallback:
                score = int(match_fallback.group(1))
                print(f"    -> Score (fallback) trouvé: {score}")
                return score
                
            print("    -> Score non trouvé sur la page.")
            return 0
            
    except Exception as e:
        print(f"    -> Erreur lors de la vérification: {e}")
        return 0

async def main():
    delay = random.uniform(1, 5)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    async with async_playwright() as p:
        # 1. Chromium en mode Fenêtre réelle pour tromper Cloudflare
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
        await dex_page.close() # On ferme la page DexScreener pour libérer de la mémoire
        
        if not tokens:
            print("[-] Aucun token trouvé.")
            return

        # 2. Nouvelle page pour RugChecker
        rug_page = await chr_context.new_page()
        await rug_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            score = await check_rugchecker(rug_page, token)
            
            # RÈGLE : Si le score est entre 80 et 100
            if SCORE_MIN <= score <= SCORE_MAX:
                found_good_coin = True
                message = f"🚀 <b>High Score Token Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: Score de {score}/100 sur RugChecker"
                await send_telegram_message(message)
            await asyncio.sleep(2)
            
        if not found_good_coin:
            print("[-] Aucun token n'a eu un score entre 80 et 100 cette fois.")
            
        await chr_browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
