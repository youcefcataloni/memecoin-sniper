import asyncio
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

def get_goplus_score(address):
    print(f"[*] Vérification GoPlus (moteur de Ave.ai) pour {address[:8]}...")
    url = f"https://api.gopluslabs.io/api/v1/token_security_solana/{address}"
    try:
        res = requests.get(url, timeout=10)
        data = res.json()
        result = data.get('result', {})
        
        if not result or not result.get('token_security_solana'):
            print("    -> Score non disponible pour ce token.")
            return None
            
        token_data = result.get('token_security_solana', {}).get(address, {})
        
        # GoPlus calcule un score de sécurité de 0 à 100.
        # Un score de 80 signifie "Très sûr" (80% Safe).
        # Un score de 10 signifie "Très dangereux" (10% Safe = High Risk).
        security_score_str = token_data.get('security_score', '0')
        security_score = int(security_score_str)
        
        print(f"    -> Score de Sécurité GoPlus: {security_score}/100")
        return security_score
        
    except Exception as e:
        print(f"    -> Erreur GoPlus: {e}")
        return None

async def main():
    delay = random.uniform(1, 5)
    print(f"[*] Waiting for {delay:.2f} seconds...")
    await asyncio.sleep(delay)

    tokens = get_new_solana_tokens_via_api()
    if not tokens:
        print("[-] Aucun token trouvé.")
        return

    print("🤖 Agent starting up...")
    
    # NOUVEAU : On teste avec un token connu (comme BONK) pour vérifier que l'API donne le bon score
    test_token = {"name": "BONK", "address": "DezXAZ8z7PnrnRJjz3wXBoRgixCa6xjnB7YaB1pPB263"}
    score = get_goplus_score(test_token['address'])
    if score is not None:
        print(f"[TEST BONK] Le score officiel de BONK est : {score}/100")
        
    found_good_coin = False
    for token in tokens:
        score = get_goplus_score(token['address'])
        
        # RÈGLE : Vous voulez être alerté si le score de Risque est faible.
        # Si le score de sécurité est élevé (ex: 80), le risque est faible.
        # Si vous voulez les tokens avec 0 à 40% de Risque, on cherche un score de sécurité >= 60.
        if score is not None and score >= 60:
            found_good_coin = True
            message = f"✅ <b>Token Faible Risque Trouvé !</b>\n\nName: <b>{token['name']}</b>\nAddress: <code>{token['address']}</code>\n\nScore de Sécurité: {score}/100 (Faible Risque)"
            await send_telegram_message(message)
        await asyncio.sleep(1)
        
    if not found_good_coin:
        print("[-] Aucun token n'a eu un bon score cette fois.")
        
    print("✅ Agent finished task.")

if __name__ == "__main__":
    asyncio.run(main())
