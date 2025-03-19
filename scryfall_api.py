# scryfall_api.py
import os
import time
import requests
import urllib.parse
from collections import OrderedDict
from config import SCRYFALL_BASE_URL, EXCHANGE_RATE_URL, REQUEST_LIMIT, PAUSE_TIME, DELAY_BETWEEN, MAX_RETRIES, \
    DEFAULT_USD_TO_EUR, CARD_IMAGES_DIR

session = requests.Session()
REQUEST_COUNT = 0


def rate_limited_get(url, params=None):
    global REQUEST_COUNT
    REQUEST_COUNT += 1
    if REQUEST_COUNT % REQUEST_LIMIT == 0:
        time.sleep(PAUSE_TIME)

    response = None
    for attempt in range(MAX_RETRIES):
        response = session.get(url, params=params)
        if response.status_code != 429:
            break
        else:
            backoff = PAUSE_TIME * (2 ** attempt)
            print(
                f"429 ricevuto per {url}. Ritento dopo {backoff} secondi... (Tentativo {attempt + 1} di {MAX_RETRIES})")
            time.sleep(backoff)
    time.sleep(DELAY_BETWEEN)
    return response


def get_usd_to_eur_rate():
    try:
        response = rate_limited_get(EXCHANGE_RATE_URL)
        response.raise_for_status()
        data = response.json()
        rate = data["rates"]["EUR"]
        print(f"Tasso di cambio USD -> EUR aggiornato: {rate}")
        return rate
    except Exception as e:
        print(f"Errore nel download del cambio USD->EUR: {e}")
        return DEFAULT_USD_TO_EUR


USD_TO_EUR = get_usd_to_eur_rate()


def fetch_card_data(card_name, lang="en"):
    url = f"{SCRYFALL_BASE_URL}/cards/named"
    params = {"exact": card_name, "lang": lang}
    try:
        response = rate_limited_get(url, params=params)
        response.raise_for_status()
        return response.json()
    except Exception as e:
        print(f"Errore nel recupero dati per '{card_name}' (lang={lang}): {e}")
        return None


def download_image(url, filename):
    try:
        response = rate_limited_get(url)
        response.raise_for_status()
        with open(filename, "wb") as f:
            f.write(response.content)
        return filename
    except Exception as e:
        print(f"Errore nel download dell'immagine da {url}: {e}")
        return None


def download_card_image(card_name):
    safe_name = urllib.parse.quote(card_name)
    filename = f"{safe_name}_normal.jpg"
    img_path = os.path.join(CARD_IMAGES_DIR, filename)
    if os.path.exists(img_path):
        return img_path
    data = fetch_card_data(card_name, lang="en")
    if data and "image_uris" in data and "normal" in data["image_uris"]:
        image_url = data["image_uris"]["normal"]
        return download_image(image_url, img_path)
    else:
        print(f"Nessuna immagine trovata per '{card_name}'.")
    return None


def get_card_text_in_italian(card_name):
    data_en = fetch_card_data(card_name, lang="en")
    if not data_en:
        return "Carta non trovata in italiano"
    oracle_id = data_en.get("oracle_id")
    if not oracle_id:
        return data_en.get("oracle_text", "Testo non disponibile in italiano")
    search_url = f"{SCRYFALL_BASE_URL}/cards/search"
    params = {"q": f"oracleid:{oracle_id} lang:it", "unique": "prints"}
    try:
        response = rate_limited_get(search_url, params=params)
        response.raise_for_status()
        data_it = response.json()
        if data_it and data_it.get("data"):
            italian_card = data_it["data"][0]
            return italian_card.get("printed_text", "Testo non disponibile in italiano")
    except Exception as e:
        print(f"Errore nella ricerca della traduzione in italiano per '{card_name}': {e}")
    return "Testo non disponibile in italiano"


def get_card_price(card_name):
    data = fetch_card_data(card_name, lang="en")
    if data:
        prices = data.get("prices", {})
        price_eur = prices.get("eur")
        price_eur_foil = prices.get("eur_foil")
        if not price_eur:
            price_usd = prices.get("usd")
            if price_usd:
                try:
                    price_eur = f"{round(float(price_usd) * USD_TO_EUR, 2)}"
                except Exception:
                    price_eur = None
        if not price_eur_foil:
            price_usd_foil = prices.get("usd_foil")
            if price_usd_foil:
                try:
                    price_eur_foil = f"{round(float(price_usd_foil) * USD_TO_EUR, 2)}"
                except Exception:
                    price_eur_foil = None
        if not price_eur and not price_eur_foil:
            return "Prezzo non disponibile"
        price_info = ""
        if price_eur:
            price_info += f"Prezzo normale: {price_eur}€\n"
        else:
            price_info += "Prezzo normale non disponibile\n"
        if price_eur_foil:
            price_info += f"Prezzo foil: {price_eur_foil}€"
        else:
            price_info += "Prezzo foil non disponibile"
        return price_info
    return "Prezzo non disponibile"


def download_printing_image_small(printing):
    if "image_uris" in printing:
        if "small" in printing["image_uris"]:
            image_url = printing["image_uris"]["small"]
            suffix = "small"
        elif "normal" in printing["image_uris"]:
            image_url = printing["image_uris"]["normal"]
            suffix = "normal"
        else:
            return None
        safe_id = printing.get("id", printing.get("name", "unknown"))
        safe_id = urllib.parse.quote(safe_id)
        filename = f"{safe_id}_{suffix}.jpg"
        img_path = os.path.join(CARD_IMAGES_DIR, filename)
        if os.path.exists(img_path):
            return img_path
        return download_image(image_url, img_path)
    return None
