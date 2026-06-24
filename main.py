import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

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
            if len(tokens) >= 1: # Juste 1 pour le test
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
    print(f"[*] Extraction du score Ave.ai pour {token['name']}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        iphone_13 = p.devices["iPhone 13"]
        context = await browser.new_context(**iphone_13, locale='en-US')
        page = await context.new_page()

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
            
            print("[*] Attente de 10 secondes pour le chargement...")
            await asyncio.sleep(10)
            
            # NOUVEAU : Récupérer le code HTML brut de toute la page
            html_content = await page.content()
            
            # NOUVEAU : Chercher TOUS les nombres entre 0 et 100 dans le code HTML
            all_numbers = re.findall(r'>(\d{1,2})<', html_content)
            
            print(f"[*] Nombres trouvés dans la page (0-100): {all_numbers}")
            
            # On affiche aussi un extrait du HTML autour du mot "Risk" pour voir comment il est codé
            risk_index = html_content.lower().find("risk")
            if risk_index != -1:
                print(f"\n--- EXTRAIT HTML AUTOUR DE 'RISK' ---")
                print(html_content[max(0, risk_index-200):risk_index+300])
                print("------------------------------------\n")
                
        except Exception as e:
            print(f"Error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
