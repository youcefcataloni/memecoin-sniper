import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re
from datetime import datetime, timezone, timedelta

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

def get_new_solana_tokens_via_api():
    print("[*] Récupération des tokens via l'API DexScreener (Immunisé à Cloudflare)...")
    try:
        res = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=15)
        profiles = res.json()
        solana_profiles = [p for p in profiles if p.get('chainId') == 'solana']
        
        tokens = []
        now = datetime.now(timezone.utc)
        
        for p in solana_profiles[:200]: # On scanne les 200 derniers profils
            address = p.get('tokenAddress')
            if not address: continue
            
            data_res = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}", timeout=15)
            data = data_res.json()
            pairs = data.get('pairs', [])
            if not pairs: continue
            
            pair = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            liq = pair.get('liquidity', {}).get('usd', 0)
            mcap = pair.get('marketCap', 0) or pair.get('fdv', 0)
            name = p.get('tokenName', pair.get('baseToken', {}).get('name', 'Unknown'))
            
            # FILTRE FINANCIER
            if liq >= 20000 and mcap >= 100000:
                # FILTRE AGE (0 à 72 heures)
                created_at_str = pair.get('pairCreatedAt')
                if created_at_str:
                    created_at = datetime.fromisoformat(created_at_str.replace('Z', '+00:00'))
                    age_hours = (now - created_at).total_seconds() / 3600
                    
                    if 0 <= age_hours <= 72:
                        print(f"    -> [GARDÉ 0-72h] {name} | Liq: ${liq:,.0f} | Mcap: ${mcap:,.0f}")
                        tokens.append({"name": name, "address": address})
                        
            if len(tokens) >= 50:
                break
                
        print(f"[+] Found {len(tokens)} tokens valides au total.")
        return tokens
        
    except Exception as e:
        print(f"[-] Erreur API DexScreener: {e}")
        return []

async def check_rugchecker(page, token):
    print(f"[*] Vérification RugChecker pour {token['name']}...")
    url = "https://rugchecker.com/fr"
    
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(3)
        
        try:
            get_started_btn = page.locator("button:has-text('Get Started')")
            await get_started_btn.click(timeout=3000)
            await asyncio.sleep(2)
        except:
            pass
            
        search_input = page.locator("input[placeholder*='Adresse du jeton']")
        if not await search_input.count():
            search_input = page.locator("input[type='text']").first
            
        await search_input.wait_for(timeout=10000)
        await search_input.fill("")
        await asyncio.sleep(1)
        await search_input.fill(token['address'])
        
        check_button = page.locator("button:has-text('Rug Check')")
        await check_button.click()
        
        print("    -> Attente du calcul du score...")
        await asyncio.sleep(12)
        
        body_text = await page.evaluate("document.body.innerText")
        
        # Le score est sous "Analyse de sécurité du jeton"
        match = re.search(r'Analyse de sécurité du jeton\s*(\d{1,3})', body_text, re.IGNORECASE)
        
        if match:
            score = int(match.group(1))
            print(f"    -> Score trouvé: {score}")
            return score
        else:
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

    # 1. API DexScreener (Pas de navigateur, pas de blocage)
    tokens = get_new_solana_tokens_via_api()
    if not tokens:
        print("[-] Aucun token trouvé.")
        return

    # 2. Chromium pour RugChecker
    async with async_playwright() as p:
        print("[*] Lancement de Chromium (Fenêtre réelle) pour RugChecker...")
        chr_browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
        chr_context = await chr_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='fr-FR'
        )
        rug_page = await chr_context.new_page()
        await rug_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            score = await check_rugchecker(rug_page, token)
            
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
