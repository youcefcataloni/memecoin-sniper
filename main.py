import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re
import json

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
    print(f"[*] Test de l'API cachée de Ave.ai pour {token['name']}...")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        iphone_13 = p.devices["iPhone 13"]
        context = await browser.new_context(**iphone_13, locale='en-US')
        page = await context.new_page()

        # NOUVEAU : Intercepter TOUTES les réponses réseau de Ave.ai
        api_responses = []
        async def handle_response(response):
            url = response.url
            # On cherche les réponses qui ressemblent à de l'API (json)
            if "ave.ai" in url and "api" in url:
                try:
                    body = await response.json()
                    api_responses.append({"url": url, "body": body})
                except:
                    pass
        
        page.on("response", handle_response)

        try:
            await page.goto("https://m.ave.ai/check", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(3)
            
            # Fermer le pop-up
            try:
                await page.evaluate("document.querySelectorAll('.van-popup, .van-overlay').forEach(el => el.style.display = 'none');")
            except:
                pass
                
            # Taper l'adresse et cliquer
            search_input = page.get_by_placeholder("Please enter contract address")
            await search_input.wait_for(timeout=10000)
            await search_input.fill(token['address'])
            
            check_button = page.locator("button.submit-button")
            await check_button.click()
            
            print("[*] Attente de 10 secondes pour que l'API réponde...")
            await asyncio.sleep(10)
            
            # Analyser les réponses de l'API pour trouver le score
            print(f"[*] {len(api_responses)} réponses API interceptées.")
            for resp in api_responses:
                # On convertit le body en texte pour chercher le chiffre
                body_str = json.dumps(resp['body'])
                # Si le corps de la réponse contient un chiffre entre 0 et 100
                if re.search(r'(\d{1,3})', body_str):
                    print(f"\n--- API TROUVÉE ---")
                    print(f"URL: {resp['url']}")
                    print(f"Contenu: {body_str[:1000]}") # On affiche les 1000 premiers caractères
                    print(f"-------------------\n")
                    
        except Exception as e:
            print(f"Error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
