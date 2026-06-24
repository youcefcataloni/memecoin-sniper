import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")

def parse_dollar_value(val_str):
    try:
        val_str = val_str.replace('$', '').replace(',', '').strip()
        if 'M' in val_str:
            return float(val_str.replace('M', '')) * 1_000_000
        elif 'K' in val_str:
            return float(val_str.replace('K', '')) * 1_000
        else:
            return float(val_str)
    except:
        return 0

async def get_new_solana_tokens(page):
    print("[*] Scraping DexScreener (Firefox)...")
    await page.goto("https://dexscreener.com/solana", wait_until="domcontentloaded", timeout=30000)
    await asyncio.sleep(5)
    
    try:
        await page.wait_for_selector("a[href*='/solana/']", timeout=20000)
    except:
        return []

    all_links = await page.query_selector_all("a[href*='/solana/']")
    
    token_rows = []
    for row in all_links:
        href = await row.get_attribute("href")
        if href:
            address = href.split("/solana/")[1].split("?")[0]
            if len(address) >= 32:
                token_rows.append(row)

    tokens = []
    for row in token_rows[:50]:
        try:
            href = await row.get_attribute("href")
            if href and "/solana/" in href:
                address = href.split("/solana/")[1].split("?")[0]
                
                row_text = await row.inner_text()
                text_parts = row_text.split('\n')
                dollar_strings = [s for s in text_parts if '$' in s and len(s) < 15]
                
                if len(dollar_strings) >= 2:
                    liq_val = parse_dollar_value(dollar_strings[-2])
                    mcap_val = parse_dollar_value(dollar_strings[-1])
                    
                    if liq_val >= 20000 and mcap_val >= 100000:
                        name = text_parts[1] if len(text_parts) > 1 else "Unknown"
                        tokens.append({"name": name, "address": address})
                        if len(tokens) >= 1: # Juste 1 pour le test
                            break 
        except:
            continue
    return tokens

async def main():
    async with async_playwright() as p:
        # 1. Firefox pour DexScreener
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

        token = tokens[0]
        print(f"[*] Test de l'API Ave.ai pour {token['name']} ({token['address'][:8]}...)")

        # 2. Chromium pour Ave.ai
        chr_browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        iphone_13 = p.devices["iPhone 13"]
        ave_context = await chr_browser.new_context(**iphone_13, locale='en-US')
        page = await ave_context.new_page()

        # NOUVEAU : Intercepter les communications et afficher l'URL
        async def handle_response(response):
            url = response.url
            # Si l'URL de l'API contient l'adresse du token, c'est la bonne porte !
            if token['address'].lower() in url.lower() and response.request.resource_type in ["xhr", "fetch"]:
                print(f"\n--- API TROUVÉE POUR LE TOKEN ---")
                print(f"URL: {url}")
                try:
                    body = await response.text()
                    print(f"Contenu: {body[:1000]}")
                except:
                    pass
                print(f"--------------------------------\n")

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
            
            print("[*] Attente de 15 secondes pour intercepter l'API...")
            await asyncio.sleep(15)
                
        except Exception as e:
            print(f"Error: {e}")
            
        await chr_browser.close()

if __name__ == "__main__":
    asyncio.run(main())
