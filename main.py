import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD_MAX = 60 # On veut un score entre 0 et 60%

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

def check_ave_api(address):
    print(f"[*] Checking Ave.ai API directe pour {address[:8]}...")
    # L'API secrète de Ave.ai en précisant la chaîne Solana
    url = f"https://cyjm05.com/v1api/v2/tokens/contract?token_id={address}-solana&type=token&user_address="
    headers = {
        "User-Agent": "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.0 Mobile/15E148 Safari/604.1"
    }
    try:
        res = requests.get(url, headers=headers, timeout=10)
        data = res.json()
        
        # On navigue dans la structure JSON pour trouver le risk_score
        contract_data = data.get("data", {}).get("token_contract", {}).get("contract_data", {})
        score = contract_data.get("risk_score")
        
        if score is not None:
            print(f"    -> Score de Risque: {score}%")
            return int(score)
        else:
            print("    -> L'API n'a pas de score pour ce token.")
            return 101
    except Exception as e:
        print(f"    -> Erreur API: {e}")
        return 101

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

async def main():
    delay = random.uniform(1, 5)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    async with async_playwright() as p:
        print("[*] Lancement de Firefox pour DexScreener...")
        ff_browser = await p.firefox.launch(headless=True)
        ff_context = await ff_browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US'
        )
        dex_page = await ff_context.new_page()
        await dex_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        tokens = await get_new_solana_tokens(dex_page)
        await ff_browser.close()
        
        if not tokens:
            print("[-] Aucun token trouvé.")
            return

        print("🤖 Agent starting up (Ave.ai API directe)...")
        
        found_good_coin = False
        for token in tokens:
            score = check_ave_api(token['address'])
            # RÈGLE : Si le score est entre 0 et 60%
            if 0 <= score <= SCORE_THRESHOLD_MAX:
                found_good_coin = True
                message = f"✅ <b>Token Faible Risque Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: Score de {score}% sur Ave.ai"
                await send_telegram_message(message)
            await asyncio.sleep(1) # Petite pause pour ne pas spammer l'API
            
        if not found_good_coin:
            print("[-] Aucun token n'a eu un score <= 60% cette fois.")
            
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
