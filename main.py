
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
            if len(tokens) >= 1:
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
    print(f"[*] Test de recherche manuelle sur Ave.ai pour {token['name']} ({token['address'][:8]}...)")

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True, args=['--no-sandbox', '--disable-setuid-sandbox'])
        
        # On simule un iPhone pour que la page m.ave.ai s'affiche correctement
        iphone_13 = p.devices["iPhone 13"]
        context = await browser.new_context(**iphone_13, locale='en-US')
        page = await context.new_page()

        try:
            # 1. Aller sur la page de scan
            await page.goto("https://m.ave.ai/check", wait_until="networkidle", timeout=30000)
            
            # Fermer le pop-up de disclaimer s'il existe
            try:
                confirm_button = page.get_by_role("button", name="Confirm")
                await confirm_button.click(timeout=3000)
                print("[+] Pop-up fermé.")
                await asyncio.sleep(2)
            except:
                print("[*] Pas de pop-up.")
            
            # 2. Trouver la barre de recherche et taper l'adresse
            print("[*] Recherche de la barre de recherche...")
            # On cherche un input de type texte ou search
            search_input = page.locator("input[type='text']").first
            await search_input.wait_for(timeout=10000)
            await search_input.fill(token['address'])
            print(f"[+] Adresse '{token['address'][:8]}...' tapée.")
            
            # 3. Appuyer sur Entrée pour lancer la recherche
            await page.keyboard.press("Enter")
            print("[*] Touche Entrée pressée. Attente des résultats...")
            
            # 4. Attendre que la page charge le résultat
            await asyncio.sleep(8)
            
            # 5. Prendre une capture d'écran du résultat
            await page.screenshot(path="ave_search_result.png", full_page=True)
            print("[+] Capture d'écran sauvegardée sous ave_search_result.png")
            
            # 6. Afficher le texte de la page pour voir où est le score
            body_text = await page.evaluate("document.body.innerText")
            print("--- TEXTE DU RÉSULTAT ---")
            print(body_text[:2000])
            print("-------------------------")
            
        except Exception as e:
            print(f"Error: {e}")
            
        await browser.close()

if __name__ == "__main__":
    asyncio.run(main())
