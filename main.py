import asyncio
from playwright.async_api import async_playwright
import requests
import os
import random
import re

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID")
SCORE_THRESHOLD = 70

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

async def get_defi_score(page, address):
    print(f"[*] Checking De.fi for {address[:8]}...")
    url = f"https://de.fi/scanner/contract/{address}"
    try:
        await page.goto(url, wait_until="load", timeout=60000)
        
        # Bouger la souris et scroller pour forcer le chargement
        await page.mouse.move(100, 100)
        await page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
        
        print("    -> Attente de 20 secondes pour le calcul de De.fi...")
        await asyncio.sleep(20)
        
        # Remonter au cas où le score est au milieu
        await page.evaluate("window.scrollTo(0, 500)")
        await asyncio.sleep(2)
        
        # Lire le code source HTML brut
        html_content = await page.content()
        
        # Recherche du score dans le HTML (cherche "75/100", "85 /100", etc.)
        match = re.search(r'(\d{1,3})\s*/\s*100', html_content)
        if match:
            score = int(match.group(1))
            print(f"    -> Score trouvé: {score}/100")
            return score
        else:
            # Si non trouvé, on affiche le texte visible de la page pour voir ce qu'il se passe
            body_text = await page.evaluate("document.body.innerText")
            print(f"    -> Could not find score. Texte visible de la page (1500 chars):\n{body_text[:1500]}")
            return 0
    except Exception as e:
        print(f"    -> Error: {e}")
        return 0

async def main():
    delay = random.uniform(1, 10)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    # TEST : On force BONK et WIF pour voir si De.fi nous donne leur score
    tokens = [
        {"name": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"},
        {"name": "WIF", "address": "EKpQGSJtjMFqKZ9KQanSqYXRcF8fBopzLHYxdM65zcjm"}
    ]

    async with async_playwright() as p:
        # On utilise Chromium pour De.fi (avec xvfb pour tromper Cloudflare)
        browser = await p.chromium.launch(headless=False, args=['--no-sandbox', '--disable-setuid-sandbox'])
        context = await browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            viewport={'width': 1920, 'height': 1080},
            locale='en-US',
        )
        
        defi_page = await context.new_page()
        await defi_page.add_init_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")

        print("🤖 Agent starting up...")
        
        found_good_coin = False
        for token in tokens:
            score = await get_defi_score(defi_page, token["address"])
            if score >= SCORE_THRESHOLD:
                found_good_coin = True
                message = f"🚀 <b>High Score Memecoin Found!</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\nScore: {score}/100"
                await send_telegram_message(message)
            
            # Attendre 10 secondes entre chaque token
            await asyncio.sleep(10)
            
        if not found_good_coin:
            print("[-] No tokens met the 70+ threshold this run.")
            
        await browser.close()
        print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
