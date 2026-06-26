import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD_MAX = 45

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

async def check_ave_ai(page, token):
    print(f"[*] Vérification Ave.ai pour {token['name']}...")
    
    captured_score = None
    
    async def handle_response(response):
        nonlocal captured_score
        if response.request.resource_type in ["xhr", "fetch"]:
            try:
                body = await response.text()
                if "risk_score" in body and token['address'].lower() in body.lower():
                    match = re.search(r'"risk_score":\s*(\d+)', body)
                    if match:
                        captured_score = int(match.group(1))
            except:
                pass

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
        
        await asyncio.sleep(10)
        page.remove_listener("response", handle_response)
        
        if captured_score is not None:
            print(f"    -> Score de Risque capturé: {captured_score}%")
            if 0 <= captured_score <= SCORE_THRESHOLD_MAX:
                return True
            else:
                return False
        else:
            print("    -> L'API n'a pas renvoyé de risk_score pour ce token.")
            return False
            
    except Exception as e:
        page.remove_listener("response", handle_response)
        return False

async def main():
    delay = random.uniform(1, 5)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

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

        # 2. Chromium (iPhone) pour Ave.ai
        print("[*] Lancement de Chromium pour Ave.ai...")
        chr_browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        iphone_13 = p.devices["iPhone 13"]
        ave_context = await chr_browser.new_context(**iphone_13, locale='en-US')
        ave_page = await ave_context.new_page()

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            is_safe = await check_ave_ai(ave_page, token)
            if is_safe:
                found_good_coin = True
                message = f"✅ <b>Token Faible Risque Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nRésultat: Score entre 0% et 45% sur Ave.ai"
                await send_telegram_message(message)
            await asyncio.sleep(2)
            
        if not found_good_coin:
            print("[-] Aucun token n'a eu un score <= 45% cette fois.")
            
        await chr_browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
