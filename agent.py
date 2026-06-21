import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD = 70

# MUCH SAFER SELECTOR: Finds any link that goes to a Solana token
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
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    payload = {"chat_id": TELEGRAM_CHAT_ID, "text": message, "parse_mode": "HTML"}
    try:
        requests.post(url, json=payload)
        print("[+] Telegram message sent successfully.")
    except Exception as e:
        print(f"[-] Failed to send Telegram message: {e}")

async def get_new_solana_tokens(page):
    print("[*] Scraping DexScreener...")
    await page.goto("https://dexscreener.com/solana", wait_until="domcontentloaded")
    try:
        await page.wait_for_selector(DEXSCREENER_ROW_SELECTOR, timeout=20000)
    except:
        print("[-] DexScreener blocked the bot or layout changed.")
        return []

    tokens = []
    rows = await page.query_selector_all(DEXSCREENER_ROW_SELECTOR)
    
    for row in rows[:50]:
        try:
            href = await row.get_attribute("href")
            if href and "/solana/" in href:
                address = href.split("/solana/")[1].split("?")[0]
                
                links = await row.eval_on_selector_all('a', '(elements) => elements.map(e => e.href)')
                has_socials = False
                for link in links:
                    if 'twitter.com' in link or 'x.com' in link or 't.me' in link or 'telegram.me' in link or ('http' in link and 'dexscreener.com' not in link):
                        has_socials = True
                        break
                
                if not has_socials:
                    continue
                
                row_text = await row.inner_text()
                text_parts = row_text.split('\n')
                dollar_strings = [s for s in text_parts if s.startswith('$') and len(s) < 10]
                
                if len(dollar_strings) >= 2:
                    liq_val = parse_dollar_value(dollar_strings[0])
                    mcap_val = parse_dollar_value(dollar_strings[1])
                    
                    if liq_val >= 20000 and mcap_val >= 100000:
                        name_element = await row.query_selector("span.css-1aqamvn")
                        name = await name_element.inner_text() if name_element else "Unknown"
                        
                        print(f"    -> [GARDÉ] {name} | Liq: ${liq_val:,.0f} | Mcap: ${mcap_val:,.0f}")
                        tokens.append({"name": name, "address": address})
                        
                        if len(tokens) >= 15:
                            break 
        except:
            continue
            
    print(f"[+] Found {len(tokens)} tokens.")
    return tokens

async def get_defi_score(page, address):
    print(f"[*] Checking De.fi for {address[:8]}...")
    url = f"https://de.fi/scanner/contract/{address}"
    try:
        await page.goto(url, wait_until="domcontentloaded", timeout=20000)
        await page.wait_for_selector(DEFI_SCORE_SELECTOR, timeout=15000)
        score_element = await page.query_selector(DEFI_SCORE_SELECTOR)
        score_text = await score_element.inner_text()
        score = int(score_text.split("/")[0].strip())
        print(f"    -> Score: {score}/100")
        return score
    except:
        print("    -> Could not find score.")
        return 0

async def main():
    delay = random.uniform(1, 15)
    print(f"[*] Waiting for {delay:.2f} seconds to mimic human behavior...")
    await asyncio.sleep(delay)

    async with async_playwright() as p:
        # NEW: Added a User-Agent to bypass DexScreener bot protection
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
        )
        
        dex_page = await context.new_page()
        defi_page = await context.new_page()

        print("🤖 Agent starting up...")
        
        # TEST MESSAGE: This will run immediately to prove Telegram works
        await send_telegram_message("🧪 Test Message: The agent is online and Telegram is working!")
        
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
