import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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

def get_real_token_address(pair_address):
    """Interroge l'API DexScreener pour trouver la vraie adresse du token à partir de l'adresse de la paire"""
    try:
        res = requests.get(f"https://api.dexscreener.com/latest/dex/pairs/solana/{pair_address}", timeout=5)
        data = res.json()
        if data.get('pair'):
            return data['pair'].get('baseToken', {}).get('address')
    except:
        pass
    return None

async def get_new_solana_tokens(page):
    print("[*] Scraping DexScreener (Moins de 24h)...")
    # Filtre 0 à 24h
    url = "https://dexscreener.com/solana?rankBy=pairAge&order=asc&minLiq=20000&minMarketCap=100000&maxAge=24&profile=1"
    
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
    seen_pairs = set()
    
    print("[*] Scroll mémorisé pour collecter les 25 premiers tokens...")
    for scroll_count in range(30): # Plus de scrolls pour trouver 25 tokens
        rows = await page.query_selector_all("a[href*='/solana/']")
        
        for row in rows:
            try:
                href = await row.get_attribute("href")
                if href and "/solana/" in href:
                    pair_address = href.split("/solana/")[1].split("?")[0]
                    
                    if len(pair_address) >= 32 and pair_address not in seen_pairs:
                        seen_pairs.add(pair_address)
                        
                        real_token_addr = get_real_token_address(pair_address)
                        if not real_token_addr:
                            continue
                            
                        row_text = await row.inner_text()
                        text_parts = row_text.split('\n')
                        name = text_parts[1] if len(text_parts) > 1 else "Unknown"
                        
                        print(f"    -> [GARDÉ <24h] {name} | Token: {real_token_addr[:8]}...")
                        tokens.append({"name": name, "address": real_token_addr})
                        
                        # NOUVEAU : On s'arrête à 25 tokens
                        if len(tokens) >= 25:
                            return tokens
            except:
                continue
            
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        await asyncio.sleep(1.5)

    print(f"[+] Found {len(tokens)} tokens valides au total.")
    return tokens

async def check_trenchradar(page, token):
    print(f"[*] Vérification TrenchRadar pour {token['name']}...")
    url = "https://www.trenchradar.net/app?chain=solana"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=60000)
        
        # Trouver la barre de recherche
        search_input = await page.wait_for_selector("input[type='text'], input[type='search'], input[placeholder*='search' i], input[placeholder*='address' i]", timeout=15000)
        
        if search_input:
            await search_input.fill(token['address'])
            await page.keyboard.press("Enter")
            
            print("    -> Attente du chargement de TrenchRadar...")
            await asyncio.sleep(10)
            
            body_text = await page.evaluate("document.body.innerText")
            body_lower = body_text.lower()
            
            # NOUVEAU : On cherche le mot "LOW" (comme le Wash Risk LOW en vert)
            if "low risk" in body_lower or ("wash risk" in body_lower and "low" in body_lower):
                print("    -> Statut 'LOW' (Vert) trouvé !")
                return True
            else:
                print("    -> Statut 'LOW' non trouvé sur la page.")
                return False
                
    except Exception as e:
        print(f"    -> Erreur: {e}")
        return False

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

        tr_page = await chr_context.new_page()
        await tr_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            is_low_risk = await check_trenchradar(tr_page, token)
            
            # RÈGLE : Si TrenchRadar affiche "LOW" en vert
            if is_low_risk:
                found_good_coin = True
                message = f"✅ <b>Token LOW RISK Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: Statut LOW (Vert) sur TrenchRadar"
                await send_telegram_message(message)
            
            await asyncio.sleep(3)
            
        if not found_good_coin:
            print("[-] Aucun token n'a eu le statut LOW cette fois.")
            
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
