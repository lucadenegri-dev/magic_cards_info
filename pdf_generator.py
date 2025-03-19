# pdf_generator.py
import os
import math
import re
from collections import OrderedDict
from reportlab.lib.pagesizes import letter
from reportlab.pdfgen import canvas
from reportlab.lib.utils import ImageReader
from reportlab.platypus import Paragraph
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.pdfbase import pdfmetrics
from reportlab.pdfbase.ttfonts import TTFont

from scryfall_api import (
    fetch_card_data, download_card_image, get_card_text_in_italian, get_card_price,
    download_printing_image_small
)
from config import DEFAULT_FONT_NAME, CRIMSON_FONT, BELEREN_BOLD_FONT, PAGE_SIZE, MANA_SYMBOLS_DIR

# Registrazione dei font
try:
    pdfmetrics.registerFont(TTFont('Crimson', CRIMSON_FONT))
    FONT_NAME = 'Crimson'
except Exception as e:
    print("Impossibile caricare il font Crimson, uso Helvetica.")
    FONT_NAME = DEFAULT_FONT_NAME

try:
    pdfmetrics.registerFont(TTFont('Beleren-Bold', BELEREN_BOLD_FONT))
    FONT_BOLD = 'Beleren-Bold'
except Exception as e:
    print("Impossibile caricare il font Beleren-Bold, uso il font normale per i titoli.")
    FONT_BOLD = FONT_NAME

def simple_markdown_to_rl(text):
    """
    Converte parte del Markdown in tag compatibili con ReportLab.
    """
    text = re.sub(r'\*\*(.*?)\*\*', r'<b>\1</b>', text)
    text = re.sub(r'"([^"]+)"', r'<b>\1</b>', text)

    lines = text.splitlines()
    new_lines = []
    current_cont_indent = None

    header_pattern = re.compile(r'^(#{1,3})\s+(.*)')
    bullet_pattern = re.compile(r'^(\s*)-\s+(.*)')

    for line in lines:
        header_match = header_pattern.match(line)
        if header_match:
            header_text = header_match.group(2).strip()
            new_line = f"<br/><b>{header_text}</b><br/>"
            new_lines.append(new_line)
            current_cont_indent = None
            continue

        bullet_match = bullet_pattern.match(line)
        if bullet_match:
            leading_spaces = bullet_match.group(1)
            content = bullet_match.group(2).strip()
            indent_level = len(leading_spaces) // 2
            indent_str = "&nbsp;" * (indent_level * 4)
            marker = "- " if indent_level == 1 else "• "
            content_wrapped = f"<font name=\"Crimson\">{content}</font>"
            new_line = f"{indent_str}{marker}{content_wrapped}"
            new_lines.append(new_line)
            current_cont_indent = indent_str + "&nbsp;&nbsp;"
            continue

        if current_cont_indent is not None and line.strip() != "":
            line = current_cont_indent + line.strip()
        if line.strip() != "" and not line.strip().startswith("<b>"):
            line = f"<font name=\"Crimson\">{line.strip()}</font>"
        new_lines.append(line)
        if line.strip() == "":
            current_cont_indent = None

    result = "<br/>".join(new_lines)
    return result

def generate_targeted_advice(num_cards, total_price, avg_price, avg_cmc, cards_list, deck_colors):
    """
    Genera un consiglio mirato utilizzando le API di OpenAI.
    """
    import os
    import requests
    try:
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            raise Exception("OPENAI_API_KEY non impostata.")
        prompt = (
            f"""<reasoning> - Simple Change: no - Reasoning: yes - Identify: "istruzioni richiedono chain-of-thought all'inizio" - Conclusion: yes - Ordering: before - Structure: yes - Examples: no - Complexity: 5 - Task: 5 - Necessity: 5 - Specificity: 5 - Prioritization: reasoning clarity, structure, detail - Conclusion: Enhance clarity and detail by explicitly requiring initial reasoning, maintaining structured instructions, and providing detailed steps and output format. </reasoning> Analizza un mazzo Magic Commander basandoti sui seguenti parametri:
- Elenco delle carte: {', '.join(cards_list)}
- Numero totale di carte: {num_cards}
- Costo medio in mana (CMC): {avg_cmc:.2f}
- Colori del mazzo: {deck_colors}

Il formato è: Commander.

Se {num_cards} è uguale a 100, elabora tutte le carte presenti nell'elenco e poi fornisci un'analisi che includa:

A) Punti di forza: sinergie, coerenza tematica e strategie efficaci.

B) Punti di debolezza: carenze di risorse, squilibri o vulnerabilità.

C) Suggerimenti strategici: idee per ottimizzare la strategia di gioco.

D) Sostituzioni, alternative: suggerimenti per sostituire carte e bilanciare il mazzo,
   tenendo conto dei colori presenti.

Se {num_cards} è invece inferiore a 100, che è il numero di carte necessarie per giocare a commander, suggerisci invece come completare il mazzo ed evita completamente i punti A,B,C,D. 

Non iniziare la risposta elencando l'elenco delle carte o Numero totale di carte o Costo medio in mana (CMC) o Colori del mazzo.
"""
        )
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}"
        }
        data = {
            "model": "gpt-4o-mini",
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.7
        }
        response = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=data)
        response.raise_for_status()
        result = response.json()
        advice = result["choices"][0]["message"]["content"].strip()
        return advice
    except Exception as e:
        print("Errore nella generazione del consiglio:", e)
    return (
        "Consiglio: Valuta attentamente il rapporto costo-efficacia delle tue carte e considera eventuali alternative per migliorare l'equilibrio del mazzo."
    )

def load_card_list_from_text(text):
    lines = text.splitlines()
    pdf_cards = []  # lista unica per il PDF
    ai_cards_dict = OrderedDict()  # conta le carte mantenendo l'ordine
    for line in lines:
        line = line.strip()
        if not line:
            continue
        match = re.match(r'^(\d+)\s+(.+)$', line)
        if match:
            count = int(match.group(1))
            card_name = match.group(2).strip()
        else:
            count = 1
            card_name = line
        if card_name not in pdf_cards:
            pdf_cards.append(card_name)
        if card_name in ai_cards_dict:
            ai_cards_dict[card_name] += count
        else:
            ai_cards_dict[card_name] = count
    ai_cards = [f"{count} {card}" for card, count in ai_cards_dict.items()]
    return pdf_cards, ai_cards, ai_cards_dict

def draw_mana_cost(c, mana_cost, x, y, symbol_width=15, symbol_height=15):
    from PIL import Image
    symbols = re.findall(r'\{([^}]+)\}', mana_cost)
    for symbol in symbols:
        image_path = os.path.join(MANA_SYMBOLS_DIR, f"{symbol}.png")
        if os.path.exists(image_path):
            try:
                img = Image.open(image_path).convert("RGBA")
                background = Image.new("RGBA", img.size, (255, 255, 255, 255))
                composite = Image.alpha_composite(background, img)
                composite = composite.convert("RGB")
                img_reader = ImageReader(composite)
                c.drawImage(img_reader, x, y, width=symbol_width, height=symbol_height, preserveAspectRatio=True)
            except Exception as e:
                print(f"Errore nel disegno del simbolo mana {symbol}: {e}")
        else:
            c.setFont(FONT_NAME, symbol_height)
            c.drawString(x, y, symbol)
        x += symbol_width + 2

def draw_summary_page(c, current_y, page_width, total_height, margin_left, margin_right,
                      num_cards, summary_total_price, avg_price, avg_cmc, ai_cards, deck_colors,
                      pre_generated_advice=None):
    c.setFont(FONT_BOLD, 20)
    c.drawCentredString(page_width / 2, current_y - 50, "Riassunto e Consigli")
    c.setFont(FONT_NAME, 14)
    summary_text = (
        f"Numero totale di carte: {num_cards}\n"
        f"Prezzo totale: {summary_total_price:.2f}€\n"
        f"Prezzo medio per carta: {avg_price:.2f}€\n"
        f"Colori del deck: {deck_colors}\n"
        f"Costo medio in mana (CMC): {avg_cmc:.2f}\n"
        f"Valutazione e consigli:\n"
    )
    text_object = c.beginText(margin_left, current_y - 80)
    for line in summary_text.split("\n"):
        text_object.textLine(line)
    c.drawText(text_object)

    if pre_generated_advice is None:
        advice = generate_targeted_advice(num_cards, summary_total_price, avg_price, avg_cmc, ai_cards, deck_colors)
    else:
        advice = pre_generated_advice

    formatted_advice = simple_markdown_to_rl(advice)
    styles = getSampleStyleSheet()
    advice_style = ParagraphStyle(
        "AdviceStyle",
        parent=styles["Normal"],
        fontName=FONT_NAME,
        fontSize=12,
        leading=14
    )
    advice_paragraph = Paragraph(formatted_advice, advice_style)
    available_width = page_width - margin_left - margin_right
    _, advice_height = advice_paragraph.wrap(available_width, total_height)
    advice_y = current_y - 180 - advice_height
    advice_paragraph.drawOn(c, margin_left, advice_y)
    summary_height = 180 + advice_height
    current_y -= summary_height
    return current_y

def create_pdf(pdf_cards, ai_cards, card_counts, output_pdf, generation_mode="both",
               lands_exclusion="none", version_exclusion="include", progress_callback=None):
    header_top_margin = 20
    header_font_size = 16
    header_height = header_top_margin + header_font_size + 10

    main_img_x = 50
    main_img_width = 200
    main_img_height = 280
    main_top_margin = header_height

    margin_left = 50
    margin_right = 50
    page_width, _ = letter
    available_width = page_width - margin_left - margin_right
    grid_img_width = 90
    grid_img_height = 110
    grid_spacing_x = 15
    grid_spacing_y = 35
    grid_cols = max(1, int((available_width + grid_spacing_x) // (grid_img_width + grid_spacing_x)))

    margin_bottom = 100
    base_summary_height = 180
    extra_space = 800

    cards_info = []
    total_cards_height = 0
    summary_total_price = 0.0
    total_count = 0
    summary_total_cmc = 0.0
    deck_colors_set = set()

    for card_name in pdf_cards:
        count = card_counts.get(card_name, 1)
        main_data = fetch_card_data(card_name, lang="en")
        if not main_data:
            continue

        if lands_exclusion == "basic":
            basic_lands = {"plains", "island", "swamp", "mountain", "forest"}
            if card_name.lower() in basic_lands:
                print(f"Escludo '{card_name}' perché è una basic land.")
                continue
        elif lands_exclusion == "all":
            type_line = main_data.get("type_line", "")
            if "Land" in type_line:
                print(f"Escludo '{card_name}' perché è una land.")
                continue

        total_count += count
        if "colors" in main_data:
            deck_colors_set.update(main_data["colors"])

        if version_exclusion == "exclude":
            printing_data = []
        else:
            prints_uri = main_data.get("prints_search_uri")
            printing_data = []
            if prints_uri:
                try:
                    import requests
                    response = requests.get(prints_uri)
                    response.raise_for_status()
                    printing_data = response.json().get("data", [])
                except Exception as e:
                    print(f"Errore nel recupero delle stampe per '{card_name}': {e}")

        text_it = get_card_text_in_italian(card_name)
        price_info = get_card_price(card_name)
        main_img_path = download_card_image(card_name)

        if printing_data:
            grid_top_margin = 20
            rows = math.ceil(len(printing_data) / grid_cols)
            prints_height = rows * (grid_img_height + grid_spacing_y) - grid_spacing_y
        else:
            grid_top_margin = 0
            prints_height = 0

        card_height = header_height + main_img_height + grid_top_margin + prints_height + margin_bottom
        total_cards_height += card_height

        prices = main_data.get("prices", {})
        price_value = None
        if prices.get("eur"):
            try:
                price_value = float(prices["eur"])
            except Exception:
                pass
        elif prices.get("usd"):
            try:
                from scryfall_api import USD_TO_EUR
                price_value = float(prices["usd"]) * USD_TO_EUR
            except Exception:
                pass
        if price_value is not None:
            summary_total_price += price_value * count
        cmc = main_data.get("cmc", 0)
        summary_total_cmc += cmc * count

        cards_info.append({
            "card_name": card_name,
            "main_data": main_data,
            "printing_data": printing_data,
            "text_it": text_it,
            "price_info": price_info,
            "main_img_path": main_img_path,
            "card_height": card_height,
            "grid_top_margin": grid_top_margin,
            "prints_height": prints_height,
            "count": count
        })

    num_cards = total_count
    avg_price = summary_total_price / total_count if total_count > 0 else 0
    avg_cmc = summary_total_cmc / total_count if total_count > 0 else 0
    deck_colors = ", ".join(sorted(deck_colors_set)) if deck_colors_set else "Colorless"

    if generation_mode in ("both", "suggestions"):
        styles = getSampleStyleSheet()
        advice_style = ParagraphStyle(
            "AdviceStyle",
            parent=styles["Normal"],
            fontName=FONT_NAME,
            fontSize=12,
            leading=14
        )
        formatted_advice = ""
        advice_paragraph = Paragraph(formatted_advice, advice_style)
        _, advice_height = advice_paragraph.wrap(available_width, 999999)
        summary_height = 160 + advice_height
    else:
        summary_height = 0

    if generation_mode in ("both", "suggestions"):
        summary_height = max(summary_height, base_summary_height) + 200
    else:
        summary_height = 0

    if generation_mode == "both":
        total_height = summary_height + total_cards_height + extra_space
    elif generation_mode == "cards":
        total_height = total_cards_height + extra_space
    elif generation_mode == "suggestions":
        total_height = summary_height + 200

    c = canvas.Canvas(output_pdf, pagesize=(page_width, total_height))
    current_y = total_height

    if generation_mode in ("both", "suggestions"):
        current_y = draw_summary_page(
            c, current_y, page_width, total_height, margin_left, margin_right,
            num_cards, summary_total_price, avg_price, avg_cmc, ai_cards, deck_colors
        )

    if generation_mode in ("both", "cards"):
        for idx, info in enumerate(cards_info):
            card_name = info["card_name"]
            printing_data = info["printing_data"]
            text_it = info["text_it"]
            price_info = info["price_info"]
            main_img_path = info["main_img_path"]
            card_height = info["card_height"]
            grid_top_margin = info["grid_top_margin"]
            main_data = info["main_data"]

            base_y = current_y

            c.setFont(FONT_BOLD, header_font_size)
            c.drawString(50, base_y - header_top_margin, card_name)

            main_img_y = base_y - main_top_margin - main_img_height
            if main_img_path:
                try:
                    from PIL import Image
                    img = Image.open(main_img_path)
                    img_reader = ImageReader(img)
                    c.drawImage(
                        img_reader, 50, main_img_y,
                        width=main_img_width, height=main_img_height,
                        preserveAspectRatio=True
                    )
                except Exception as e:
                    print(f"Errore nel disegno dell'immagine principale per '{card_name}': {e}")

            current_text_x = 50 + main_img_width + 20
            text_y = base_y - main_top_margin - 20

            c.setFont(FONT_BOLD, 12)
            c.drawString(current_text_x, text_y, "Effetto:")
            text_y -= 15

            styles = getSampleStyleSheet()
            effect_style = ParagraphStyle(
                "EffectStyle",
                parent=styles["Normal"],
                fontName=FONT_NAME,
                fontSize=12,
                leading=14
            )
            effect_text = text_it.replace("\n", "<br/>")
            effect_paragraph = Paragraph(effect_text, effect_style)
            available_effect_width = page_width - current_text_x - margin_right
            w_eff, h_eff = effect_paragraph.wrap(available_effect_width, text_y)
            effect_paragraph.drawOn(c, current_text_x, text_y - h_eff)
            text_y -= (h_eff + 15)

            c.setFont(FONT_BOLD, 12)
            c.drawString(current_text_x, text_y, "Prezzo:")
            text_y -= 15
            c.setFont(FONT_NAME, 10)
            if price_info.strip() == "Prezzo non disponibile":
                price_info += "\n"
            for line in price_info.split("\n"):
                c.drawString(current_text_x, text_y, line)
                text_y -= 15

            mana_cost = main_data.get("mana_cost", "")
            if mana_cost:
                c.setFont(FONT_BOLD, 12)
                c.drawString(current_text_x, text_y, "Costo in mana:")
                text_y -= 20
                draw_mana_cost(c, mana_cost, current_text_x, text_y, symbol_width=15, symbol_height=15)
                text_y -= 20

            artist = main_data.get("artist", "Artista non disponibile")
            c.setFont(FONT_BOLD, 12)
            c.drawString(current_text_x, text_y, "Artista:")
            text_y -= 15
            c.setFont(FONT_NAME, 10)
            c.drawString(current_text_x, text_y, artist)
            text_y -= 20

            if printing_data:
                grid_start_y = main_img_y - grid_top_margin - 120
                col = 0
                row = 0
                for printing in printing_data:
                    print_img_path = download_printing_image_small(printing)
                    x = margin_left + col * (grid_img_width + grid_spacing_x)
                    y = grid_start_y - row * (grid_img_height + grid_spacing_y)
                    if print_img_path:
                        try:
                            from PIL import Image
                            img = Image.open(print_img_path)
                            img_reader = ImageReader(img)
                            c.drawImage(
                                img_reader, x, y,
                                width=grid_img_width, height=grid_img_height,
                                preserveAspectRatio=True
                            )
                        except Exception as e:
                            print(f"Errore nel disegno dell'immagine per una stampa di '{card_name}': {e}")
                    set_name = printing.get("set_name", "Sconosciuto")
                    released_at = printing.get("released_at", "Data sconosciuta")
                    if released_at != "Data sconosciuta" and len(released_at) >= 4:
                        released_at = released_at[:4]
                        combined_text = f"{set_name} - {released_at}"
                    else:
                        combined_text = set_name
                    prices_printing = printing.get("prices", {})
                    price_str = None
                    if prices_printing.get("eur"):
                        price_str = prices_printing.get("eur")
                    elif prices_printing.get("usd"):
                        try:
                            price_str = f"{round(float(prices_printing.get('usd')) * 1, 2)}"
                        except Exception:
                            price_str = None
                    if price_str:
                        combined_text += f" - {price_str}€"
                    set_style = ParagraphStyle(
                        "SetStyle",
                        parent=styles["Normal"],
                        fontName=FONT_NAME,
                        fontSize=8,
                        leading=10
                    )
                    available_set_width = grid_img_width - 10
                    set_paragraph = Paragraph(combined_text, set_style)
                    w_set, h_set = set_paragraph.wrap(available_set_width, grid_img_height)
                    set_paragraph.drawOn(c, x + 5, y - h_set)
                    col += 1
                    if col >= grid_cols:
                        col = 0
                        row += 1

            available_mech_width = page_width - current_text_x - margin_right
            import json
            vocab_path = os.path.join(os.path.dirname(__file__), "data", "vocab_wiki.json")
            try:
                with open(vocab_path, "r", encoding="utf-8") as f:
                    vocab = json.load(f)
            except Exception as e:
                print(f"Errore nel caricamento del vocabolario: {e}")
                vocab = {}
            mechanics_found = []
            text_en = main_data.get("oracle_text", "")
            for mechanic in vocab.keys():
                if re.search(r'\b' + re.escape(mechanic) + r'\b', text_en, re.IGNORECASE):
                    mechanics_found.append(mechanic)
            c.setFont(FONT_BOLD, 12)
            c.drawString(current_text_x, text_y, "Meccaniche:")
            text_y -= 25
            if mechanics_found:
                c.setFont(FONT_NAME, 10)
                current_x = current_text_x
                for idx, mechanic in enumerate(mechanics_found):
                    mech_text = mechanic
                    text_width = c.stringWidth(mech_text, FONT_NAME, 10)
                    c.drawString(current_x, text_y - 7, mech_text)
                    try:
                        from reportlab.pdfbase.pdfdoc import PDFDictionary, PDFName, PDFArray, PDFString
                        ann = PDFDictionary()
                        ann["Type"] = PDFName("Annot")
                        ann["Subtype"] = PDFName("Text")
                        ann["Rect"] = PDFArray([current_x, text_y, current_x + text_width, text_y + 10])
                        ann["Contents"] = PDFString(vocab.get(mechanic, "Descrizione non disponibile"))
                        ann["T"] = PDFString(mechanic)
                        c._addAnnotation(ann)
                    except Exception as e:
                        print(f"Errore nell'aggiunta dell'annotazione per {mechanic}: {e}")
                    comma_space = c.stringWidth(", ", FONT_NAME, 10)
                    current_x += text_width
                    if idx < len(mechanics_found) - 1:
                        c.drawString(current_x, text_y, ", ")
                        current_x += comma_space
                text_y -= 15
            else:
                c.setFont(FONT_NAME, 10)
                c.drawString(current_text_x, text_y, "Nessuna meccanica trovata.")
                text_y -= 15

            line_y = base_y - card_height + margin_bottom - 60
            c.setLineWidth(1)
            c.line(30, line_y, page_width - 30, line_y)
            current_y -= card_height
            if progress_callback:
                progress_callback(idx + 1, len(cards_info))
    c.save()
    print(f"PDF creato: {output_pdf}")
