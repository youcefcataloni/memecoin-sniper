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

async def check_ave_ai(page, token):
    print(f"[*] Vérification Ave.ai pour {token['name']}...")
    
    await page.goto("https://m.ave.ai/check", wait_until="networkidle", timeout=30000)
    await asyncio.sleep(3)
    
    try:
        await page.evaluate("document.querySelectorAll('.van-popup, .van-overlay').forEach(el => el.style.display = 'none');")
    except:
        pass
        
    try:
        search_input = page.get_by_placeholder("Please enter contract address")
        await search_input.wait_for(timeout=10000)
        await search_input.fill(token['address'])
        
        check_button = page.locator("button.submit-button")
        await check_button.click()
        
    except Exception as e:
        print(f"    -> Erreur lors de la recherche: {e}")
        return False
        
    try:
        await page.wait_for_selector("text=Buy Tax", timeout=15000)
    except:
        print("    -> Les résultats n'ont pas chargé à temps.")
        return False
        
    body_text = await page.evaluate("document.body.innerText")
    
    # NOUVEAU : On lit le nombre de Danger, Warning et les Taxes
    danger_match = re.search(r'Danger\s*(\d+)', body_text)
    danger_count = int(danger_match.group(1)) if danger_match else 0
    
    warning_match = re.search(r'Warning\s*(\d+)', body_text)
    warning_count = int(warning_match.group(1)) if warning_match else 0
    
    buy_tax_match = re.search(r'Buy Tax\s*(\d+)%', body_text)
    buy_tax = int(buy_tax_match.group(1)) if buy_tax_match else 0
    
    sell_tax_match = re.search(r'Sell Tax\s*(\d+)%', body_text)
    sell_tax = int(sell_tax_match.group(1)) if sell_tax_match else 0
    
    print(f"    -> Danger: {danger_count} | Warning: {warning_count} | Buy Tax: {buy_tax}% | Sell Tax: {sell_tax}%")
    
    # RÈGLE : Si 0 Danger, 0 ou 1 Warning, et Taxes <= 5%, c'est un token à faible risque (0-40%)
    if danger_count == 0 and warning_count <= 1 and buy_tax <= 5 and sell_tax <= 5:
        return True
    else:
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
                message = f"✅ <b>Token Faible Risque Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: 0 Danger, Taxes 0% sur Ave.ai"
                await send_telegram_message(message)
            await asyncio.sleep(2)
            
        if not found_good_coin:
            print("[-] Aucun token n'a passé le filtre de sécurité cette fois.")
            
        await browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
