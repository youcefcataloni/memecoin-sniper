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

def get_new_solana_tokens_via_api():
    print("[*] Récupération des tokens via l'API DexScreener...")
    try:
        res = requests.get("https://api.dexscreener.com/token-profiles/latest/v1", timeout=10)
        profiles = res.json()
        solana_profiles = [p for p in profiles if p.get('chainId') == 'solana']
        
        tokens = []
        for p in solana_profiles[:200]: # On scanne 200 tokens
            address = p.get('tokenAddress')
            if not address: continue
            
            data_res = requests.get(f"https://api.dexscreener.com/latest/dex/tokens/{address}", timeout=10)
            data = data_res.json()
            pairs = data.get('pairs', [])
            if not pairs: continue
            
            pair = max(pairs, key=lambda x: x.get('liquidity', {}).get('usd', 0))
            liq = pair.get('liquidity', {}).get('usd', 0)
            mcap = pair.get('marketCap', 0) or pair.get('fdv', 0)
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

async def check_ave_ai(page, token):
    print(f"[*] Vérification Ave.ai pour {token['name']}...")
    
    captured_score = None
    
    # NOUVEAU : Fonction qui écoute toutes les communications de données
    async def handle_response(response):
        nonlocal captured_score
        if response.request.resource_type in ["xhr", "fetch"]:
            try:
                body = await response.text()
                # Si la communication contient "risk_score" ET l'adresse du token
                if "risk_score" in body and token['address'].lower() in body.lower():
                    # On extrait le chiffre juste après "risk_score"
                    match = re.search(r'"risk_score":\s*(\d+)', body)
                    if match:
                        captured_score = int(match.group(1))
            except:
                pass

    # On attache l'écouteur à la page
    page.on("response", handle_response)

    try:
        await page.goto("https://m.ave.ai/check", wait_until="networkidle", timeout=30000)
        await asyncio.sleep(3)
        
        try:
            await page.evaluate("document.querySelectorAll('.van-popup, .van-overlay').forEach(el => el.style.display = 'none');")
        except:
            pass
            
        search_input = page.get_by_placeholder("Please enter contract address")
        await search_input.wait_for(timeout=10000)
        await search_input.fill(token['address'])
        
        check_button = page.locator("button.submit-button")
        await check_button.click()
        
        print("    -> Attente de l'interception du score (10s)...")
        await asyncio.sleep(10)
        
        # On détache l'écouteur
        page.remove_listener("response", handle_response)
        
        if captured_score is not None:
            print(f"    -> Score de Risque officiel capturé: {captured_score}%")
            # RÈGLE : Si le score est entre 0% et 40%
            if 0 <= captured_score <= 40:
                return True
            else:
                return False
        else:
            print("    -> L'API n'a pas renvoyé de risk_score pour ce token.")
            return False
            
    except Exception as e:
        page.remove_listener("response", handle_response)
        print(f"    -> Erreur: {e}")
        return False

async def main():
    delay = random.uniform(1, 5)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    tokens = get_new_solana_tokens_via_api()
    if not tokens:
        print("[-] Aucun token trouvé.")
        return

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        iphone_13 = p.devices["iPhone 13"]
        context = await browser.new_context(**iphone_13, locale='en-US')
        page = await context.new_page()

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            is_safe = await check_ave_ai(page, token)
            if is_safe:
                found_good_coin = True
                message = f"✅ <b>Token Faible Risque Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: Score entre 0% et 40% sur Ave.ai"
                await send_telegram_message(message)
            await asyncio.sleep(2)
            
        if not found_good_coin:
            print("[-] Aucun token n'a eu un score entre 0% et 40% cette fois.")
            
        await browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
