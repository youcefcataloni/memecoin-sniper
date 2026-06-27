import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_MAX = 4 # De 0 à 4/10

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
    print("[*] Scraping DexScreener (3 à 7 jours)...")
    url = "https://dexscreener.com/solana?rankBy=pairAge&order=asc&minLiq=20000&minMarketCap=100000&minAge=72&maxAge=168&profile=1"
    
    rows = []
    for attempt in range(3):
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        rows = await page.query_selector_all("a[href*='/solana/']")
        if len(rows) > 0:
            print(f"[+] Cloudflare nous a laissé passer (Tentative {attempt+1}).")
            break
        print(f"[*] Bloqué par Cloudflare. Nouvelle tentative dans 10s...")
        await asyncio.sleep(10)
        
    if not rows:
        return []
    
    tokens = []
    seen_addresses = set()
    
    print("[*] Scroll mémorisé pour collecter les 15 premiers tokens...")
    for scroll_count in range(20):
        rows = await page.query_selector_all("a[href*='/solana/']")
        
        for row in rows:
            try:
                href = await row.get_attribute("href")
                if href and "/solana/" in href:
                    pair_address = href.split("/solana/")[1].split("?")[0]
                    
                    if len(pair_address) >= 32 and pair_address not in seen_addresses:
                        seen_addresses.add(pair_address)
                        
                        # NOUVEAU : On récupère TOUS les liens de la ligne
                        links = await row.eval_on_selector_all('a', '(elements) => elements.map(e => e.href)')
                        token_address = None
                        
                        for link in links:
                            if "/solana/" in link:
                                addr = link.split("/solana/")[1].split("?")[0]
                                # Si l'adresse est différente de l'adresse de la paire, c'est l'adresse du Token !
                                if len(addr) >= 32 and addr != pair_address:
                                    token_address = addr
                                    break
                        
                        # Si on n'a pas trouvé d'adresse différente, on garde l'adresse de la paire
                        if not token_address:
                            token_address = pair_address
                            
                        row_text = await row.inner_text()
                        text_parts = row_text.split('\n')
                        name = text_parts[1] if len(text_parts) > 1 else "Unknown"
                        
                        print(f"    -> [GARDÉ 3-7j] {name} | Token: {token_address[:8]}...")
                        tokens.append({"name": name, "address": token_address})
                        
                        if len(tokens) >= 15:
                            return tokens
            except:
                continue
            
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.5)

    print(f"[+] Found {len(tokens)} tokens valides au total.")
    return tokens

async def check_solanatracker(page, token):
    print(f"[*] Vérification SolanaTracker pour {token['name']}...")
    url = "https://www.solanatracker.io/rugcheck"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5)
        
        search_input = page.locator("input[placeholder*='address' i], input[placeholder*='token' i]").first
        if not await search_input.count():
            search_input = page.locator("input[type='text']").nth(1)
            
        await search_input.wait_for(timeout=10000)
        await search_input.fill(token['address'])
        
        analyze_btn = page.locator("button:has-text('Analyze')")
        if await analyze_btn.count():
            await analyze_btn.click()
        else:
            await page.keyboard.press("Enter")
        
        print("    -> Attente du chargement du score...")
        try:
            await page.wait_for_function("() => document.body.innerText.includes('/10')", timeout=15000)
        except:
            print("    -> Score /10 non trouvé après 15s.")
            return 99
            
        body_text = await page.evaluate("document.body.innerText")
        
        match = re.search(r'\((\d{1,2})\s*/\s*10\)', body_text)
        if not match:
            match = re.search(r'(\d{1,2})\s*/\s*10', body_text)
            
        if match:
            score = int(match.group(1))
            print(f"    -> Score trouvé: {score}/10")
            return score
        else:
            print("    -> Score non trouvé.")
            return 99
            
    except Exception as e:
        print(f"    -> Erreur: {e}")
        return 99

async def main():
    delay = random.uniform(1, 5)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

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

        st_page = await chr_context.new_page()
        await st_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            score = await check_solanatracker(st_page, token)
            
            # RÈGLE : Si le score est entre 0 et 4/10
            if 0 <= score <= SCORE_MAX:
                found_good_coin = True
                message = f"✅ <b>Token Faible Risque Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: Score de {score}/10 sur SolanaTracker"
                await send_telegram_message(message)
            
            await asyncio.sleep(3)
            
        if not found_good_coin:
            print("[-] Aucun token n'a eu un score <= 4/10 cette fois.")
            
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
