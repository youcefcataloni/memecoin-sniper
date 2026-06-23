import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD = 70

async def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print("[-] ERROR: Telegram secrets are missing in GitHub! Cannot send message.")
        return
        
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        response = requests.post(url, json=payload, timeout=10)
        print(f"[*] Telegram response code: {response.status_code}")
    except Exception as e:
        print(f"[-] Failed to send Telegram message: {e}")

def get_new_solana_tokens_via_api():
    print("[*] Récupération des tokens via l'API DexScreener...")
    try:
        res = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=10)
        profiles = res.json()
        
        solana_profiles = [p for p in profiles if p.get('chainId') == 'solana']
        print(f"[*] Trouvé {len(solana_profiles)} profils Solana récents.")
        
        tokens = []
        for p in solana_profiles[:50]: 
            address = p.get('tokenAddress')
            if not address: continue
            
            data_res = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}", timeout=10)
            data = data_res.json()
            pairs = data.get('pairs', [])
            if not pairs: continue
            
            pair = pairs[0]
            liq = pair.get('liquidity', {}).get('usd', 0)
            mcap = pair.get('marketCap', 0)
            name = p.get('tokenName', pair.get('baseToken', {}).get('name', 'Unknown'))
            
            if liq >= 20000 and mcap >= 100000:
                print(f"    -> [GARDÉ] {name} | Liq: ${liq:,.0f} | Mcap: ${mcap:,.0f}")
                tokens.append({"name": name, "address": address})
                
            if len(tokens) >= 15:
                break
                
        return tokens
    except Exception as e:
        print(f"[-] Erreur API DexScreener: {e}")
        return []

async def get_trenchradar_score(page, address):
    print(f"[*] Checking TrenchRadar for {address[:8]}...")
    url = f"https://www.trenchradar.net/app?chain=solana"
    try:
        await page.goto(url, wait_until="load", timeout=60000)
        await asyncio.sleep(5)
        
        # TrenchRadar utilise probablement une barre de recherche pour vérifier un token
        # On cherche un champ de texte (input)
        search_input = await page.query_selector("input[type='text'], input[type='search'], input[placeholder*='search' i], input[placeholder*='address' i]")
        
        if search_input:
            print("    -> Barre de recherche trouvée. Saisie de l'adresse...")
            await search_input.fill("")
            await search_input.fill(address)
            await page.keyboard.press("Enter")
            # Attendre que le score se calcule
            print("    -> Attente de 15 secondes pour le calcul...")
            await asyncio.sleep(15)
        else:
            print("    -> Aucune barre de recherche trouvée. Lecture de la page...")
            await asyncio.sleep(10)
            
        # Lire le texte de la page
        body_text = await page.evaluate("document.body.innerText")
        
        # Recherche du score (ex: 85/100, 70 / 100)
        match = re.search(r'(\d{1,3})\s*/\s*100', body_text)
        if match:
            score = int(match.group(1))
            print(f"    -> Score trouvé: {score}/100")
            return score
        else:
            print(f"    -> Score non trouvé. Texte (500 chars): {body_text[:500]}")
            return 0
    except Exception as e:
        print(f"    -> Error: {e}")
        return 0

async def main():
    delay = random.uniform(1, 10)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    tokens = get_new_solana_tokens_via_api()
    
    if not tokens:
        print("[-] Aucun token trouvé via l'API.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
        )
        
        radar_page = await context.new_page()
        await radar_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            score = await get_trenchradar_score(radar_page, token["address"])
            if score >= SCORE_THRESHOLD:
                found_good_coin = True
                message = f"🚀 <b>High Score Memecoin Found!</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\nScore: {score}/100"
                await send_telegram_message(message)
            
            await asyncio.sleep(10)
            
        if not found_good_coin:
            print("[-] No tokens met the 70+ threshold this run.")
            
        await browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
