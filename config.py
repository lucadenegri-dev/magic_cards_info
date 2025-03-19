# config.py
import os
from dotenv import load_dotenv

# Carica le variabili d'ambiente dal file .env (assumiamo che sia in assets/)
dotenv_path = os.path.join(os.path.dirname(__file__), 'assets', '.env')
load_dotenv(dotenv_path)

# Directory di base e risorse
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
ASSETS_DIR = os.path.join(BASE_DIR, 'assets')
CARD_IMAGES_DIR = os.path.join(ASSETS_DIR, 'card_images')
FONTS_DIR = os.path.join(ASSETS_DIR, 'fonts')
MANA_SYMBOLS_DIR = os.path.join(ASSETS_DIR, 'mana_symbols')

# Crea la cartella delle immagini se non esiste
os.makedirs(CARD_IMAGES_DIR, exist_ok=True)

# API endpoints e costanti
SCRYFALL_BASE_URL = "https://api.scryfall.com"
EXCHANGE_RATE_URL = "https://api.exchangerate.host/latest?base=USD&symbols=EUR"

# Impostazioni del rate limiter
REQUEST_LIMIT = 200
PAUSE_TIME = 60
DELAY_BETWEEN = 0.1
MAX_RETRIES = 3

# Tasso di cambio di default
DEFAULT_USD_TO_EUR = 0.92

# Percorsi dei font
CRIMSON_FONT = os.path.join(FONTS_DIR, 'CrimsonText-Regular.ttf')
BELEREN_BOLD_FONT = os.path.join(FONTS_DIR, 'Beleren-Bold.ttf')

# Font di fallback
DEFAULT_FONT_NAME = 'Helvetica'

# Dimensioni della pagina (usando ReportLab; letter è una tuple)
from reportlab.lib.pagesizes import letter
PAGE_SIZE = letter
