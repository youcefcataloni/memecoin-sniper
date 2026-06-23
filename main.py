import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

async def send_telegram_message(message):
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload, timeout=10)
    except:
        pass

def get_new_solana_tokens_via_api():
    print("[*] Récupération des tokens via l'API DexScreener...")
    try:
        res = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=10)
        profiles = res.json()
        solana_profiles = [p for p in profiles if p.get('chainId') == 'solana']
        
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
                tokens.append({"name": name, "address": address})
            if len(tokens) >= 1: # On prend juste 1 token pour le test
                break
        return tokens
    except Exception as e:
        print(f"[-] Erreur API DexScreener: {e}")
        return []

async def main():
    tokens = get_new_solana_tokens_via_api()
    if not tokens:
        print("[-] Aucun token trouvé.")
        return

    token = tokens[0]
    print(f"[*] Checking Ave.ai for {token['name']} ({token['address'][:8]}...)")
    url = f"https://m.ave.ai/token/solana/{token['address']}"

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        iphone_13 = p.devices["iPhone 13"]
        context = await browser.new_context(**iphone_13, locale='en-US')
        page = await context.new_page()

        try:
            await page.goto(url, wait_until="networkidle", timeout=30000)
            await asyncio.sleep(5)
            
            # Prendre une capture d'écran de la page entière
            await page.screenshot(path="ave_screenshot.png", full_page=True)
            print("[+] Capture d'écran sauvegardée sous ave_screenshot.png")
            
            # Afficher tout le texte de la page pour qu'on voit où est le score
            body_text = await page.evaluate("document.body.innerText")
            print("--- TEXTE DE LA PAGE AVE.AI ---")
            print(body_text)
            print("--------------------------------")
            
        except Exception as e:
            print(f"Error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
