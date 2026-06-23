import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD = 40 # CHANGÉ : On cherche un score entre 0 et 40%

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

async def get_ave_score(page, address):
    print(f"[*] Checking Ave.ai for {address[:8]}...")
    # NOUVEAU : URL mobile de Ave.ai
    url = f"https://m.ave.ai/token/solana/{address}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(5) # Attendre 5 secondes que le score charge
        
        body_text = await page.evaluate("document.body.innerText")
        
        # NOUVEAU : Afficher le contexte autour du mot "score" ou "security" pour comprendre la page
        score_index = body_text.lower().find("score")
        if score_index == -1:
            score_index = body_text.lower().find("security")
            
        if score_index != -1:
            print(f"    -> Contexte trouvé: ...{body_text[max(0, score_index-50):score_index+100]}...")
        
        # Recherche de tous les nombres entre 0 et 100 dans le texte
        numbers = re.findall(r'\b([0-9]{1,2})\b', body_text)
        
        # On cherche un nombre qui est <= 40
        for num_str in numbers:
            num = int(num_str)
            if 0 <= num <= SCORE_THRESHOLD:
                print(f"    -> Score trouvé (<= 40%): {num}%")
                return num
        
        print("    -> Could not find score <= 40%.")
        return 101 # Retourne 101 si non trouvé ou > 40%
    except Exception as e:
        print(f"    -> Error: {e}")
        return 101

async def main():
    delay = random.uniform(1, 10)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    tokens = get_new_solana_tokens_via_api()
    
    if not tokens:
        print("[-] Aucun token trouvé via l'API.")
        return

    async with async_playwright() as p:
        # On utilise un navigateur normal (headless=True) car Ave.ai ne bloque pas les bots
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        
        # NOUVEAU : On simule un iPhone pour que la page m.ave.ai s'affiche correctement
        iphone_13 = p.devices["iPhone 13"]
        context = await browser.new_context(
            **iphone_13,
            locale='en-US'
        )
        
        ave_page = await context.new_page()

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            score = await get_ave_score(ave_page, token["address"])
            
            # CHANGÉ : Si le score est entre 0 et 40
            if score <= SCORE_THRESHOLD:
                found_good_coin = True
                message = f"⚠️ <b>Low Score Memecoin Found!</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\nScore: {score}%"
                await send_telegram_message(message)
            
            await asyncio.sleep(3)
            
        if not found_good_coin:
            print("[-] No tokens met the <= 40% threshold this run.")
            
        await browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
