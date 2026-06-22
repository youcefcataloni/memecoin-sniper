import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD = 70

DEXSCREENER_ROW_SELECTOR = "a[href*='/solana/']"
DEFI_SCORE_SELECTOR = "div.scanner-score-value"

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

async def get_new_solana_tokens(page):
    print("[*] Scraping DexScreener...")
    await page.goto("https://dexscreener.com/solana", wait_until="domcontentloaded", timeout=30000)
    
    title = await page.title()
    print(f"[*] Titre de la page: {title}")
    await asyncio.sleep(5)
    
    try:
        await page.wait_for_selector(DEXSCREENER_ROW_SELECTOR, timeout=20000)
    except:
        print("[-] DexScreener blocked the bot or layout changed.")
        return []

    all_links = await page.query_selector_all(DEXSCREENER_ROW_SELECTOR)
    
    token_rows = []
    for row in all_links:
        href = await row.get_attribute("href")
        if href:
            address = href.split("/solana/")[1].split("?")[0]
            if len(address) >= 32:
                token_rows.append(row)
                
    print(f"[*] Nombre de vrais tokens trouvés: {len(token_rows)}")

    tokens = []
    for row in token_rows[:15]: # On remet à 15 tokens
        try:
            href = await row.get_attribute("href")
            if href and "/solana/" in href:
                address = href.split("/solana/")[1].split("?")[0]
                
                has_socials = True # Toujours désactivé pour le test
                
                row_text = await row.inner_text()
                text_parts = row_text.split('\n')
                dollar_strings = [s for s in text_parts if '$' in s and len(s) < 15]
                
                if len(dollar_strings) >= 2:
                    liq_val = parse_dollar_value(dollar_strings[-2])
                    mcap_val = parse_dollar_value(dollar_strings[-1])
                    
                    if liq_val >= 20000 and mcap_val >= 100000:
                        name = text_parts[1] if len(text_parts) > 1 else "Unknown"
                        
                        print(f"    -> [GARDÉ] {name} | Liq: ${liq_val:,.0f} | Mcap: ${mcap_val:,.0f}")
                        tokens.append({"name": name, "address": address})
        except:
            continue
            
    print(f"[+] Found {len(tokens)} tokens valides.")
    return tokens

async def get_defi_score(page, address):
    print(f"[*] Checking De.fi for {address[:8]}...")
    url = f"https://de.fi/scanner/contract/{address}"
    try:
        await page.goto(url, wait_until="load", timeout=30000)
        await asyncio.sleep(3)
        
        title = await page.title()
        print(f"    -> Titre De.fi: {title}")
        
        body_text = await page.evaluate("document.body.innerText.substring(0, 200)")
        print(f"    -> Texte De.fi: {body_text}")
        
        await page.wait_for_selector(DEFI_SCORE_SELECTOR, timeout=25000)
        score_element = await page.query_selector(DEFI_SCORE_SELECTOR)
        score_text = await score_element.inner_text()
        score = int(score_text.split("/")[0].strip())
        print(f"    -> Score: {score}/100")
        return score
    except Exception as e:
        print("    -> Could not find score.")
        return 0

async def main():
    delay = random.uniform(1, 10)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    async with async_playwright() as p:
        browser = await p.firefox.launch(headless=True)
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:121.0) Gecko/20100101 Firefox/121.0"
        )
        
        dex_page = await context.new_page()
        await dex_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        
        defi_page = await context.new_page()

        print("🤖 Agent starting up...")
        
        tokens = await get_new_solana_tokens(dex_page)
        
        found_good_coin = False
        for token in tokens:
            score = await get_defi_score(defi_page, token["address"])
            if score >= SCORE_THRESHOLD:
                found_good_coin = True
                message = f"🚀 <b>High Score Memecoin Found!</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\nScore: {score}/100"
                await send_telegram_message(message)
            await asyncio.sleep(3)
            
        if not found_good_coin:
            print("[-] No tokens met the 70+ threshold this run.")
            
        await browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
