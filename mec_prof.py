# mec_prof.py
import os
import json
import re
from pdf_generator import load_card_list_from_text
from scryfall_api import fetch_card_data


def generate_mechanics_content(text_input):
    """
    Legge l'elenco delle carte dal widget di testo e restituisce una lista
    di dizionari con i dati:
      - 'card': nome della carta
      - 'oracle': descrizione in inglese (oracle_text)
      - 'mechs': lista di stringhe per ogni meccanica individuata con la relativa spiegazione
    """
    text = text_input.get("1.0", "end")
    pdf_cards, _, _ = load_card_list_from_text(text)
    if not pdf_cards:
        return []

    # Carica il vocabolario delle meccaniche da data/vocab_wiki.json
    vocab_path = os.path.join(os.path.dirname(__file__), "data", "vocab_wiki.json")
    try:
        with open(vocab_path, "r", encoding="utf-8") as f:
            vocab = json.load(f)
    except Exception as e:
        return [{"card": "Errore", "oracle": f"Errore nel caricamento del vocabolario: {e}", "mechs": []}]

    results = []
    for card in pdf_cards:
        card_data = fetch_card_data(card, lang="en")
        if not card_data:
            results.append({
                "card": card,
                "oracle": "Dati non trovati.",
                "mechs": []
            })
            continue

        oracle_text = card_data.get("oracle_text", "Nessuna descrizione disponibile")
        mechs = []
        for mech, description in vocab.items():
            if re.search(r'\b' + re.escape(mech) + r'\b', oracle_text, re.IGNORECASE):
                mechs.append(f"{mech}: {description}")

        results.append({
            "card": card,
            "oracle": oracle_text,
            "mechs": mechs
        })
    return results
