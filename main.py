from __future__ import annotations

from fastapi.staticfiles import StaticFiles
import os
import random
import string
import time
import asyncio
import re
import unicodedata
import base64
import binascii
import hashlib
import textwrap
import math
import io
from difflib import SequenceMatcher
from typing import Any, Dict, List, Optional, Literal, Tuple
from urllib.parse import unquote, urlparse

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import json
from pathlib import Path

try:
    from PIL import Image
except Exception:
    Image = None

DATA_DIR = Path("data")
CORE_FILE = DATA_DIR / "core_questions.json"
IMAGE_FILE = DATA_DIR / "image_questions.json"
CONSENSUS_FILE = DATA_DIR / "consensus_dilemmas.json"
DISABLED_CONSENSUS_FILE = DATA_DIR / "disabled_consensus_dilemmas.json"
USED_TRUSTED_REAL_IMAGE_FILE = DATA_DIR / "used_trusted_real_images.json"
RECENT_IMAGE_SCENE_FILE = DATA_DIR / "recent_image_scene_keys.json"
ALL_TIME_RANKING_FILE = DATA_DIR / "all_time_ranking.json"
QUESTION_IMAGE_DIR = Path("static") / "question-images"
UPLOADED_IMAGE_DIR = QUESTION_IMAGE_DIR / "uploads"
GENERATED_IMAGE_DIR = QUESTION_IMAGE_DIR / "generated"
PDF_ASSET_DIR = Path("static") / "pdf-assets"
GROUP_EVALUATION_BACKGROUND_FILE = PDF_ASSET_DIR / "group-evaluation-background.png"
AICO_REPORT_IMAGE_FILE = Path("static") / "Aico.png"
AI_GENERATION_MAX_ATTEMPTS = 4
AI_IMAGE_POOL_TARGET_COUNT = 24
AI_IMAGE_POOL_TARGET_VARIETY = 16
AI_IMAGE_POOL_GENERATION_BATCH = 4
IMAGE_ROUND_RECENT_SCENE_LIMIT = 10
MAX_TEACHER_IMAGE_BYTES = 8 * 1024 * 1024
AUTO_IMAGE_SET_MIN_COUNT = 2
AUTO_IMAGE_SET_MAX_COUNT = 6
ALLOWED_TEACHER_IMAGE_MIME_TYPES = {
    "image/png": ".png",
    "image/jpeg": ".jpg",
    "image/webp": ".webp",
    "image/gif": ".gif",
}
OPENAI_IMAGE_OUTPUT_EXTENSIONS = {
    "png": ".png",
    "jpeg": ".jpg",
    "webp": ".webp",
}
OPENAI_IMAGE_OUTPUT_MIME_TYPES = {
    "png": "image/png",
    "jpeg": "image/jpeg",
    "webp": "image/webp",
}
IMAGE_BINARY_OPTIONS = [
    "Waarschijnlijk AI-gegenereerd of bewerkt",
    "Waarschijnlijk een echte foto",
]
AUTO_IMAGE_QUESTION_VARIANTS = [
    "Kijk goed: is dit waarschijnlijk een echte foto of een AI-beeld?",
    "Denk je dat deze foto echt is, of door AI gegenereerd of bewerkt?",
    "Wat denk je: zie je hier een echte foto of een AI-beeld?",
]
TRUSTED_REAL_IMAGE_LIBRARY = [
    {
        "id": "trusted_real_wikimedia_cat_window",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:Cat_In_A_Window.jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Cat_In_A_Window.jpg",
        "image_alt": "Kat die uit een raam kijkt met gevelbekleding op de achtergrond",
        "question": "Kijk goed: is dit waarschijnlijk een echte foto of een AI-beeld?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. De snorharen, vachtstructuur en weerspiegelingen in het raam blijven overal logisch. "
            "Tip: kijk bij twijfel naar fijne randen zoals haren, glasreflecties en rechte lijnen rond het venster."
        ),
    },
    {
        "id": "trusted_real_wikimedia_market_rain",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:USDA_Farmers_Market_Rainy_Opening_(9128285098).jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/USDA_Farmers_Market_Rainy_Opening_(9128285098).jpg",
        "image_alt": "Straatmarkt in de regen met paraplu's en natte straatstenen",
        "question": "Wat denk je: zie je hier een echte foto of een AI-beeld?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. De natte straat, paraplu's en mensen reageren allemaal geloofwaardig op hetzelfde licht en weer. "
            "Tip: kijk of schaduwen, reflecties en drukke achtergronden overal dezelfde logica volgen."
        ),
    },
    {
        "id": "trusted_real_wikimedia_tomatoes_greenhouse",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:Tomatoes_in_Greenhouse_(28270013041).jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Tomatoes_in_Greenhouse_(28270013041).jpg",
        "image_alt": "Tomatenplanten in een broeikas met bladeren en rekken",
        "question": "Denk je dat deze foto echt is, of door AI gegenereerd of bewerkt?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. De planten tonen natuurlijke variatie: bladeren verschillen licht van vorm, en de diepte in de serre blijft consequent. "
            "Tip: let op herhaling. AI maakt patronen vaak te netjes of laat details plots verspringen."
        ),
    },
    {
        "id": "trusted_real_wikimedia_train_interior",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:R160_G_Train_Interior.jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/R160_G_Train_Interior.jpg",
        "image_alt": "Interieur van een treinwagon met stoelen, ramen en gangpad",
        "question": "Kijk goed: is dit waarschijnlijk een echte foto of een AI-beeld?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. De perspectieflijnen van stoelen, ramen en plafond blijven netjes doorlopen zonder vreemde breuken. "
            "Tip: kijk in interieurs vooral naar herhalende vormen. Bij AI loopt zo'n patroon vaak ergens net mis."
        ),
    },
    {
        "id": "trusted_real_wikimedia_bike_rack",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:Bike_Rack.jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Bike_Rack.jpg",
        "image_alt": "Fietsenrek met meerdere fietsen op een open plein",
        "question": "Wat denk je: zie je hier een echte foto of een AI-beeld?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. De metalen buizen, fietswielen en schaduwen blijven overal op dezelfde manier in perspectief staan. "
            "Tip: kijk bij fietsen naar spaken, kettingen en overlappende buizen; daar maakt AI vaak kleine fouten."
        ),
    },
    {
        "id": "trusted_real_wikimedia_bus_interior",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:LACMTA_bus_interior.jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/LACMTA_bus_interior.jpg",
        "image_alt": "Binnenkant van een bus met stoelen, stangen en ramen",
        "question": "Kijk goed: is dit waarschijnlijk een echte foto of een AI-beeld?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. De stangen, stoelranden en raamreflecties lopen allemaal consequent door zonder vreemde verdraaiingen. "
            "Tip: let in voertuigen op rechte lijnen en herhalende stoelpatronen; AI laat daar snel kleine breuken zien."
        ),
    },
    {
        "id": "trusted_real_wikimedia_washington_greenhouse",
        "source": "wikimedia",
        "source_label": "Wikimedia Commons",
        "source_url": "https://commons.wikimedia.org/wiki/File:Washington%27s_greenhouse.jpg",
        "image_url": "https://commons.wikimedia.org/wiki/Special:Redirect/file/Washington%27s_greenhouse.jpg",
        "image_alt": "Buitenzicht van een greenhouse of serre vanuit schuin perspectief",
        "question": "Wat denk je: zie je hier een echte foto of een AI-beeld?",
        "explanation": (
            "Dit is een echte foto uit Wikimedia Commons. Metselwerk, ramen en perspectief blijven logisch en tonen kleine natuurlijke onregelmatigheden. "
            "Tip: echte foto's hebben vaak kleine imperfecties, maar geen onmogelijke vervormingen in stenen, raamranden of hoeken."
        ),
    },
]
WIKIMEDIA_COMMONS_HOSTS = {
    "commons.wikimedia.org",
    "upload.wikimedia.org",
}
AUTO_IMAGE_SCENE_LIBRARY = [
    {
        "label": "rommelige klasbank",
        "alt": "Rommelige klasbank met schriften, pennen en een drinkfles",
        "prompt": "A candid smartphone photo of a messy classroom desk with open notebooks, colored pens, a pencil case and a reusable water bottle in soft afternoon daylight.",
    },
    {
        "label": "natte hond in park",
        "alt": "Natte hond die zich uitschudt in een park",
        "prompt": "A casual phone photo of a wet dog shaking off water near a park bench after rain, with natural motion blur and realistic outdoor lighting.",
    },
    {
        "label": "keukentafel met pannenkoeken",
        "alt": "Bord met pannenkoeken en bessen op een keukentafel",
        "prompt": "A photorealistic phone snapshot of pancakes with berries and powdered sugar on a kitchen table, with everyday mess and natural window light.",
    },
    {
        "label": "treinwagon met rugzak",
        "alt": "Rugzak op een stoel in een treinwagon",
        "prompt": "A realistic commuter train interior photographed with a phone, showing a backpack on a seat and a few blurred passengers in the background.",
    },
    {
        "label": "locker room sportschoenen",
        "alt": "Modderige sportschoenen naast een sporttas in een kleedkamer",
        "prompt": "A candid locker room photo with muddy football shoes beside a sports bag and a bench, lit by ordinary indoor lighting.",
    },
    {
        "label": "zwarte kat op vensterbank",
        "alt": "Zwarte kat die zich uitrekt op een vensterbank tussen kamerplanten",
        "prompt": "A natural-looking phone photo of a black cat stretching on a windowsill next to houseplants on a cloudy day.",
    },
    {
        "label": "markt in de regen",
        "alt": "Straatmarkt in de regen met paraplu's en fruitkramen",
        "prompt": "A documentary-style phone photo of a rainy street market with umbrellas, fruit crates and reflections on wet pavement.",
    },
    {
        "label": "broeikas met tomatenplanten",
        "alt": "Kleine broeikas met tomatenplanten en tuinhandschoenen",
        "prompt": "A believable smartphone photo inside a small greenhouse with tomato plants, a wooden crate and gardening gloves.",
    },
    {
        "label": "fietsrekken na school",
        "alt": "Rij fietsen aan een fietsenrek op een schoolplein",
        "prompt": "A realistic phone photo of bicycle racks after school with backpacks, puddles and late afternoon light.",
    },
    {
        "label": "voetbalkleedkamer",
        "alt": "Voetbalshirts en sporttassen in een kleedkamer",
        "prompt": "A candid smartphone photo inside a football locker room with shirts, sports bags and a damp floor after training.",
    },
    {
        "label": "bibliotheektafel met boeken",
        "alt": "Open boeken en notities op een tafel in een bibliotheek",
        "prompt": "A natural phone snapshot of an old wooden library table with open books, handwritten notes and soft indoor lighting.",
    },
    {
        "label": "skatepark bij zonsondergang",
        "alt": "Skateboard op de grond in een skatepark bij zonsondergang",
        "prompt": "A documentary-style smartphone photo of a skateboard lying near a concrete ramp in a skatepark during sunset.",
    },
    {
        "label": "aquarium met vissen",
        "alt": "Kleine vissen in een aquarium met planten en grind",
        "prompt": "A believable close smartphone photo of a home aquarium with small fish, aquatic plants and gravel, lit by the tank light.",
    },
    {
        "label": "bakplaat met koekjes",
        "alt": "Versgebakken koekjes op een metalen bakplaat",
        "prompt": "A casual kitchen phone photo of freshly baked cookies cooling on a metal baking tray with crumbs and oven mitts nearby.",
    },
    {
        "label": "busrit in de ochtend",
        "alt": "Binnenkant van een bus met lege stoelen en ochtendlicht",
        "prompt": "A realistic commuter bus interior photographed with a phone in the morning, with empty seats, window reflections and soft sunlight.",
    },
    {
        "label": "campingtafel buiten",
        "alt": "Campingtafel met bekers, kaarten en een zaklamp buiten",
        "prompt": "A natural evening phone photo of a camping table outside with cups, playing cards, a flashlight and a cool blue dusk sky.",
    },
    {
        "label": "museumzaal met schilderijen",
        "alt": "Gang in een museum met schilderijen aan de muur",
        "prompt": "A photorealistic smartphone photo inside a museum gallery with framed paintings, polished floors and a few visitors in the distance.",
    },
    {
        "label": "hond aan keukendeur",
        "alt": "Hond die aan een glazen keukendeur staat",
        "prompt": "A casual phone photo of a dog standing by a glass kitchen door on a rainy day with natural indoor lighting.",
    },
    {
        "label": "speeltuin na regen",
        "alt": "Lege speeltuin met natte glijbaan en plassen",
        "prompt": "A believable smartphone photo of an empty playground after rain with puddles, a wet slide and overcast light.",
    },
]
AI_SCENE_EXPLANATION_HINTS = {
    "rommelige klasbank met schriften pennen en een drinkfles": (
        "Op de klasbank klopt de tekst op het etiket of op een schrift niet helemaal, en een pen of maprand lijkt net in een ander voorwerp te versmelten. "
        "Tip: kijk heel precies naar letters, rechte randen en plekken waar pennen, papier en flesjes elkaar raken."
    ),
    "natte hond die zich uitschudt in een park": (
        "Bij de hond lopen sommige waterdruppels en haren niet logisch mee met de beweging, alsof enkele stukjes los van elkaar zweven. "
        "Tip: let op de rand van de vacht, de vorm van de poten en of opspattend water overal dezelfde richting volgt."
    ),
    "bord met pannenkoeken en bessen op een keukentafel": (
        "Bij de pannenkoeken zie je dat poedersuiker, bessen of de rand van het bord op sommige plekken vreemd in elkaar overlopen. "
        "Tip: kijk naar kleine eetdetails zoals kruimels, schaduwen op de tafel en de precieze contour van het bestek."
    ),
    "rugzak op een stoel in een treinwagon": (
        "De rugzakriem of stoelrand buigt ergens net onlogisch af, en een raamreflectie volgt niet helemaal hetzelfde perspectief als de wagon. "
        "Tip: controleer in voertuigen vooral rechte lijnen, herhalende stoelvormen en spiegelingen in de ramen."
    ),
    "modderige sportschoenen naast een sporttas in een kleedkamer": (
        "De veters of moddersporen op de sportschoenen lijken op enkele plekken in elkaar te smelten, en de sporttas heeft een plooi die niet logisch doorloopt. "
        "Tip: zoom in op veters, ritsen en modderranden; daar verraadt AI zich vaak het snelst."
    ),
    "zwarte kat die zich uitrekt op een vensterbank tussen kamerplanten": (
        "Bij de kat of de planten zie je dat enkele snorharen, bladeren of raamranden niet mooi scherp en logisch doorlopen. "
        "Tip: let op dunne lijnen zoals snorharen, bladstelen en de reflectie in het glas."
    ),
    "straatmarkt in de regen met paraplu s en fruitkramen": (
        "Een paraplu, kraamrand of natte weerspiegeling klopt net niet met de rest van het beeld, alsof een stukje vervormd is. "
        "Tip: kijk in regenfoto's naar spiegelingen op de grond, de spaken van paraplu's en de vorm van fruitbakken."
    ),
    "kleine broeikas met tomatenplanten en tuinhandschoenen": (
        "Sommige bladeren, stokken of touwtjes in de broeikas lopen niet logisch door en lijken plots van vorm te veranderen. "
        "Tip: volg een plantsteel of rekje van begin tot einde en kijk waar een lijn onverwacht verspringt."
    ),
    "rij fietsen aan een fietsenrek op een schoolplein": (
        "Bij een paar fietsen zie je dat spaken, kettingen of framebuizen niet helemaal logisch op elkaar aansluiten. "
        "Tip: kijk bij fietsen naar ronde vormen, overlappende stangen en de open ruimtes tussen de spaken."
    ),
    "voetbalshirts en sporttassen in een kleedkamer": (
        "Een shirtcijfer, kapstok of tasriem lijkt ergens vervormd, alsof een detail half verdwenen is. "
        "Tip: let op nummers, ritsen, riemen en herhalende haakjes aan de muur."
    ),
    "open boeken en notities op een tafel in een bibliotheek": (
        "Op de boekenrug of in de notities staan letters die net niet leesbaar zijn, en een paginarand loopt vreemd in de schaduw door. "
        "Tip: kijk heel precies naar tekst, paginaranden en de hoek van stapels papier."
    ),
    "skateboard op de grond in een skatepark bij zonsondergang": (
        "Een wiel of truck van het skateboard staat net in een onmogelijke hoek, of de schaduw volgt niet mooi de vorm van het bord. "
        "Tip: controleer ronde wielen, schroeven en of de schaduw dezelfde richting houdt als het licht."
    ),
    "kleine vissen in een aquarium met planten en grind": (
        "Bij een vis of glasreflectie zie je dat een vin, oog of plantenstengel net niet logisch verderloopt. "
        "Tip: let op doorzichtige randen, dubbele reflecties in het glas en heel fijne vinnen."
    ),
    "versgebakken koekjes op een metalen bakplaat": (
        "Een koekje of kruimelrand lijkt ergens samen te smelten met de bakplaat of het bakpapier, waardoor de vorm net niet klopt. "
        "Tip: kijk naar kleine kruimels, de rand van het papier en de schaduw onder de koekjes."
    ),
    "binnenkant van een bus met lege stoelen en ochtendlicht": (
        "Een stoelrand, stang of raamreflectie loopt net niet mooi door, alsof één stuk perspectief verschoven is. "
        "Tip: let in bussen op parallelle lijnen, stoelpatronen en de spiegeling in de ramen."
    ),
    "campingtafel met bekers kaarten en een zaklamp buiten": (
        "De symbolen op de kaarten of de rand van een beker lijken een beetje vervormd, alsof het detail half herschreven is. "
        "Tip: kijk naar speelkaarten, ronde bekerranden en kleine voorwerpen die dicht bij elkaar liggen."
    ),
    "gang in een museum met schilderijen aan de muur": (
        "Een kaderhoek of lijst van een schilderij klopt net niet met het perspectief van de rest van de gang. "
        "Tip: volg de rechte lijnen van kaders, vloerplanken en spots aan het plafond."
    ),
    "hond die aan een glazen keukendeur staat": (
        "Bij de hond of in het glas zie je dat een poot, snuit of weerspiegeling niet precies overeenkomt met de rest van het lichaam. "
        "Tip: kijk naar reflecties in het raam en naar de overgang tussen vacht, poot en deurstijl."
    ),
    "lege speeltuin met natte glijbaan en plassen": (
        "Een ketting, leuning of weerspiegeling in een plas verandert ergens subtiel van vorm terwijl dat niet logisch is. "
        "Tip: let op herhalende metalen delen, natte reflecties en de precieze rand van de glijbaan."
    ),
}
GENERIC_AI_EXPLANATION_MARKERS = [
    "dit beeld werd met ai gemaakt",
    "kijk bij zulke fotos extra",
    "kijk bij zulke foto s extra",
    "kan wijzen op ai",
    "kunnen soms",
    "lijken soms",
    "let op of er rare vormen",
    "de kat en de planten zien er heel natuurlijk uit",
]
THEMES = {
    "werking": {
        "label": "Hoe werkt AI?",
        "color": "#3498DB"
    },
    "leefwereld": {
        "label": "AI in jouw leefwereld",
        "color": "#2ECC71"
    },
    "kritisch": {
        "label": "Kritisch, veilig en verantwoord",
        "color": "#E74C3C"
    },
    "kansen": {
        "label": "Voordelen en kansen",
        "color": "#F39C12"
    },
    "beeld": {
        "label": "AI-foto's herkennen",
        "color": "#5B7C99"
    }
}
THEME_ALIASES = {
    "verantwoord": "kritisch",
    "risicos": "kritisch",
    "beeldronde": "beeld",
}
QUESTION_DIFFICULTIES = {
    "basis": {
        "label": "Niveau 1 · Basis",
        "short_label": "Basis",
    },
    "verdieping": {
        "label": "Niveau 2 · Verdieping",
        "short_label": "Verdieping",
    },
    "uitdaging": {
        "label": "Niveau 3 · Uitdaging",
        "short_label": "Uitdaging",
    },
}
QUESTION_DIFFICULTY_ORDER = ["basis", "verdieping", "uitdaging"]
QUESTION_DIFFICULTY_SELECTION_PRIORITY = ["verdieping", "uitdaging", "basis"]
QUESTION_DIFFICULTY_ALIASES = {
    "basis": "basis",
    "niveau1": "basis",
    "niveau-1": "basis",
    "level1": "basis",
    "easy": "basis",
    "verdieping": "verdieping",
    "niveau2": "verdieping",
    "niveau-2": "verdieping",
    "level2": "verdieping",
    "medium": "verdieping",
    "uitdaging": "uitdaging",
    "niveau3": "uitdaging",
    "niveau-3": "uitdaging",
    "level3": "uitdaging",
    "hard": "uitdaging",
}
QUESTION_DIFFICULTY_MODES = {
    "basis": {
        "label": "Basis",
        "description": "Kies vooral toegankelijkere vragen.",
    },
    "mix": {
        "label": "Mix",
        "description": "Wissel niveaus af met nadruk op stevige denkvragen.",
    },
    "uitdaging": {
        "label": "Uitdaging",
        "description": "Kies vooral de moeilijkere vragen.",
    },
}
QUESTION_DIFFICULTY_MODE_ALIASES = {
    "basis": "basis",
    "mix": "mix",
    "gemengd": "mix",
    "uitdaging": "uitdaging",
}
QUESTION_SCENARIO_MARKERS = (
    "een leerling",
    "een klasgenoot",
    "jij gebruikt",
    "stel dat",
    "je wil",
    "je gebruikt",
    "op school",
    "in de klas",
    "sociale media",
    "zoekmachine",
    "chatbot",
    "app",
)
QUESTION_ADVANCED_MARKERS = (
    "betrouw",
    "privacy",
    "vooroordeel",
    "bias",
    "transpar",
    "hallucin",
    "auteursrecht",
    "patroon",
    "algorit",
    "train",
    "prompt",
    "bron",
    "controle",
    "persoonsgegeven",
    "aanbevel",
)
QUESTION_CHALLENGE_MARKERS = (
    "beste",
    "meest",
    "sterkst",
    "eerst",
    "waarom",
    "waarschijnlijk",
    "verschil",
    "past het best",
    "veiligst",
    "eerlijkst",
    "controleer",
    "uitleg",
)
TRIVIAL_DISTRACTOR_MARKERS = (
    "alle bovenstaande",
    "geen van bovenstaande",
    "ik weet het niet",
    "maakt niet uit",
    "zomaar",
    "omdat ai slaapt",
    "omdat een robot liegt",
)
QUESTION_DIFFICULTY_GENERATION_GUIDANCE = {
    "basis": (
        "Maak een toegankelijke vraag op instapniveau. Laat leerlingen nadenken, "
        "maar hou de situatie overzichtelijk en vermijd te veel extra lagen."
    ),
    "verdieping": (
        "Maak een stevigere denkvraag. Laat minstens twee foute opties op het eerste zicht aannemelijk lijken, "
        "zodat leerlingen echt moeten vergelijken."
    ),
    "uitdaging": (
        "Maak een moeilijke doordenker. Zorg dat meerdere opties inhoudelijk dichtbij elkaar liggen en dat "
        "de juiste keuze afhangt van nuance, context of een kritische afweging."
    ),
}
KANSEN_THEME_SOURCE_IDS = {
    "core_leefwereld_2",
    "core_leefwereld_3",
    "core_leefwereld_18",
    "ai_3",
    "ai_5",
    "ai_19",
    "ai_35",
    "ai_52",
}
ETHICAL_AI_DILEMMAS = [
    {
        "id": "ethics_1",
        "question": "Een leerling laat AI bijna een volledige boekbespreking schrijven en past daarna alleen enkele zinnen aan. Is het eerlijk om dat werk als volledig eigen werk in te dienen? Waarom wel of niet?",
        "guidance": "Zoek samen een antwoord dat eerlijkheid, leerdoel en eigen inspanning mee afweegt."
    },
    {
        "id": "ethics_2",
        "question": "Een school wil AI gebruiken om te voorspellen welke leerlingen extra begeleiding nodig hebben. Is dat een goed idee als die voorspellingen soms fout kunnen zijn?",
        "guidance": "Bespreek samen de voordelen van hulp op tijd, maar ook het risico op fouten en oneerlijke labels."
    },
    {
        "id": "ethics_3",
        "question": "Een app met AI geeft heel snelle studietips, maar bewaart ook alles wat leerlingen intypen. Mag je zo'n app gebruiken op school?",
        "guidance": "Neem privacy, nut, toestemming en veiligheid mee in jullie consensus."
    },
    {
        "id": "ethics_4",
        "question": "Iemand maakt met AI een nepstem van een klasgenoot voor een grappig filmpje. Kan dat onschuldig zijn, of ga je dan over een grens?",
        "guidance": "Denk samen na over toestemming, respect en mogelijke gevolgen voor anderen."
    },
    {
        "id": "ethics_5",
        "question": "Een leraar gebruikt AI om sneller feedback op taken te geven. Mag dat als leerlingen niet precies weten welk deel door AI en welk deel door de leraar geschreven is?",
        "guidance": "Weeg samen snelheid, duidelijkheid, vertrouwen en transparantie af."
    },
    {
        "id": "ethics_6",
        "question": "Een AI-chatbot geeft een leerling raad over een persoonlijk probleem. Is het verstandig dat een leerling die raad volgt zonder met een volwassene te praten?",
        "guidance": "Let op hulp, verantwoordelijkheid, betrouwbaarheid en wanneer menselijke steun nodig is."
    },
]
CONSENSUS_PASSAGE_REWARD = 5
CONSENSUS_EXPLOSION_PENALTY = 3
CONSENSUS_MAX_USES = 3
MAX_EVENT_LOG_ENTRIES = 120
JSON_LIST_CACHE: Dict[str, Dict[str, Any]] = {}
PROCESSED_QUESTION_CACHE: Dict[str, Dict[str, Any]] = {}
AI_GROUP_EVALUATION_REPORT_CACHE: Dict[str, List[Tuple[str, int, int]]] = {}
# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "double diamond").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()
AI_OWNER_PASSWORD = (os.getenv("AI_OWNER_PASSWORD") or "").strip()

# OpenAI client (Aico)
# Works with the "openai" python package (new style client).
try:
    from openai import OpenAI, APIConnectionError, APIStatusError, BadRequestError
    _client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
    QUESTION_GENERATION_MODEL = os.getenv("OPENAI_QUESTION_MODEL", "gpt-4.1-mini")
    IMAGE_GENERATION_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5").strip() or "gpt-image-1.5"
    IMAGE_ANALYSIS_MODEL = os.getenv("OPENAI_IMAGE_ANALYSIS_MODEL", QUESTION_GENERATION_MODEL).strip() or QUESTION_GENERATION_MODEL
    EVALUATION_REPORT_MODEL = os.getenv("OPENAI_EVALUATION_REPORT_MODEL", QUESTION_GENERATION_MODEL).strip() or QUESTION_GENERATION_MODEL
    IMAGE_GENERATION_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip() or "medium"
    IMAGE_GENERATION_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024").strip() or "1024x1024"
    THEME_GENERATION_GUIDANCE = {
        "werking": """
Focus op hoe AI werkt: data, patronen, voorspellen, trainen, prompten, voorbeelden en beperkingen.
Maak liever een denkvraag of korte praktijksituatie dan een losse definitiesvraag.
""".strip(),
        "leefwereld": """
Focus op situaties uit school, sociale media, zoeken, navigatie, aanbevelingen of chatbots.
Laat leerlingen nadenken waar AI wel of niet nuttig is in het dagelijks leven.
""".strip(),
        "kritisch": """
Focus op betrouwbaarheid van AI-output, hallucinaties, bias, privacy, eerlijk schoolgebruik, transparantie en blind vertrouwen in AI.
Laat leerlingen nadenken over kritisch, veilig en verantwoordelijk omgaan met AI.
Maak afleiders geloofwaardig, niet flauw of absurd.
""".strip(),
        "kansen": """
Focus op voordelen van AI in school, creativiteit, zoeken, plannen, ondersteuning, toegankelijkheid en dagelijkse toepassingen.
Laat leerlingen nadenken waar AI echt kan helpen of tijd kan besparen, zonder de vraag promotioneel te maken.
Laat de vraag gaan over goede keuzes, niet alleen over losse regeltjes.
""".strip(),
        "beeld": """
Focus op AI-foto's herkennen, deepfakes, gemanipuleerde beelden, broncontrole, context en zichtbare details die twijfel kunnen oproepen.
Laat leerlingen traag kijken en redeneren waarom een beeld betrouwbaar lijkt of net niet.
Gebruik liefst een herkenbare situatie of beeldbeschrijving, niet alleen een losse definitie.
""".strip(),
    }
    SYSTEM_PROMPT = """
Je maakt inhoudelijke meerkeuzevragen voor een educatief bordspel over artificiele intelligentie.

Doelgroep:
leerlingen van 12 tot 14 jaar.

Schrijfstijl:
- eenvoudig Nederlands, maar niet kinderachtig
- inhoudelijk correct en serieus
- helder en concreet
- geen flauwe mopantwoorden of absurde afleiders

Kwaliteitseisen:
- 1 duidelijke, beste correcte optie
- 3 geloofwaardige maar foutieve opties
- de opties lijken op elkaar in stijl en lengte
- laat minstens 2 foute opties inhoudelijk dicht aanleunen bij het juiste antwoord
- laat foute opties klinken als misvattingen, halve waarheden of bijna-goede keuzes
- laat het juiste antwoord niet opvallen door veel meer detail of precisie
- laat leerlingen nadenken in plaats van alleen een woordje herkennen
- gebruik liefst een korte situatie, vergelijking of redenering
- vermijd té simpele vragen zoals losse woordbetekenissen zonder context
- vermijd te simpele vragen zoals losse woordbetekenissen zonder context
- vermijd onzinnige opties zoals "omdat AI slaapt" of "omdat een robot liegt"

Vaste kwaliteitslat voor AI-geletterdheid:
- gebruik eenvoudige leerlingentaal voor de eerste graad secundair onderwijs
- maak de vraag kort, concreet en herkenbaar voor leerlingen
- laat elke vraag aansluiten bij een situatie uit school, apps, zoeken, sociale media, beelden of chatbots
- raak waar mogelijk een concreet thema: AI herkennen, wat AI doet, kritisch kijken, betrouwbaarheid, privacy, eerlijkheid, AI op school, zelfstandig denken of verantwoord gebruik
- toon dat AI niet altijd juist is en kritisch gecontroleerd moet worden
- toon dat AI fouten of vooroordelen kan bevatten
- wees voorzichtig met privacy en persoonlijke gegevens
- AI mag helpen, maar mag zelfstandig denken niet vervangen
- vermijd moeilijke woorden, dubbele vragen en herhaling

Vorm:
- korte duidelijke vraag
- 4 antwoordopties
- slechts 1 correct antwoord
- opties ongeveer even lang
- vraag en opties zijn geschikt om klassikaal te bespreken
- gebruik geen markdown

Controleer jezelf voor je antwoord geeft:
- Is de vraag inhoudelijk genoeg?
- Zijn alle 4 opties plausibel voor een leerling?
- Is exact 1 optie duidelijk het beste antwoord?

Geef altijd JSON in dit formaat:

{
"question": "...",
"options": ["...","...","...","..."],
 "correct_index": 0,
 "explanation": "..."
}
"""
except Exception:
    OpenAI = None
    _client = None
    IMAGE_ANALYSIS_MODEL = "gpt-4.1-mini"
    EVALUATION_REPORT_MODEL = "gpt-4.1-mini"
    APIConnectionError = Exception
    APIStatusError = Exception
    BadRequestError = Exception

PROMPT_IMPROVEMENT_CHANCE = 0.35
PROMPT_IMPROVEMENT_MISSIONS = [
    {
        "situation": "Je moet voor Nederlands een spreekbeurt voorbereiden over plastic soep.",
        "weak_prompt": "Maak mijn spreekbeurt.",
        "goal": "Vraag hulp om ideeen, structuur en controlepunten te krijgen, zonder dat AI de hele taak overneemt.",
    },
    {
        "situation": "Je wil voor techniek een stappenplan maken om veilig met een lijmpistool te werken.",
        "weak_prompt": "Zeg alles over lijmpistolen.",
        "goal": "Vraag een kort, bruikbaar stappenplan met veiligheidsregels en een checklist.",
    },
    {
        "situation": "Je begrijpt een stukje leerstof over fotosynthese nog niet goed.",
        "weak_prompt": "Leg fotosynthese uit.",
        "goal": "Vraag uitleg op jouw niveau, met een voorbeeld en een korte controlevraag.",
    },
    {
        "situation": "Je groepje wil ideeen zoeken voor een creatief project rond hergebruik van materialen.",
        "weak_prompt": "Geef ideeen.",
        "goal": "Vraag meerdere haalbare ideeen, met materiaal, tijd en wat je ervan kan leren.",
    },
    {
        "situation": "Je wil een planning maken voor een toetsweek zonder alles uit te stellen.",
        "weak_prompt": "Maak een planning.",
        "goal": "Vraag een realistische planning op basis van vakken, tijd en pauzes, met ruimte om zelf keuzes te maken.",
    },
]


def env_int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)) or default)
    except (TypeError, ValueError):
        return default


AI_BYOK_DEFAULT_TTL_MINUTES = env_int("AI_BYOK_DEFAULT_TTL_MINUTES", 120)
AI_BYOK_MAX_TTL_MINUTES = env_int("AI_BYOK_MAX_TTL_MINUTES", 480)
AI_RUNTIME_CONFIG: Dict[str, Any] = {
    "mode": "default",
    "byok_client": None,
    "byok_expires_at": 0.0,
    "byok_last4": "",
}


def cleanup_expired_byok_key(now: Optional[float] = None) -> None:
    current = time.time() if now is None else now
    if AI_RUNTIME_CONFIG.get("mode") == "byok" and current >= float(AI_RUNTIME_CONFIG.get("byok_expires_at") or 0):
        AI_RUNTIME_CONFIG.update({
            "mode": "default",
            "byok_client": None,
            "byok_expires_at": 0.0,
            "byok_last4": "",
        })


def has_valid_ai_owner_password(x_ai_owner_password: Optional[str]) -> bool:
    return bool(AI_OWNER_PASSWORD) and (x_ai_owner_password or "").strip() == AI_OWNER_PASSWORD


def get_openai_client(allow_server_key: bool = False):
    cleanup_expired_byok_key()
    if AI_RUNTIME_CONFIG.get("mode") == "disabled":
        return None
    if AI_RUNTIME_CONFIG.get("mode") == "byok":
        return AI_RUNTIME_CONFIG.get("byok_client")
    if allow_server_key:
        return _client
    return None


def openai_unavailable_message() -> str:
    if AI_RUNTIME_CONFIG.get("mode") == "disabled":
        return "AI staat momenteel uit in de leerkrachtenmodule."
    return "OpenAI client niet beschikbaar. Gebruik BYOK of ontgrendel de serverkey met het eigenaarspaswoord."


def build_ai_runtime_status(owner_verified: bool = False) -> dict:
    cleanup_expired_byok_key()
    mode = str(AI_RUNTIME_CONFIG.get("mode") or "default")
    client = get_openai_client(allow_server_key=owner_verified)
    expires_at = float(AI_RUNTIME_CONFIG.get("byok_expires_at") or 0)
    expires_in = max(0, int(expires_at - time.time())) if mode == "byok" and expires_at else 0
    return {
        "mode": mode,
        "available": client is not None,
        "server_key_available": _client is not None,
        "server_key_owner_required": _client is not None,
        "server_key_owner_configured": bool(AI_OWNER_PASSWORD),
        "server_key_owner_verified": owner_verified,
        "server_key_locked": mode == "default" and _client is not None and not owner_verified,
        "byok_active": mode == "byok" and client is not None,
        "byok_last4": AI_RUNTIME_CONFIG.get("byok_last4") or "",
        "expires_at": expires_at if mode == "byok" else None,
        "expires_in_seconds": expires_in,
    }


# ----------------------------
# Helpers: Coordinates A-R / 1-17
# ----------------------------

COLS = list(string.ascii_uppercase[:18])  # A..R (18 cols)
ROWS = list(range(1, 18))                 # 1..17

Coord = str  # e.g., "H14"

def all_coords() -> List[Coord]:
    return [f"{c}{r}" for c in COLS for r in ROWS]

def parse_coord(coord: str) -> Tuple[str, int]:

    coord = coord.strip().upper()
    if len(coord) < 2:
        raise ValueError("Invalid coord length")
    col = coord[0]
    try:
        row = int(coord[1:])
    except ValueError:
        raise ValueError("Invalid row")
    if col not in COLS or row not in ROWS:
        raise ValueError("Coord out of board range")
    return col, row
# ----------------------------
# Helpers: Question system
# ----------------------------

def normalize_theme_key(theme: object) -> str:
    raw_theme = str(theme or "").strip()
    mapped_theme = THEME_ALIASES.get(raw_theme, raw_theme)
    return mapped_theme


def image_binary_answer_label(index: object) -> str:
    if isinstance(index, int) and 0 <= index < len(IMAGE_BINARY_OPTIONS):
        return IMAGE_BINARY_OPTIONS[index]
    return "Onbekend"


def image_source_host(image_url: object) -> str:
    parsed = urlparse(str(image_url or "").strip())
    return str(parsed.netloc or "").split(":", 1)[0].strip().casefold()


def image_source_path(image_url: object) -> str:
    parsed = urlparse(str(image_url or "").strip())
    return unquote(str(parsed.path or ""))


def trusted_real_source_label_for_url(image_url: object) -> str:
    host = image_source_host(image_url)
    if host in WIKIMEDIA_COMMONS_HOSTS:
        return "Wikimedia Commons"
    return ""


def is_trusted_real_image_url(image_url: object) -> bool:
    normalized_url = str(image_url or "").strip()
    if not normalized_url:
        return False

    host = image_source_host(normalized_url)
    path = image_source_path(normalized_url)

    if host == "commons.wikimedia.org":
        return path.startswith("/wiki/Special:Redirect/file/")

    if host == "upload.wikimedia.org":
        return path.startswith("/wikipedia/commons/")

    return False


def is_image_binary_question(question: dict) -> bool:
    return str(question.get("type") or "multiple_choice") == "image_binary"


def is_round_eligible_image_question(question: dict) -> bool:
    if not is_image_binary_question(question):
        return False
    if not question.get("approved", True) or question.get("rejected", False):
        return False

    correct_index = question.get("correct_index")
    image_url = str(question.get("image_url") or "").strip()
    if correct_index not in (0, 1) or not image_url:
        return False

    if correct_index == 1:
        return is_trusted_real_image_url(image_url)

    return True


def build_trusted_real_image_questions() -> List[dict]:
    used_ids = set(load_used_trusted_real_image_ids())
    questions: List[dict] = []

    for item in TRUSTED_REAL_IMAGE_LIBRARY:
        questions.append(
            {
                "id": item["id"],
                "source": item["source"],
                "source_label": item["source_label"],
                "source_url": item["source_url"],
                "type": "image_binary",
                "theme": "beeld",
                "display_theme": THEMES["beeld"]["label"],
                "question": item["question"],
                "options": list(IMAGE_BINARY_OPTIONS),
                "correct_index": 1,
                "image_url": item["image_url"],
                "image_alt": item["image_alt"],
                "explanation": item["explanation"],
                "approved": True,
                "rejected": False,
                "used": item["id"] in used_ids,
            }
        )

    return questions


def image_scene_family_key(question: dict) -> str:
    source_url = str(question.get("source_url") or "").strip()
    if source_url:
        return normalize_text_for_similarity(source_url)

    image_alt = str(question.get("image_alt") or "").strip()
    normalized_alt = normalize_text_for_similarity(image_alt)
    if normalized_alt and normalized_alt not in {"beeld bij de vraag", "ai gegenereerde foto"}:
        return normalized_alt

    image_url = str(question.get("image_url") or "").strip()
    filename = Path(urlparse(image_url).path).name
    stem = re.sub(r"-\d{10}-\d{4}\.(png|jpg|jpeg|webp)$", "", filename, flags=re.IGNORECASE)
    stem = re.sub(r"\.(png|jpg|jpeg|webp)$", "", stem, flags=re.IGNORECASE)
    if stem and stem.lower() != "image":
        return normalize_text_for_similarity(stem)

    question_id = str(question.get("id") or "").strip()
    return normalize_text_for_similarity(question_id or image_url)


def count_unique_image_scene_keys(questions: List[dict]) -> int:
    keys = {
        image_scene_family_key(question)
        for question in questions
        if image_scene_family_key(question)
    }
    return len(keys)


def choose_image_round_question(questions: List[dict]) -> Optional[dict]:
    if not questions:
        return None

    recent_scene_keys = set(load_recent_image_scene_keys())
    fresh_questions = [
        question for question in questions
        if image_scene_family_key(question) not in recent_scene_keys
    ]
    candidate_pool = fresh_questions or questions

    ai_candidates = [question for question in candidate_pool if question.get("correct_index") == 0]
    real_candidates = [question for question in candidate_pool if question.get("correct_index") == 1]

    if ai_candidates and real_candidates:
        if random.random() < 0.8:
            return random.choice(ai_candidates)
        return random.choice(real_candidates)

    if ai_candidates:
        return random.choice(ai_candidates)
    if real_candidates:
        return random.choice(real_candidates)

    return random.choice(candidate_pool)


def choose_auto_image_scene_seeds_for_generation(
    count: int,
    existing_questions: List[dict],
) -> List[dict]:
    if count <= 0:
        return []

    existing_keys = {
        image_scene_family_key(question)
        for question in existing_questions
        if question.get("correct_index") == 0
    }
    unused_scenes = [
        scene for scene in AUTO_IMAGE_SCENE_LIBRARY
        if normalize_text_for_similarity(scene.get("alt") or scene.get("label") or "") not in existing_keys
    ]

    if len(unused_scenes) >= count:
        random.shuffle(unused_scenes)
        return [dict(scene) for scene in unused_scenes[:count]]

    selected = [dict(scene) for scene in unused_scenes]
    remaining = count - len(selected)
    if remaining <= 0:
        return selected

    fallback_scenes = choose_auto_image_scene_seeds(remaining)
    selected.extend(fallback_scenes)
    return selected


def dedupe_image_questions_by_url(questions: List[dict]) -> List[dict]:
    unique_questions: List[dict] = []
    seen_urls: set[str] = set()

    for question in questions:
        image_url = str(question.get("image_url") or "").strip()
        if not image_url or image_url in seen_urls:
            continue

        seen_urls.add(image_url)
        unique_questions.append(question)

    return unique_questions


def load_round_image_questions(include_used: bool = True) -> List[dict]:
    questions = build_trusted_real_image_questions()
    questions.extend(
        question
        for question in load_image_questions()
        if is_round_eligible_image_question(question)
    )
    questions = dedupe_image_questions_by_url(questions)
    if include_used:
        return questions
    return [question for question in questions if not question.get("used", False)]


def scene_specific_ai_explanation(question: dict) -> str:
    family_key = image_scene_family_key(question)
    return AI_SCENE_EXPLANATION_HINTS.get(family_key, "")


def should_upgrade_ai_image_explanation(question: dict) -> bool:
    if question.get("correct_index") != 0:
        return False

    explanation = normalize_text_for_similarity(question.get("explanation", ""))
    if not explanation:
        return True

    if any(marker in explanation for marker in GENERIC_AI_EXPLANATION_MARKERS):
        return True

    return False


def processed_question_cache_key(path: Path) -> str:
    return f"processed::{cache_key_for_path(path)}"


def load_processed_question_cache(path: Path) -> Optional[List[dict]]:
    cache_entry = PROCESSED_QUESTION_CACHE.get(processed_question_cache_key(path))
    if not cache_entry:
        return None

    if cache_entry.get("mtime_ns") != file_mtime_ns(path):
        return None

    questions = cache_entry.get("questions")
    return questions if isinstance(questions, list) else None


def store_processed_question_cache(path: Path, questions: List[dict]) -> None:
    PROCESSED_QUESTION_CACHE[processed_question_cache_key(path)] = {
        "mtime_ns": file_mtime_ns(path),
        "questions": questions,
    }


def migrate_core_question_themes_in_memory(questions: List[dict]) -> bool:
    changed = False

    for question in questions:
        normalized_theme = normalize_theme_key(question.get("theme"))
        question_id = str(question.get("id") or "").strip()

        if question_id in KANSEN_THEME_SOURCE_IDS:
            normalized_theme = "kansen"
        elif normalized_theme == "beeld":
            normalized_theme = "kritisch"

        if normalized_theme and question.get("theme") != normalized_theme:
            question["theme"] = normalized_theme
            changed = True

    return changed


def normalize_question_difficulty_key(value: object, fallback: str = "basis") -> str:
    normalized = normalize_text_for_similarity(value).replace(" ", "").strip("-")
    if normalized in QUESTION_DIFFICULTY_ALIASES:
        return QUESTION_DIFFICULTY_ALIASES[normalized]
    return fallback


def infer_question_difficulty(question: dict) -> str:
    if str(question.get("type") or "multiple_choice") != "multiple_choice":
        return "basis"

    question_text = normalize_text_for_similarity(question.get("question", ""))
    options = [
        normalize_text_for_similarity(option)
        for option in list(question.get("options") or [])
        if normalize_text_for_similarity(option)
    ]

    score = 0
    if len(question_text.split()) >= 12:
        score += 1
    if any(marker in question_text for marker in QUESTION_SCENARIO_MARKERS):
        score += 1
    if any(marker in question_text for marker in QUESTION_ADVANCED_MARKERS):
        score += 1
    if any(marker in question_text for marker in QUESTION_CHALLENGE_MARKERS):
        score += 1

    average_option_length = (
        sum(len(option.split()) for option in options) / len(options)
        if options
        else 0.0
    )
    if average_option_length >= 5:
        score += 1

    if str(question.get("source") or "").strip().lower() == "ai":
        score += 1
    if str(question.get("theme") or "").strip() == "kritisch":
        score += 1

    if score >= 5:
        return "uitdaging"
    if score >= 3:
        return "verdieping"
    return "basis"


def question_difficulty_key_for_question(question: dict) -> str:
    return normalize_question_difficulty_key(
        question.get("difficulty"),
        infer_question_difficulty(question),
    )


def question_difficulty_label(question: dict) -> str:
    difficulty_key = question_difficulty_key_for_question(question)
    return QUESTION_DIFFICULTIES.get(difficulty_key, QUESTION_DIFFICULTIES["basis"])["label"]


def question_difficulty_short_label(question: dict) -> str:
    difficulty_key = question_difficulty_key_for_question(question)
    return QUESTION_DIFFICULTIES.get(difficulty_key, QUESTION_DIFFICULTIES["basis"])["short_label"]


def question_difficulty_instruction(question: dict) -> str:
    difficulty_key = question_difficulty_key_for_question(question)
    base_instruction = (
        "Kies het beste antwoord. Bij een juist antwoord mag je 3 tegels leggen, "
        "bij een fout krijg je een plaatsingscoordinaat."
    )
    if difficulty_key == "basis":
        return base_instruction
    if difficulty_key == "verdieping":
        return base_instruction + " Lees goed: meerdere opties lijken bewust geloofwaardig."
    return base_instruction + " Vergelijk de nuances zorgvuldig: meerdere opties kunnen bijna juist lijken."


def normalize_question_difficulty_mode(value: object, fallback: str = "mix") -> str:
    normalized = normalize_text_for_similarity(value).replace(" ", "").strip("-")
    if normalized in QUESTION_DIFFICULTY_MODE_ALIASES:
        return QUESTION_DIFFICULTY_MODE_ALIASES[normalized]
    return fallback


def question_difficulty_mode_label(mode: object) -> str:
    normalized_mode = normalize_question_difficulty_mode(mode)
    return QUESTION_DIFFICULTY_MODES.get(normalized_mode, QUESTION_DIFFICULTY_MODES["mix"])["label"]


def question_difficulty_mode_description(mode: object) -> str:
    normalized_mode = normalize_question_difficulty_mode(mode)
    return QUESTION_DIFFICULTY_MODES.get(normalized_mode, QUESTION_DIFFICULTY_MODES["mix"])["description"]


def migrate_core_question_difficulties_in_memory(questions: List[dict]) -> bool:
    changed = False

    for question in questions:
        if str(question.get("type") or "multiple_choice") != "multiple_choice":
            continue

        inferred_difficulty = question_difficulty_key_for_question(question)
        if question.get("difficulty") != inferred_difficulty:
            question["difficulty"] = inferred_difficulty
            changed = True

    return changed


def migrate_image_question_metadata_in_memory(questions: List[dict]) -> bool:
    changed = False
    image_theme_label = THEMES["beeld"]["label"]

    for question in questions:
        question_type = str(question.get("type") or "image_binary")
        if question_type != "image_binary":
            continue

        if question.get("theme") != "beeld":
            question["theme"] = "beeld"
            changed = True

        if question.get("display_theme") != image_theme_label:
            question["display_theme"] = image_theme_label
            changed = True

        if list(question.get("options") or []) != list(IMAGE_BINARY_OPTIONS):
            question["options"] = list(IMAGE_BINARY_OPTIONS)
            changed = True

        if question.get("correct_index") == 0 and should_upgrade_ai_image_explanation(question):
            upgraded_explanation = scene_specific_ai_explanation(question)
            if upgraded_explanation and str(question.get("explanation") or "").strip() != upgraded_explanation:
                question["explanation"] = upgraded_explanation
                changed = True

    return changed

def load_core_questions():
    cached_questions = load_processed_question_cache(CORE_FILE)
    if cached_questions is not None:
        return cached_questions

    questions = load_questions_from_file(CORE_FILE)
    changed = migrate_core_question_themes_in_memory(questions)
    if migrate_core_question_difficulties_in_memory(questions):
        changed = True
    cleaned_questions, removed_ids = dedupe_core_question_bank(questions)
    changed = changed or bool(removed_ids)
    if rebalance_core_question_answer_positions_in_memory(cleaned_questions):
        changed = True
    if changed:
        save_core_questions(cleaned_questions)
        return cleaned_questions
    store_processed_question_cache(CORE_FILE, cleaned_questions)
    return cleaned_questions


def load_image_questions():
    cached_questions = load_processed_question_cache(IMAGE_FILE)
    if cached_questions is not None:
        return cached_questions

    questions = load_questions_from_file(IMAGE_FILE)
    changed = migrate_image_question_metadata_in_memory(questions)
    cleaned_questions, removed_ids = dedupe_image_question_bank(questions)
    changed = changed or bool(removed_ids)
    if changed:
        save_image_questions(cleaned_questions)
        return cleaned_questions
    store_processed_question_cache(IMAGE_FILE, cleaned_questions)
    return cleaned_questions


def load_consensus_dilemmas():
    return load_questions_from_file(CONSENSUS_FILE)


def load_questions_from_file(path: Path):
    return load_json_list_from_file(path)


def cache_key_for_path(path: Path) -> str:
    try:
        return str(path.resolve())
    except OSError:
        return str(path)


def file_mtime_ns(path: Path) -> Optional[int]:
    try:
        return path.stat().st_mtime_ns
    except OSError:
        return None


def load_json_list_from_file(path: Path) -> List[Any]:
    cache_key = cache_key_for_path(path)
    mtime_ns = file_mtime_ns(path)
    cached = JSON_LIST_CACHE.get(cache_key)

    if cached and cached.get("mtime_ns") == mtime_ns:
        payload = cached.get("payload")
        return payload if isinstance(payload, list) else []

    if not path.exists():
        payload: List[Any] = []
    else:
        try:
            with open(path, "r", encoding="utf-8") as f:
                payload = json.load(f)
        except (OSError, json.JSONDecodeError):
            payload = []

    if not isinstance(payload, list):
        payload = []

    JSON_LIST_CACHE[cache_key] = {
        "mtime_ns": mtime_ns,
        "payload": payload,
    }
    return payload


def save_json_list_to_file(path: Path, payload: List[Any]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(payload, f, indent=2, ensure_ascii=False)

    JSON_LIST_CACHE[cache_key_for_path(path)] = {
        "mtime_ns": file_mtime_ns(path),
        "payload": payload,
    }


def load_string_list_from_file(path: Path) -> List[str]:
    payload = load_json_list_from_file(path)

    values: List[str] = []
    for item in payload:
        normalized = str(item or "").strip()
        if normalized and normalized not in values:
            values.append(normalized)
    return values


def load_all_time_ranking() -> List[AllTimeRankingEntry]:
    if not ALL_TIME_RANKING_FILE.exists():
        return []

    try:
        with open(ALL_TIME_RANKING_FILE, "r", encoding="utf-8") as f:
            payload = json.load(f)
    except (OSError, json.JSONDecodeError):
        return []

    if not isinstance(payload, list):
        return []

    entries: List[AllTimeRankingEntry] = []
    seen_ids: set[str] = set()

    for item in payload:
        if not isinstance(item, dict):
            continue

        entry_id = str(item.get("id") or "").strip()
        game_id = str(item.get("game_id") or "").strip()
        if not entry_id or not game_id or entry_id in seen_ids:
            continue

        raw_names = item.get("player_names")
        if not isinstance(raw_names, list):
            raw_names = []

        player_names: List[str] = []
        for raw_name in raw_names:
            normalized_name = str(raw_name or "").strip()
            if normalized_name:
                player_names.append(normalized_name)

        try:
            created_at = float(item.get("created_at") or 0.0)
        except (TypeError, ValueError):
            created_at = 0.0

        try:
            diamond_total = max(0, int(item.get("diamond_total") or 0))
        except (TypeError, ValueError):
            diamond_total = 0

        escaped_player_count = len(player_names)
        if escaped_player_count <= 0:
            continue

        entries.append(AllTimeRankingEntry(
            id=entry_id,
            game_id=game_id,
            created_at=created_at,
            player_names=player_names,
            escaped_player_count=escaped_player_count,
            diamond_total=diamond_total,
        ))
        seen_ids.add(entry_id)

    return sort_all_time_ranking(entries)


def sort_all_time_ranking(entries: List[AllTimeRankingEntry]) -> List[AllTimeRankingEntry]:
    return sorted(
        entries,
        key=lambda entry: (
            -entry.diamond_total,
            -entry.escaped_player_count,
            -entry.created_at,
            entry.id,
        ),
    )


def save_all_time_ranking(entries: List[AllTimeRankingEntry]) -> None:
    serializable_entries = [entry.model_dump() for entry in sort_all_time_ranking(entries)]
    with open(ALL_TIME_RANKING_FILE, "w", encoding="utf-8") as f:
        json.dump(serializable_entries, f, indent=2, ensure_ascii=False)


def load_used_trusted_real_image_ids() -> List[str]:
    return load_string_list_from_file(USED_TRUSTED_REAL_IMAGE_FILE)


def save_used_trusted_real_image_ids(image_ids: List[str]) -> None:
    save_json_list_to_file(USED_TRUSTED_REAL_IMAGE_FILE, list(dict.fromkeys(image_ids)))


def load_recent_image_scene_keys() -> List[str]:
    return load_string_list_from_file(RECENT_IMAGE_SCENE_FILE)


def save_recent_image_scene_keys(scene_keys: List[str]) -> None:
    trimmed = list(dict.fromkeys(scene_keys))[-IMAGE_ROUND_RECENT_SCENE_LIMIT:]
    save_json_list_to_file(RECENT_IMAGE_SCENE_FILE, trimmed)


def reset_questions():
    for load_questions, save_questions in (
        (load_core_questions, save_core_questions),
        (load_image_questions, save_image_questions),
        (load_consensus_dilemmas, save_consensus_dilemmas),
    ):
        questions = load_questions()
        if not questions:
            continue

        for question in questions:
            question["used"] = False

        save_questions(questions)

    save_used_trusted_real_image_ids([])
    save_recent_image_scene_keys([])


def save_core_questions(questions):
    save_questions_to_file(CORE_FILE, questions)
    store_processed_question_cache(CORE_FILE, questions)


def save_image_questions(questions):
    save_questions_to_file(IMAGE_FILE, questions)
    store_processed_question_cache(IMAGE_FILE, questions)


def save_consensus_dilemmas(questions):
    save_questions_to_file(CONSENSUS_FILE, questions)


def save_questions_to_file(path: Path, questions):
    save_json_list_to_file(path, questions)


def save_string_list_to_file(path: Path, values: List[str]) -> None:
    save_json_list_to_file(path, values)


def load_disabled_consensus_ids() -> List[str]:
    return load_string_list_from_file(DISABLED_CONSENSUS_FILE)


def save_disabled_consensus_ids(question_ids: List[str]) -> None:
    save_string_list_to_file(DISABLED_CONSENSUS_FILE, question_ids)


def save_teacher_uploaded_image(data_url: str, filename: str = "") -> str:
    normalized = str(data_url or "").strip()
    match = re.fullmatch(
        r"data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=\s]+)",
        normalized,
    )
    if not match:
        raise HTTPException(400, "De geplakte afbeelding kon niet gelezen worden.")

    mime_type = match.group(1).lower()
    extension = ALLOWED_TEACHER_IMAGE_MIME_TYPES.get(mime_type)
    if not extension:
        raise HTTPException(400, "Gebruik een PNG, JPG, WEBP of GIF als geplakte afbeelding.")

    encoded_payload = re.sub(r"\s+", "", match.group(2))

    try:
        image_bytes = base64.b64decode(encoded_payload, validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(400, "De geplakte afbeelding bevat ongeldige beelddata.")

    if not image_bytes:
        raise HTTPException(400, "De geplakte afbeelding is leeg.")

    if len(image_bytes) > MAX_TEACHER_IMAGE_BYTES:
        raise HTTPException(400, "De geplakte afbeelding is te groot. Gebruik maximaal 8 MB.")

    safe_stem = re.sub(r"[^a-zA-Z0-9_-]+", "-", Path(filename or "").stem).strip("-").lower()
    if not safe_stem:
        safe_stem = "clipboard"

    unique_name = f"{safe_stem}-{int(time.time())}-{random.randint(1000, 9999)}{extension}"
    UPLOADED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = UPLOADED_IMAGE_DIR / unique_name
    output_path.write_bytes(image_bytes)

    return f"/static/question-images/uploads/{unique_name}"


def safe_generated_image_stem(label: str, fallback: str = "generated-image") -> str:
    normalized = normalize_text_for_similarity(label).replace(" ", "-").strip("-")
    return normalized or fallback


def save_generated_image_bytes(image_bytes: bytes, label: str, output_format: str = "png") -> str:
    if not image_bytes:
        raise HTTPException(500, "De gegenereerde afbeelding bevat geen beelddata.")

    extension = OPENAI_IMAGE_OUTPUT_EXTENSIONS.get(str(output_format or "").strip().lower(), ".png")
    safe_stem = safe_generated_image_stem(label, "generated-image")
    unique_name = f"{safe_stem}-{int(time.time())}-{random.randint(1000, 9999)}{extension}"
    GENERATED_IMAGE_DIR.mkdir(parents=True, exist_ok=True)
    output_path = GENERATED_IMAGE_DIR / unique_name
    output_path.write_bytes(image_bytes)
    return f"/static/question-images/generated/{unique_name}"


def generated_image_data_url(image_bytes: bytes, output_format: str = "png") -> str:
    mime_type = OPENAI_IMAGE_OUTPUT_MIME_TYPES.get(str(output_format or "").strip().lower(), "image/png")
    encoded = base64.b64encode(image_bytes).decode("ascii")
    return f"data:{mime_type};base64,{encoded}"


def explain_generated_ai_image(
    image_bytes: bytes,
    output_format: str = "png",
    image_alt: str = "",
    allow_server_key: bool = False,
) -> str:
    fallback = (
        "Er zit in dit beeld een klein detail dat niet logisch doorloopt, zoals een vervormde rand, een rare reflectie of tekst die half verandert. "
        "Tip: kies één verdacht stukje en volg dat detail heel precies, bijvoorbeeld langs een raamrand, vinger, letter of schaduw."
    )

    client = get_openai_client(allow_server_key=allow_server_key)
    if client is None or not image_bytes:
        return fallback

    try:
        response = client.chat.completions.create(
            model=IMAGE_ANALYSIS_MODEL,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je helpt een leerkracht bij een beeldvraag over AI-beelden voor leerlingen van 12 tot 14 jaar. "
                        "De afbeelding is al zeker AI-gegenereerd. "
                        "Geef exact 2 korte Nederlandse zinnen in eenvoudig Nederlands. "
                        "De eerste zin noemt 1 heel concreet zichtbaar detail dat niet klopt en zegt waar in het beeld dat zit. "
                        "De tweede zin begint met 'Tip:' en zegt waar ze best op letten. "
                        "Schrijf niet algemeen over 'details' of 'schaduwen' zonder concreet voorwerp te noemen. "
                        "Noem alleen dingen die echt zichtbaar lijken. "
                        "Als het beeld moeilijk te ontmaskeren is, zeg dat eerlijk en noem waar je extra op zou letten. "
                        "Geef alleen JSON terug in de vorm {\"explanation\":\"...\"}."
                    ),
                },
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": (
                                "Beschrijf de belangrijkste zichtbare aanwijzingen voor leerlingen. "
                                f"Alt-tekst: {str(image_alt or '').strip() or 'Geen alt-tekst beschikbaar.'}"
                            ),
                        },
                        {
                            "type": "image_url",
                            "image_url": {"url": generated_image_data_url(image_bytes, output_format)},
                        },
                    ],
                },
            ],
        )
    except Exception as exc:
        print("AI image explanation error:", exc)
        return fallback

    content = str((response.choices[0].message.content or "")).strip()
    if not content:
        return fallback

    try:
        payload = json.loads(content)
    except json.JSONDecodeError:
        return fallback

    explanation = str(payload.get("explanation") or "").strip()
    return explanation or fallback


def choose_auto_image_scene_seeds(count: int) -> List[dict]:
    if count <= 0:
        return []

    seeds = list(AUTO_IMAGE_SCENE_LIBRARY)
    random.shuffle(seeds)

    selected: List[dict] = []
    while len(selected) < count:
        if not seeds:
            seeds = list(AUTO_IMAGE_SCENE_LIBRARY)
            random.shuffle(seeds)
        selected.append(dict(seeds.pop()))

    return selected


def build_auto_image_prompt(scene: dict, focus: str = "") -> str:
    focus_text = str(focus or "").strip()
    focus_clause = ""
    if focus_text:
        focus_clause = f"Work this topic into the scene in a natural way if it fits: {focus_text}. "

    return (
        "Create a photorealistic, candid smartphone photo that looks like an ordinary real-life snapshot. "
        f"Scene: {scene.get('prompt', '')} "
        f"{focus_clause}"
        "The image must stay mostly believable, but include exactly one subtle visible clue that gives away AI generation or editing. "
        "Examples include a slightly warped finger, an impossible reflection, a mildly distorted label, a repeated object detail, an inconsistent shadow or a seam that almost lines up but not quite. "
        "Keep that clue modest, age-appropriate and only noticeable after careful looking. "
        "Keep the composition natural and slightly imperfect. "
        "Do not add text overlays, watermarks, collages, split screens or user interface elements. "
        "If people appear, keep anatomy and proportions realistic apart from that one subtle clue."
    )


def generate_ai_mix_image(scene: dict, focus: str = "", allow_server_key: bool = False) -> dict:
    client = get_openai_client(allow_server_key=allow_server_key)
    if client is None:
        raise HTTPException(500, openai_unavailable_message())

    prompt = build_auto_image_prompt(scene, focus)

    try:
        response = client.images.generate(
            model=IMAGE_GENERATION_MODEL,
            prompt=prompt,
            size=IMAGE_GENERATION_SIZE,
            quality=IMAGE_GENERATION_QUALITY,
            output_format="png",
            n=1,
        )
    except APIConnectionError as exc:
        print("AI image generation error:", exc)
        raise HTTPException(503, "De verbinding met OpenAI voor beeldgeneratie lukt momenteel niet.")
    except BadRequestError as exc:
        print("AI image generation bad request:", exc)
        raise HTTPException(
            500,
            "De OpenAI-instellingen voor beeldgeneratie zijn ongeldig. Controleer model en parameters.",
        )
    except APIStatusError as exc:
        print("AI image generation status error:", exc)
        raise HTTPException(502, "OpenAI gaf tijdelijk een serverfout bij beeldgeneratie.")
    except Exception as exc:
        print("AI image generation error:", exc)
        raise HTTPException(500, "De automatische AI-afbeelding kon niet gegenereerd worden.")

    image_payload = (response.data or [None])[0]
    image_b64 = ""
    if image_payload is not None:
        image_b64 = str(getattr(image_payload, "b64_json", "") or "").strip()

    if not image_b64:
        raise HTTPException(500, "OpenAI gaf geen beelddata terug voor de automatische beeldmix.")

    try:
        image_bytes = base64.b64decode(re.sub(r"\s+", "", image_b64), validate=True)
    except (ValueError, binascii.Error):
        raise HTTPException(500, "De automatische AI-afbeelding bevat ongeldige beelddata.")

    output_format = str(getattr(response, "output_format", "") or "png").strip().lower() or "png"
    image_url = save_generated_image_bytes(image_bytes, str(scene.get("label") or "generated-image"), output_format)
    return {
        "image_url": image_url,
        "image_alt": str(scene.get("alt") or "AI-gegenereerde foto"),
        "revised_prompt": str(getattr(image_payload, "revised_prompt", "") or "").strip(),
        "explanation": explain_generated_ai_image(
            image_bytes,
            output_format,
            str(scene.get("alt") or "AI-gegenereerde foto"),
            allow_server_key=allow_server_key,
        ),
    }


def seed_ai_image_question_pool_if_needed(allow_server_key: bool = False) -> int:
    if get_openai_client(allow_server_key=allow_server_key) is None:
        return 0

    existing_image_questions = load_image_questions()
    ai_candidates = unique_ai_image_candidates(existing_image_questions)
    ai_count = len(ai_candidates)
    scene_variety = count_unique_image_scene_keys(ai_candidates)

    missing_count = max(0, AI_IMAGE_POOL_TARGET_COUNT - ai_count)
    missing_variety = max(0, AI_IMAGE_POOL_TARGET_VARIETY - scene_variety)
    generation_count = min(
        AI_IMAGE_POOL_GENERATION_BATCH,
        max(missing_count, missing_variety),
    )

    if generation_count <= 0:
        return 0

    scenes = choose_auto_image_scene_seeds_for_generation(generation_count, ai_candidates)
    if not scenes:
        return 0

    working_questions = list(existing_image_questions)
    new_questions: List[dict] = []

    for scene in scenes:
        try:
            generated_image = generate_ai_mix_image(scene, allow_server_key=allow_server_key)
        except HTTPException as exc:
            print("AI pool seed skipped:", exc.detail)
            break

        generated_question = build_auto_image_question(
            working_questions,
            correct_index=0,
            image_url=generated_image["image_url"],
            image_alt=generated_image["image_alt"],
            explanation=str(generated_image.get("explanation") or "").strip() or (
                "Dit beeld is door AI gemaakt of bewerkt. Tip: let op kleine details zoals tekst, reflecties, vingers en schaduwen."
            ),
            source="ai",
        )
        working_questions.append(generated_question)
        new_questions.append(generated_question)

    if new_questions:
        existing_image_questions.extend(new_questions)
        save_image_questions(existing_image_questions)

    return len(new_questions)


def build_auto_image_question(
    existing_questions: List[dict],
    *,
    correct_index: int,
    image_url: str,
    image_alt: str,
    explanation: str,
    source: str = "auto",
) -> dict:
    return {
        "id": next_prefixed_question_id(existing_questions, "image_round_"),
        "source": source,
        "type": "image_binary",
        "theme": "beeld",
        "display_theme": THEMES["beeld"]["label"],
        "question": random.choice(AUTO_IMAGE_QUESTION_VARIANTS),
        "options": list(IMAGE_BINARY_OPTIONS),
        "correct_index": correct_index,
        "image_url": image_url,
        "image_alt": image_alt,
        "explanation": explanation,
        "approved": True,
        "rejected": False,
        "used": False,
    }


def build_auto_image_preview_item(question: dict, source: str = "bestaand") -> dict:
    preview_item = dict(question)
    preview_item["source"] = source
    preview_item["preview_only"] = True
    return preview_item


def unique_image_candidates_by_correct_index(questions: List[dict], correct_index: int) -> List[dict]:
    seen_urls: set[str] = set()
    candidates: List[dict] = []

    for question in questions:
        if not is_round_eligible_image_question(question):
            continue
        if question.get("correct_index") != correct_index:
            continue

        image_url = str(question.get("image_url") or "").strip()
        if not image_url or image_url in seen_urls:
            continue

        seen_urls.add(image_url)
        candidates.append(question)

    return candidates


def unique_real_image_candidates(questions: List[dict]) -> List[dict]:
    return unique_image_candidates_by_correct_index(questions, 1)


def unique_ai_image_candidates(questions: List[dict]) -> List[dict]:
    return unique_image_candidates_by_correct_index(questions, 0)


QUESTION_STOPWORDS = {
    "a", "aan", "ai", "al", "alleen", "als", "bij", "dan", "dat", "de", "denkt",
    "deze", "die", "dit", "doet", "door", "een", "en", "er", "gebruik", "gebruikt",
    "heeft", "het", "hoe", "iemand", "in", "is", "je", "kan", "kies", "kijk",
    "kun", "laat", "lijkt", "maak", "meestal", "met", "niet", "of", "om", "op",
    "soms", "te", "tegen", "uit", "vaak", "van", "vraag", "waarschijnlijk", "wat",
    "welk", "welke", "waar", "waarom", "wordt", "zou", "zonder",
}

QUESTION_EXPLANATION_FALLBACKS = {
    "core_werking_1": "AI kan fouten maken omdat het leert uit voorbeelden of data die onvolledig, scheef of verouderd kunnen zijn. Als de input niet goed is, kan het antwoord ook fout zijn.",
    "core_werking_2": "Een AI-model leert niet uit zichzelf: het heeft veel voorbeelden of data nodig om patronen te herkennen en later iets te kunnen voorspellen.",
    "core_werking_3": "AI zoekt vaak patronen en verbanden in informatie. Zo kan het bijvoorbeeld dingen herkennen, sorteren of voorspellen.",
    "core_werking_4": "Een prompt is de vraag of instructie die je aan AI geeft. Hoe duidelijker je prompt, hoe groter de kans op een bruikbaar antwoord.",
    "core_werking_5": "AI lijkt slim omdat het heel snel patronen herkent in veel gegevens. Dat is iets anders dan echt begrijpen of voelen.",
    "core_leefwereld_1": "AI zit vaak in apps en platforms die aanbevelingen doen, zoals video's, muziek of berichten die bij jouw gedrag passen.",
    "core_leefwereld_2": "AI kan helpen bij huiswerk door uitleg, voorbeelden of structuur te geven. Je moet wel zelf blijven nadenken en controleren.",
    "core_leefwereld_3": "Navigatie-apps gebruiken AI om verkeer en routes te voorspellen. Daardoor kunnen ze sneller een handige route voorstellen.",
    "core_leefwereld_4": "Bij een spreekbeurt is het slim om informatie uit AI altijd te controleren met andere bronnen, omdat AI zich kan vergissen of dingen kan verzinnen.",
    "core_leefwereld_5": "Een app die foto's groepeert gebruikt vaak AI om gezichten, plaatsen of voorwerpen te herkennen en foto's automatisch te ordenen.",
    "core_risicos_1": "Bias betekent dat er een vooroordeel of scheefheid in de data zit. Daardoor kan AI sommige groepen of situaties oneerlijk beoordelen.",
    "core_risicos_2": "Je moet AI-antwoorden controleren omdat AI soms zelfverzekerd iets fout of verzonnen kan zeggen. Dat heet ook wel hallucineren.",
    "core_risicos_3": "Een AI-foto kan nep zijn maar toch echt lijken. Daarom is het belangrijk om kritisch te kijken naar details en context.",
    "core_risicos_4": "Privacy is belangrijk omdat gegevens die je invoert soms worden opgeslagen of gebruikt om systemen verder te trainen of te verbeteren.",
    "core_risicos_5": "Bij vreemd AI-advies check je best eerst een betrouwbare bron, omdat AI niet altijd juist, volledig of veilig is.",
    "core_verantwoord_1": "Verantwoord AI-gebruik betekent dat je controleert wat AI zegt en zelf blijft nadenken. AI mag helpen, maar niet al je werk of oordeel vervangen.",
    "core_verantwoord_2": "Als AI iets gemeens maakt, gebruik je dat best niet zomaar. Je past het aan of laat het weg, zodat je niemand kwetst of misleidt.",
    "core_verantwoord_3": "Het is eerlijk om te zeggen dat je AI gebruikte, omdat je dan transparant bent over hoe je werkte en wat nog van jezelf kwam.",
    "core_verantwoord_4": "Een goede klasafspraak maakt duidelijk wanneer AI wel en niet mag. Zo weet iedereen wat eerlijk en veilig gebruik is.",
    "core_verantwoord_5": "Respectvol AI-gebruik begint bij veilige, duidelijke en beleefde prompts. Je gebruikt AI dan zonder anderen te schaden of gevoelige info te delen.",
}

THEME_EXPLANATION_FALLBACKS = {
    "werking": "In dit thema gaat het om hoe AI werkt: modellen leren uit voorbeelden, volgen instructies en herkennen patronen in data. Ze denken niet zelfstandig zoals mensen.",
    "leefwereld": "In het dagelijks leven zit AI vaak in apps en tools die aanbevelen, zoeken, voorspellen of automatisch helpen. Het is dus belangrijk om zulke toepassingen te herkennen.",
    "kritisch": "In dit thema gaat het om AI kritisch beoordelen: controleren, privacy bewaken, eerlijk blijven, veilig handelen en niet blind vertrouwen op output die slim klinkt.",
    "kansen": "In dit thema gaat het om waar AI echt kan helpen: sneller zoeken, plannen, uitleg krijgen, creatief werken of ondersteuning krijgen in herkenbare situaties.",
    "beeld": "In dit thema gaat het om AI-foto's herkennen: traag kijken, details controleren, bron en context meenemen en niet te snel geloven dat een beeld echt is.",
    "risicos": "In dit thema gaat het om AI kritisch beoordelen: controleren, privacy bewaken, eerlijk blijven, veilig handelen en niet blind vertrouwen op output die slim klinkt.",
    "verantwoord": "In dit thema gaat het om AI kritisch beoordelen: controleren, privacy bewaken, eerlijk blijven, veilig handelen en niet blind vertrouwen op output die slim klinkt.",
    "beeldronde": "In dit thema gaat het om AI-foto's herkennen: traag kijken, details controleren, bron en context meenemen en niet te snel geloven dat een beeld echt is.",
}


def normalize_text_for_similarity(text: object) -> str:
    value = unicodedata.normalize("NFKD", str(text or ""))
    ascii_value = value.encode("ascii", "ignore").decode("ascii")
    lowered = ascii_value.casefold()
    collapsed = re.sub(r"[^a-z0-9]+", " ", lowered)
    return " ".join(collapsed.split())


def similarity_tokens(text: object) -> set[str]:
    tokens = {
        token
        for token in normalize_text_for_similarity(text).split()
        if len(token) > 2 and token not in QUESTION_STOPWORDS
    }
    return tokens


def jaccard_similarity(left: set[str], right: set[str]) -> float:
    if not left or not right:
        return 0.0
    return len(left & right) / len(left | right)


def question_similarity_score(left_question: dict, right_question: dict) -> float:
    left_text = normalize_text_for_similarity(left_question.get("question", ""))
    right_text = normalize_text_for_similarity(right_question.get("question", ""))
    if not left_text or not right_text:
        return 0.0
    if left_text == right_text:
        return 1.0

    token_score = jaccard_similarity(
        similarity_tokens(left_question.get("question", "")),
        similarity_tokens(right_question.get("question", "")),
    )
    sequence_score = SequenceMatcher(None, left_text, right_text).ratio()
    return max(token_score, sequence_score)


def option_overlap_ratio(left_question: dict, right_question: dict) -> float:
    left_options = {
        normalize_text_for_similarity(option)
        for option in list(left_question.get("options") or [])
        if normalize_text_for_similarity(option)
    }
    right_options = {
        normalize_text_for_similarity(option)
        for option in list(right_question.get("options") or [])
        if normalize_text_for_similarity(option)
    }
    if not left_options or not right_options:
        return 0.0
    return len(left_options & right_options) / max(len(left_options), len(right_options))


def find_similar_question(candidate: dict, existing_questions: List[dict]) -> Optional[dict]:
    candidate_type = str(candidate.get("type") or "multiple_choice")

    for existing in existing_questions:
        existing_type = str(existing.get("type") or "multiple_choice")
        if existing_type != candidate_type:
            continue

        similarity = question_similarity_score(candidate, existing)
        option_overlap = option_overlap_ratio(candidate, existing)

        if similarity >= 0.88:
            return existing

        if similarity >= 0.73 and option_overlap >= 0.25:
            return existing

        if similarity >= 0.5 and option_overlap >= 0.5:
            return existing

    return None


def normalize_image_question_key(question: dict) -> str:
    return normalize_text_for_similarity(question.get("image_url", ""))


def find_duplicate_image_question(candidate: dict, existing_questions: List[dict]) -> Optional[dict]:
    candidate_key = normalize_image_question_key(candidate)
    if not candidate_key:
        return None

    for existing in existing_questions:
        existing_type = str(existing.get("type") or "multiple_choice")
        if existing_type != "image_binary":
            continue
        if normalize_image_question_key(existing) == candidate_key:
            return existing

    return None


def dedupe_core_question_bank(questions: List[dict]) -> tuple[List[dict], List[str]]:
    kept_questions: List[dict] = []
    removed_ids: List[str] = []

    for question in questions:
        if find_similar_question(question, kept_questions) is not None:
            question_id = str(question.get("id") or "").strip()
            if question_id:
                removed_ids.append(question_id)
            continue
        kept_questions.append(question)

    return kept_questions, removed_ids


def dedupe_image_question_bank(questions: List[dict]) -> tuple[List[dict], List[str]]:
    kept_questions: List[dict] = []
    removed_ids: List[str] = []

    for question in questions:
        if find_duplicate_image_question(question, kept_questions) is not None:
            question_id = str(question.get("id") or "").strip()
            if question_id:
                removed_ids.append(question_id)
            continue
        kept_questions.append(question)

    return kept_questions, removed_ids


def build_generation_avoid_list(questions: List[dict], theme: str, rejected_variants: List[str], limit: int = 10) -> str:
    examples = [
        str(question.get("question", "")).strip()
        for question in questions
        if question.get("theme") == theme and question.get("question")
    ]
    examples.extend(rejected_variants)
    unique_examples: List[str] = []
    seen = set()
    for example in examples:
        normalized = normalize_text_for_similarity(example)
        if not normalized or normalized in seen:
            continue
        seen.add(normalized)
        unique_examples.append(example)

    if not unique_examples:
        return ""

    trimmed = unique_examples[:limit]
    return "\n".join(f"- {example}" for example in trimmed)


def prune_duplicate_pending_ai_questions() -> List[dict]:
    questions = rebalance_ai_question_answer_positions()
    if not questions:
        return []

    changed = False
    seen_questions: List[dict] = []

    for question in questions:
        is_pending_ai = (
            question.get("source") == "ai"
            and question.get("approved") is False
            and not question.get("rejected", False)
        )

        if is_pending_ai:
            similar = find_similar_question(question, seen_questions)
            if similar is not None:
                question["approved"] = False
                question["rejected"] = True
                changed = True
                continue

        if not question.get("rejected", False):
            seen_questions.append(question)

    if changed:
        save_core_questions(questions)

    return questions


def with_question_difficulty_metadata(question: dict) -> dict:
    payload = dict(question)
    if str(payload.get("type") or "multiple_choice") == "multiple_choice":
        payload["difficulty"] = question_difficulty_key_for_question(payload)
        payload["difficulty_label"] = question_difficulty_label(payload)
        payload["difficulty_short_label"] = question_difficulty_short_label(payload)
    return payload


def difficulty_count_template() -> Dict[str, int]:
    return {difficulty: 0 for difficulty in QUESTION_DIFFICULTY_ORDER}


def choose_balanced_core_question(core_questions: List[dict], theme_key: str) -> Optional[dict]:
    available_by_difficulty: Dict[str, List[dict]] = {
        difficulty: []
        for difficulty in QUESTION_DIFFICULTY_ORDER
    }
    used_counts = difficulty_count_template()

    for question in core_questions:
        if str(question.get("type") or "multiple_choice") != "multiple_choice":
            continue
        if question.get("theme") != theme_key:
            continue
        if not question.get("approved", True) or question.get("rejected", False):
            continue

        difficulty_key = question_difficulty_key_for_question(question)
        if question.get("used", False):
            used_counts[difficulty_key] += 1
            continue

        available_by_difficulty[difficulty_key].append(question)

    available_difficulties = [
        difficulty
        for difficulty in QUESTION_DIFFICULTY_ORDER
        if available_by_difficulty[difficulty]
    ]
    if not available_difficulties:
        return None

    lowest_used_count = min(used_counts[difficulty] for difficulty in available_difficulties)
    least_served_difficulties = [
        difficulty
        for difficulty in available_difficulties
        if used_counts[difficulty] == lowest_used_count
    ]

    for preferred_difficulty in QUESTION_DIFFICULTY_SELECTION_PRIORITY:
        if preferred_difficulty in least_served_difficulties:
            return random.choice(available_by_difficulty[preferred_difficulty])

    fallback_difficulty = least_served_difficulties[0]
    return random.choice(available_by_difficulty[fallback_difficulty])


def choose_core_question_for_mode(
    core_questions: List[dict],
    theme_key: str,
    mode: str = "mix",
) -> Optional[dict]:
    normalized_mode = normalize_question_difficulty_mode(mode)
    if normalized_mode == "mix":
        return choose_balanced_core_question(core_questions, theme_key)

    available_by_difficulty: Dict[str, List[dict]] = {
        difficulty: []
        for difficulty in QUESTION_DIFFICULTY_ORDER
    }

    for question in core_questions:
        if str(question.get("type") or "multiple_choice") != "multiple_choice":
            continue
        if question.get("theme") != theme_key:
            continue
        if question.get("used", False):
            continue
        if not question.get("approved", True) or question.get("rejected", False):
            continue

        available_by_difficulty[question_difficulty_key_for_question(question)].append(question)

    difficulty_priority = (
        ["basis", "verdieping", "uitdaging"]
        if normalized_mode == "basis"
        else ["uitdaging", "verdieping", "basis"]
    )

    for difficulty_key in difficulty_priority:
        if available_by_difficulty[difficulty_key]:
            return random.choice(available_by_difficulty[difficulty_key])

    return None


def current_question_difficulty_mode(gs: Optional[GameState] = None) -> str:
    if gs is not None:
        return normalize_question_difficulty_mode(getattr(gs, "question_difficulty_mode", None))
    return normalize_question_difficulty_mode(QUESTION_DIFFICULTY_MODE)


def choose_generation_difficulty(theme_key: str, questions: List[dict]) -> str:
    counts = difficulty_count_template()

    for question in questions:
        if str(question.get("type") or "multiple_choice") != "multiple_choice":
            continue
        if question.get("theme") != theme_key:
            continue
        if question.get("rejected", False):
            continue

        counts[question_difficulty_key_for_question(question)] += 1

    lowest_count = min(counts.values()) if counts else 0
    underrepresented = [
        difficulty
        for difficulty in QUESTION_DIFFICULTY_ORDER
        if counts.get(difficulty, 0) == lowest_count
    ]

    for preferred_difficulty in QUESTION_DIFFICULTY_SELECTION_PRIORITY:
        if preferred_difficulty in underrepresented:
            return preferred_difficulty

    return "verdieping"


def multiple_choice_quality_issues(question: dict, difficulty_key: Optional[str] = None) -> List[str]:
    if str(question.get("type") or "multiple_choice") != "multiple_choice":
        return []

    options = [str(option).strip() for option in list(question.get("options") or [])]
    correct_index = question.get("correct_index")
    if len(options) != 4 or not isinstance(correct_index, int) or not 0 <= correct_index < 4:
        return ["De vraag heeft geen geldige set van vier antwoordopties."]

    issues: List[str] = []
    normalized_question = normalize_text_for_similarity(question.get("question", ""))
    if len(normalized_question.split()) < 6:
        issues.append("De vraag mist nog context en is te kort om echt te laten redeneren.")

    normalized_options = [normalize_text_for_similarity(option) for option in options]
    word_counts = [len(option.split()) for option in normalized_options]
    correct_option = normalized_options[correct_index]
    correct_tokens = similarity_tokens(options[correct_index])
    question_tokens = similarity_tokens(question.get("question", ""))
    overlap_target_tokens = correct_tokens | question_tokens

    plausible_distractors = 0
    overlapping_distractors = 0

    for index, option in enumerate(normalized_options):
        if any(marker in option for marker in TRIVIAL_DISTRACTOR_MARKERS):
            issues.append("Er zit nog een flauwe of te makkelijke afleider tussen.")
            break

        if index == correct_index:
            continue

        if len(option.split()) >= max(2, len(correct_option.split()) - 1):
            plausible_distractors += 1
        if similarity_tokens(options[index]) & overlap_target_tokens:
            overlapping_distractors += 1

        if difficulty_key in {"verdieping", "uitdaging"} and len(option.split()) < 3:
            issues.append("Minstens één fout antwoord is te kort om geloofwaardig te zijn.")
            break

    if max(word_counts) - min(word_counts) >= 7:
        issues.append("De antwoordopties verschillen te sterk in lengte, waardoor één optie te veel opvalt.")
    if plausible_distractors < 2:
        issues.append("De foute opties leunen nog te weinig aan bij het echte antwoord.")
    if overlapping_distractors < 2:
        issues.append("Minstens twee foute opties moeten inhoudelijk dichter bij het juiste antwoord liggen.")

    deduped_issues: List[str] = []
    seen = set()
    for issue in issues:
        if issue not in seen:
            seen.add(issue)
            deduped_issues.append(issue)
    return deduped_issues


def build_question_payload(question: dict, fallback_theme: str) -> dict:
    question_type = str(question.get("type") or "multiple_choice")
    is_image_question = question_type == "image_binary"
    fallback_theme_label = THEMES.get(fallback_theme, {}).get("label", fallback_theme)

    if is_image_question:
        instruction = (
            question.get("instruction")
            or "Kijk goed naar het beeld en kies of het waarschijnlijk een echte foto is, of door AI gegenereerd of bewerkt."
        )
        eyebrow = question.get("eyebrow") or "Beeldvraag"
        fallback_theme_label = THEMES["beeld"]["label"]
    else:
        instruction = (
            question.get("instruction")
            or question_difficulty_instruction(question)
        )
        eyebrow = question.get("eyebrow") or "Meerkeuzevraag"

    payload = {
        "id": question["id"],
        "question": question["question"],
        "options": question["options"],
        "type": question_type,
        "display_theme": question.get("display_theme") or fallback_theme_label,
        "instruction": instruction,
        "eyebrow": eyebrow,
    }

    if not is_image_question:
        payload["difficulty"] = question_difficulty_key_for_question(question)
        payload["difficulty_label"] = question_difficulty_label(question)
        payload["difficulty_short_label"] = question_difficulty_short_label(question)

    if question.get("image_url"):
        payload["image_url"] = question["image_url"]

    if question.get("image_alt"):
        payload["image_alt"] = question["image_alt"]

    return payload


def build_prompt_improvement_payload() -> dict:
    mission = random.choice(PROMPT_IMPROVEMENT_MISSIONS)
    prompt_id = "prompt-improvement-" + str(int(time.time() * 1000)) + "-" + "".join(random.choices(string.ascii_lowercase, k=5))
    return {
        "id": prompt_id,
        "type": "prompt_improvement",
        "display_theme": THEMES["kansen"]["label"],
        "eyebrow": "Promptmissie",
        "instruction": "Verbeter de zwakke prompt. Maak hem duidelijker, concreter en nuttiger, zonder de taak volledig door AI te laten overnemen.",
        "question": "Verbeter deze prompt zodat AI beter kan helpen.",
        "situation": mission["situation"],
        "weak_prompt": mission["weak_prompt"],
        "goal": mission["goal"],
        "options": [],
        "difficulty": "verdieping",
        "difficulty_label": QUESTION_DIFFICULTIES["verdieping"]["label"],
        "difficulty_short_label": QUESTION_DIFFICULTIES["verdieping"]["short_label"],
    }


def build_manageable_question_summary(
    question: dict,
    store: Literal["core", "image", "consensus"],
) -> dict:
    default_type = "consensus_dilemma" if store == "consensus" else "multiple_choice"
    question_type = str(question.get("type") or default_type)
    theme_key = str(question.get("theme") or "")

    if question_type == "image_binary":
        fallback_theme_label = THEMES["beeld"]["label"]
    elif question_type == "consensus_dilemma":
        fallback_theme_label = "Groepsdilemma"
    else:
        fallback_theme_label = "Vraag"

    theme_label = (
        question.get("display_theme")
        or THEMES.get(theme_key, {}).get("label")
        or fallback_theme_label
    )

    payload = {
        "id": question["id"],
        "question": question["question"],
        "type": question_type,
        "store": store,
        "source": str(question.get("source") or ""),
        "display_theme": theme_label,
        "used": bool(question.get("used", False)),
    }

    if question_type == "image_binary":
        payload["image_url"] = question.get("image_url", "")
        payload["image_alt"] = question.get("image_alt", "")
        payload["explanation"] = learning_explanation_text(question)
        payload["correct_label"] = image_binary_answer_label(question.get("correct_index"))
    elif question_type == "consensus_dilemma":
        payload["guidance"] = str(question.get("guidance") or "").strip()
    else:
        payload["options"] = list(question.get("options") or [])
        payload["correct_label"] = answer_label_from_index(question.get("correct_index"))
        payload["difficulty"] = question_difficulty_key_for_question(question)
        payload["difficulty_label"] = question_difficulty_label(question)
        payload["difficulty_short_label"] = question_difficulty_short_label(question)

    return payload


def answer_label_from_index(index: object) -> str:
    if not isinstance(index, int) or index < 0:
        return "Onbekend"
    labels = ["A", "B", "C", "D"]
    return labels[index] if index < len(labels) else str(index + 1)


def correct_option_text(question: dict) -> str:
    correct_index = question.get("correct_index")
    options = list(question.get("options") or [])
    if isinstance(correct_index, int) and 0 <= correct_index < len(options):
        return str(options[correct_index]).strip()
    return ""


def learning_explanation_text(question: dict) -> str:
    explicit = str(question.get("explanation") or "").strip()
    if explicit:
        return explicit

    question_id = str(question.get("id") or "").strip()
    if question_id in QUESTION_EXPLANATION_FALLBACKS:
        return QUESTION_EXPLANATION_FALLBACKS[question_id]

    correct_text = correct_option_text(question)
    if str(question.get("type") or "multiple_choice") == "image_binary":
        if question.get("correct_index") == 1:
            source_label = trusted_real_source_label_for_url(question.get("image_url"))
            source_text = f" uit {source_label}" if source_label else ""
            return (
                f"Dit is een echte foto{source_text}. Licht, schaduwen, perspectief en kleine details blijven hier logisch samenwerken. "
                "Tip: kijk bij twijfel naar tekst, reflecties, handen en herhalende patronen voor je iets als fake bestempelt."
            )
        scene_hint = scene_specific_ai_explanation(question)
        if scene_hint:
            return scene_hint
        return (
            "Er zit in dit beeld een klein detail dat niet logisch doorloopt, ook al oogt de foto op het eerste zicht geloofwaardig. "
            "Tip: zoom in op een klein verdacht stukje en controleer letters, reflecties, randen of vingers heel precies."
        )

    theme = str(question.get("theme") or "").strip()
    label = answer_label_from_index(question.get("correct_index"))
    theme_hint = THEME_EXPLANATION_FALLBACKS.get(
        theme,
        "Het juiste antwoord past het best bij wat AI doet of hoe je AI kritisch en verantwoord gebruikt."
    )
    if correct_text:
        return f"Het juiste antwoord is {label}: {correct_text}. {theme_hint}"
    return theme_hint


def load_all_consensus_dilemmas() -> List[dict]:
    disabled_ids = set(load_disabled_consensus_ids())
    built_in = []
    for dilemma in ETHICAL_AI_DILEMMAS:
        entry = dict(dilemma)
        if entry.get("id") in disabled_ids:
            continue
        entry["type"] = "consensus_dilemma"
        entry["display_theme"] = entry.get("display_theme") or "Groepsdilemma"
        entry["source"] = entry.get("source") or "system"
        built_in.append(entry)

    custom = []
    for dilemma in load_consensus_dilemmas():
        entry = dict(dilemma)
        if entry.get("id") in disabled_ids:
            continue
        entry["type"] = "consensus_dilemma"
        entry["display_theme"] = entry.get("display_theme") or "Groepsdilemma"
        entry["source"] = entry.get("source") or "teacher"
        custom.append(entry)

    return built_in + custom


def load_removable_questions() -> List[dict]:
    removable: List[dict] = []

    for question in load_core_questions():
        removable.append(build_manageable_question_summary(question, "core"))

    for question in load_image_questions():
        removable.append(build_manageable_question_summary(question, "image"))

    for dilemma in load_all_consensus_dilemmas():
        removable.append(build_manageable_question_summary(dilemma, "consensus"))

    removable.reverse()
    return removable


def delete_removable_question(question_id: str) -> bool:
    core_questions = load_core_questions()
    for index, question in enumerate(core_questions):
        if question.get("id") != question_id:
            continue
        core_questions.pop(index)
        save_core_questions(core_questions)
        return True

    image_questions = load_image_questions()
    for index, question in enumerate(image_questions):
        if question.get("id") != question_id:
            continue
        image_questions.pop(index)
        save_image_questions(image_questions)
        return True

    consensus_dilemmas = load_consensus_dilemmas()
    for index, dilemma in enumerate(consensus_dilemmas):
        if dilemma.get("id") != question_id:
            continue
        consensus_dilemmas.pop(index)
        save_consensus_dilemmas(consensus_dilemmas)
        return True

    built_in_ids = {
        str(dilemma.get("id") or "").strip()
        for dilemma in ETHICAL_AI_DILEMMAS
        if str(dilemma.get("id") or "").strip()
    }
    if question_id in built_in_ids:
        disabled_ids = load_disabled_consensus_ids()
        if question_id not in disabled_ids:
            disabled_ids.append(question_id)
            save_disabled_consensus_ids(disabled_ids)
        return True

    return False


def mark_consensus_dilemma_used(dilemma_id: str) -> Optional[dict]:
    dilemmas = load_consensus_dilemmas()
    for dilemma in dilemmas:
        if dilemma.get("id") != dilemma_id:
            continue

        dilemma["used"] = True
        save_consensus_dilemmas(dilemmas)
        return dilemma

    return None


def mark_question_used(question_id: str) -> Optional[dict]:
    for load_questions, save_questions in (
        (load_core_questions, save_core_questions),
        (load_image_questions, save_image_questions),
    ):
        questions = load_questions()
        for question in questions:
            if question.get("id") != question_id:
                continue

            question["used"] = True
            if is_image_binary_question(question):
                scene_key = image_scene_family_key(question)
                if scene_key:
                    recent_scene_keys = load_recent_image_scene_keys()
                    recent_scene_keys.append(scene_key)
                    save_recent_image_scene_keys(recent_scene_keys)

                family_key = image_scene_family_key(question)
                for sibling in questions:
                    if sibling.get("id") == question_id:
                        continue
                    if not is_image_binary_question(sibling):
                        continue
                    if image_scene_family_key(sibling) == family_key:
                        sibling["used"] = True
            save_questions(questions)
            return question

    for question in build_trusted_real_image_questions():
        if question.get("id") != question_id:
            continue

        used_ids = load_used_trusted_real_image_ids()
        if question_id not in used_ids:
            used_ids.append(question_id)
            save_used_trusted_real_image_ids(used_ids)
        scene_key = image_scene_family_key(question)
        if scene_key:
            recent_scene_keys = load_recent_image_scene_keys()
            recent_scene_keys.append(scene_key)
            save_recent_image_scene_keys(recent_scene_keys)
        question["used"] = True
        return question

    return None


def normalize_question_options(options: List[str]) -> List[str]:
    normalized = [str(option).strip() for option in options]
    if len(normalized) != 4 or any(not option for option in normalized):
        raise HTTPException(400, "Een vraag moet exact 4 niet-lege antwoordopties hebben.")
    return normalized


def stable_question_correct_index(question: dict) -> int:
    stable_key = str(question.get("id") or "").strip() or normalize_text_for_similarity(question.get("question", ""))
    if not stable_key:
        return 0

    digest = hashlib.sha256(stable_key.encode("utf-8")).digest()
    return digest[0] % 4


def move_correct_option_to_index(question: dict, target_index: int) -> bool:
    options = list(question.get("options") or [])
    current_index = question.get("correct_index")
    if len(options) != 4 or not isinstance(current_index, int) or not 0 <= current_index < len(options):
        return False
    if not 0 <= target_index < len(options):
        return False
    if current_index == target_index:
        return False

    correct_option = options.pop(current_index)
    options.insert(target_index, correct_option)
    question["options"] = options
    question["correct_index"] = target_index
    return True


def rebalance_core_question_answer_positions_in_memory(questions: List[dict]) -> bool:
    changed = False
    for question in questions:
        if question.get("source") not in {"ai", "core"}:
            continue
        if question.get("rejected", False):
            continue
        if str(question.get("type") or "multiple_choice") != "multiple_choice":
            continue

        target_index = stable_question_correct_index(question)
        if move_correct_option_to_index(question, target_index):
            changed = True

    return changed


def rebalance_ai_question_answer_positions() -> List[dict]:
    return load_core_questions()


def require_teacher_password(x_teacher_password: Optional[str]) -> None:
    if not TEACHER_PASSWORD:
        raise HTTPException(500, "Er is geen leerkrachtpaswoord ingesteld.")

    provided_password = (x_teacher_password or "").strip()
    if provided_password != TEACHER_PASSWORD:
        raise HTTPException(401, "Onjuist leerkrachtpaswoord.")


def has_valid_teacher_password(x_teacher_password: Optional[str]) -> bool:
    return bool(TEACHER_PASSWORD) and (x_teacher_password or "").strip() == TEACHER_PASSWORD


def next_prefixed_question_id(questions: List[dict], prefix: str) -> str:
    highest_id = 0
    for question in questions:
        question_id = str(question.get("id", ""))
        if not question_id.startswith(prefix):
            continue

        suffix = question_id.removeprefix(prefix)
        if suffix.isdigit():
            highest_id = max(highest_id, int(suffix))

    return f"{prefix}{highest_id + 1}"


def next_ai_question_id(questions: List[dict]) -> str:
    return next_prefixed_question_id(questions, "ai_")


def next_teacher_question_id(questions: List[dict]) -> str:
    return next_prefixed_question_id(questions, "teacher_")


def next_teacher_consensus_id(dilemmas: List[dict]) -> str:
    return next_prefixed_question_id(dilemmas, "ethics_teacher_")


def random_empty_coord(occupied: set[str]) -> Coord:
    choices = [c for c in all_coords() if c not in occupied]
    if not choices:
        raise RuntimeError("No empty coordinates available")
    return random.choice(choices)


def random_destroyed_coords(gs: "GameState", count: int) -> List[Coord]:
    blocked = set(gs.destroyed_tiles)
    if gs.exit_known and gs.exit_coord:
        blocked.add(gs.exit_coord)
    blocked.update(player.start_coord for player in gs.players)

    choices = [coord for coord in all_coords() if coord not in blocked]
    if len(choices) < count:
        raise HTTPException(400, "Er zijn niet genoeg vrije tegels meer om willekeurig te laten ontploffen.")

    return random.sample(choices, count)


def should_trigger_random_dynamite_blast(distributed_count: int) -> bool:
    if distributed_count < 4:
        return False
    if distributed_count >= 6:
        return True

    # Gives each outcome (4, 5 or 6 distributed sticks) the same overall chance.
    remaining_trigger_counts = 6 - distributed_count + 1
    return random.randint(1, remaining_trigger_counts) == 1


def two_by_two_block_candidates(anchor_coord: Coord) -> List[List[Coord]]:
    col, row = parse_coord(anchor_coord)
    col_index = COLS.index(col)
    candidates: List[Tuple[int, List[Coord]]] = []

    for col_shift in (0, -1):
        for row_shift in (0, -1):
            top_left_col = col_index + col_shift
            top_left_row = row + row_shift
            if top_left_col < 0 or top_left_col + 1 >= len(COLS):
                continue
            if top_left_row < 1 or top_left_row + 1 > ROWS[-1]:
                continue

            block = [
                f"{COLS[top_left_col]}{top_left_row}",
                f"{COLS[top_left_col + 1]}{top_left_row}",
                f"{COLS[top_left_col]}{top_left_row + 1}",
                f"{COLS[top_left_col + 1]}{top_left_row + 1}",
            ]
            shift_cost = abs(col_shift) + abs(row_shift)
            candidates.append((shift_cost, block))

    candidates.sort(key=lambda item: (item[0], item[1][0]))
    return [block for _, block in candidates]

def manhattan(a: Coord, b: Coord) -> int:
    ac, ar = parse_coord(a)
    bc, br = parse_coord(b)
    return abs(COLS.index(ac) - COLS.index(bc)) + abs(ar - br)


# ----------------------------
# Models
# ----------------------------

Phase = Literal["setup", "running", "endgame", "exploded", "finished"]

class Player(BaseModel):
    id: str
    name: str
    start_coord: Coord
    info_cards: int = 0
    dynamite: int = 0
    escaped: bool = False
    escaped_at: Optional[float] = None  # epoch seconds


class AllTimeRankingEntry(BaseModel):
    id: str
    game_id: str
    created_at: float
    player_names: List[str] = Field(default_factory=list)
    escaped_player_count: int = 0
    diamond_total: int = 0


class GroupEvaluationTheme(BaseModel):
    label: str
    answered: int = 0
    correct: int = 0


class GroupEvaluationMistake(BaseModel):
    theme_label: str
    question: str
    chosen_option: str = ""
    correct_option: str = ""
    explanation: str = ""


class GroupEvaluation(BaseModel):
    total_answered: int = 0
    total_correct: int = 0
    themes: Dict[str, GroupEvaluationTheme] = Field(default_factory=dict)
    mistakes: List[GroupEvaluationMistake] = Field(default_factory=list)


class SpawnItem(BaseModel):
    kind: Literal["diamond", "dynamite"]
    coord: Coord
    spawned_at: float


class GameState(BaseModel):
    game_id: str
    phase: Phase = "setup"
    question_difficulty_mode: Literal["basis", "mix", "uitdaging"] = "mix"

    # Timing
    started_at: Optional[float] = None
    deadline_at: Optional[float] = None  # explosion moment
    auto_exit_reveal_at: Optional[float] = None  # time when exit becomes visible automatically (25 min)
    timer_paused: bool = False
    paused_at: Optional[float] = None
    pause_reasons: List[str] = Field(default_factory=list)
    distributed_dynamite_count: int = 0
    last_dynamite_blast_id: int = 0
    last_dynamite_blast_blocks: List[List[Coord]] = Field(default_factory=list)
    last_dynamite_blast_board_count: int = 0
    last_dynamite_blast_player_count: int = 0
    last_dynamite_blast_summary: str = ""

    # Exit
    exit_known: bool = False
    exit_coord: Optional[Coord] = None

    # Turn mgmt
    players: List[Player] = Field(default_factory=list)
    turn_index: int = 0  # index in players list

    # Items on board
    items: List[SpawnItem] = Field(default_factory=list)
    next_diamond_spawn_at: Optional[float] = None
    next_dynamite_spawn_at: Optional[float] = None
    destroyed_tiles: List[Coord] = Field(default_factory=list)

    # Group ethics challenge
    consensus_used_count: int = 0
    consensus_used_ids: List[str] = Field(default_factory=list)
    consensus_active: bool = False
    consensus_question_id: Optional[str] = None
    consensus_question: Optional[str] = None
    consensus_guidance: Optional[str] = None
    passage_bonus_tiles: int = 0

    # Control flags
    emergency_pressed: bool = False
    emergency_pressed_by: Optional[str] = None
    emergency_pressed_at: Optional[float] = None

    # Ranking
    all_time_ranking: List[AllTimeRankingEntry] = Field(default_factory=list)
    latest_all_time_ranking_entry_id: Optional[str] = None
    final_result_note: Optional[str] = None
    ranking_recorded: bool = False
    ranking_name_prompt_pending: bool = False
    group_evaluation: GroupEvaluation = Field(default_factory=GroupEvaluation)

    # Logging
    event_log: List[str] = Field(default_factory=list)

    def current_player(self) -> Optional[Player]:
        if not self.players:
            return None
        # Skip escaped players when selecting current
        for _ in range(len(self.players)):
            p = self.players[self.turn_index]
            if not p.escaped:
                return p
            self.turn_index = (self.turn_index + 1) % len(self.players)
        return None  # all escaped

    def remaining_seconds(self) -> Optional[int]:
        if self.deadline_at is None:
            return None
        reference_time = self.paused_at if self.timer_paused and self.paused_at else time.time()
        return max(0, int(self.deadline_at - reference_time))

    def occupied_coords(self, include_start_coords: bool = False) -> set[str]:
        occ = set()
        if self.exit_known and self.exit_coord:
            occ.add(self.exit_coord)
        for it in self.items:
            occ.add(it.coord)
        occ.update(self.destroyed_tiles)
        if include_start_coords:
            for p in self.players:
                occ.add(p.start_coord)
        return occ


# ----------------------------
# Requests / Responses
# ----------------------------

class NewGameRequest(BaseModel):
    player_names: List[str] = Field(min_items=1, max_items=8)
    timer_minutes: int = 30
    auto_exit_reveal_minute: int = 25   # after game start
    emergency_endgame_minutes: int = 5  # explosion occurs this many minutes after emergency press
    min_start_distance: int = 4         # min manhattan distance between players (soft)
    seed: Optional[int] = None


class RankingFinalizeRequest(BaseModel):
    player_names: List[str] = Field(min_items=1, max_items=8)


class ActionResponse(BaseModel):
    ok: bool
    message: str
    state: GameState


class OptionalStateActionResponse(BaseModel):
    ok: bool
    message: str
    state: Optional[GameState] = None


class QuestionDifficultyModeRequest(BaseModel):
    mode: Literal["basis", "mix", "uitdaging"]


class SpawnRequest(BaseModel):
    kind: Literal["diamond", "dynamite"]
    max_simultaneous: int = 3  # e.g. dynamite max 3 simultaneously; can use for diamonds too


class RemoveItemRequest(BaseModel):
    coord: Coord


class ChatRequest(BaseModel):
    player_id: Optional[str] = None
    message: str


class QuestionReviewRequest(BaseModel):
    id: str
    action: Literal["approve", "reject", "delete"]
    question: Optional[str] = None
    options: Optional[List[str]] = None
    correct_index: Optional[int] = None


class TeacherQuestionCreateRequest(BaseModel):
    question_type: Literal["multiple_choice", "image_binary", "consensus_dilemma"] = "multiple_choice"
    theme: Optional[str] = None
    question: str
    options: Optional[List[str]] = None
    correct_index: int
    image_url: Optional[str] = None
    image_alt: Optional[str] = None
    explanation: Optional[str] = None
    guidance: Optional[str] = None


class TeacherImageUploadRequest(BaseModel):
    data_url: str
    filename: Optional[str] = None


class TeacherAutoImageSetRequest(BaseModel):
    count: int = Field(default=4, ge=AUTO_IMAGE_SET_MIN_COUNT, le=AUTO_IMAGE_SET_MAX_COUNT)
    focus: Optional[str] = None


class TeacherQuestionDeleteRequest(BaseModel):
    id: str


class TeacherAISettingsRequest(BaseModel):
    mode: Literal["default", "byok", "disabled"]
    api_key: Optional[str] = None
    owner_password: Optional[str] = None
    ttl_minutes: int = Field(default=AI_BYOK_DEFAULT_TTL_MINUTES, ge=5, le=AI_BYOK_MAX_TTL_MINUTES)


class ConsensusEvaluationRequest(BaseModel):
    decision: Literal["approve", "reject"]


# ----------------------------
# App + In-memory state
# ----------------------------

app = FastAPI(title="De diamantmijn - Game API (MVP)")
from fastapi.responses import FileResponse, Response

HTML_HEADERS = {
    "Cache-Control": "no-store, no-cache, must-revalidate",
    "Pragma": "no-cache",
    "Expires": "0",
}

@app.get("/")
def serve_index():
    return FileResponse("static/index.html", headers=HTML_HEADERS)
app.mount("/static", StaticFiles(directory="static"), name="static")

STATE_LOCK = asyncio.Lock()
AI_IMAGE_POOL_LOCK = asyncio.Lock()
GAME_SESSIONS: Dict[str, GameState] = {}
GAME_SESSION_LAST_SEEN: Dict[str, float] = {}
DEFAULT_GAME_SESSION_ID = "default"
MAX_GAME_SESSIONS = 200
GAME_SESSION_TTL_SECONDS = 12 * 60 * 60
QUESTION_DIFFICULTY_MODE = "mix"

# Global config for current game (stored for the loop)
CONFIG: Dict[str, int] = {
    "timer_minutes": 30,
    "auto_exit_reveal_minute": 25,
    "emergency_endgame_minutes": 5,
    "diamond_spawn_min_seconds": 120,
    "diamond_spawn_max_seconds": 210,
    "diamond_max_simultaneous": 3,
    "dynamite_spawn_min_seconds": 180,
    "dynamite_spawn_max_seconds": 300,
    "dynamite_max_simultaneous": 4,
}


def normalize_game_session_id(x_game_session: Optional[str]) -> str:
    session_id = (x_game_session or DEFAULT_GAME_SESSION_ID).strip()
    if not re.fullmatch(r"[A-Za-z0-9_-]{8,128}", session_id):
        return DEFAULT_GAME_SESSION_ID
    return session_id


def get_game_state(session_id: str) -> Optional[GameState]:
    gs = GAME_SESSIONS.get(session_id)
    if gs is not None:
        GAME_SESSION_LAST_SEEN[session_id] = time.time()
    return gs


def set_game_state(session_id: str, gs: GameState) -> None:
    GAME_SESSIONS[session_id] = gs
    GAME_SESSION_LAST_SEEN[session_id] = time.time()
    prune_game_sessions()


def clear_game_state(session_id: str) -> None:
    GAME_SESSIONS.pop(session_id, None)
    GAME_SESSION_LAST_SEEN.pop(session_id, None)


def prune_game_sessions(now: Optional[float] = None) -> None:
    current = time.time() if now is None else now
    stale_ids = [
        session_id
        for session_id, last_seen in GAME_SESSION_LAST_SEEN.items()
        if session_id != DEFAULT_GAME_SESSION_ID and current - last_seen > GAME_SESSION_TTL_SECONDS
    ]
    for session_id in stale_ids:
        clear_game_state(session_id)

    if len(GAME_SESSIONS) <= MAX_GAME_SESSIONS:
        return

    oldest_ids = sorted(
        GAME_SESSION_LAST_SEEN,
        key=lambda session_id: GAME_SESSION_LAST_SEEN.get(session_id, 0),
    )
    for session_id in oldest_ids:
        if len(GAME_SESSIONS) <= MAX_GAME_SESSIONS:
            break
        if session_id != DEFAULT_GAME_SESSION_ID:
            clear_game_state(session_id)
DEFAULT_RANDOM_SPAWN_CONFIG = {
    "diamond_spawn_min_seconds": 120,
    "diamond_spawn_max_seconds": 210,
    "diamond_max_simultaneous": 3,
    "dynamite_spawn_min_seconds": 180,
    "dynamite_spawn_max_seconds": 300,
    "dynamite_max_simultaneous": 4,
}
@app.post("/api/tile/auto_place")
async def auto_place_tile(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")

        coord = random_empty_coord(gs.occupied_coords(include_start_coords=True))

        _log(gs, f"Fout antwoord. Tegel moet geplaatst worden op {coord}.")

        return {"coord": coord}
# ----------------------------
# Core game functions
# ----------------------------

def _log(gs: GameState, msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    gs.event_log.append(f"[{stamp}] {msg}")
    if len(gs.event_log) > MAX_EVENT_LOG_ENTRIES:
        gs.event_log = gs.event_log[-MAX_EVENT_LOG_ENTRIES:]


def _collect_item_for_player(gs: GameState, player: Player, item: SpawnItem) -> str:
    coord = item.coord

    if item.kind == "diamond":
        player.info_cards += 1
        _log(gs, f"{player.name} verzamelt DIAMANT op {coord} -> +1 diamant (totaal {player.info_cards}).")
        return f"Diamant op {coord} toegevoegd aan {player.name} (totaal {player.info_cards})."

    player.dynamite += 1
    _log(gs, f"{player.name} verzamelt DYNAMIET op {coord} -> +1 dynamiet (totaal {player.dynamite}).")
    return f"Dynamiet op {coord} toegevoegd aan {player.name} (totaal {player.dynamite})."


def _escaped_players(gs: GameState) -> List[Player]:
    return [player for player in gs.players if player.escaped]


def _escaped_player_names(gs: GameState) -> List[str]:
    return [player.name for player in _escaped_players(gs)]


def _escaped_diamond_total(gs: GameState) -> int:
    return sum(max(0, int(player.info_cards or 0)) for player in _escaped_players(gs))


def _normalize_ranking_player_names(player_names: List[str], expected_count: int) -> List[str]:
    normalized_names: List[str] = []
    if expected_count <= 0:
        return normalized_names

    if len(player_names) != expected_count:
        raise HTTPException(
            400,
            f"Geef precies {expected_count} naam{'en' if expected_count != 1 else ''} op voor de ontsnapte spelers.",
        )

    for index, raw_name in enumerate(player_names, start=1):
        normalized_name = str(raw_name or "").strip()
        if not normalized_name:
            raise HTTPException(400, f"Vul een naam in voor ontsnapte speler {index}.")
        normalized_names.append(normalized_name)

    return normalized_names


def _ranking_summary_text(names: List[str], diamond_total: int) -> str:
    if not names:
        return "Niemand raakte op tijd uit de mijn. Er werd geen rankingresultaat toegevoegd."

    names_text = ", ".join(names)
    diamonds_text = f"{diamond_total} diamant{'en' if diamond_total != 1 else ''}"
    if len(names) == 1:
        return f"{names_text} bereikte de uitgang met {diamonds_text}. (1 ontsnapte speler)"

    player_text = f"{len(names)} ontsnapte spelers"
    return f"{names_text} bereikten samen de uitgang met {diamonds_text}. ({player_text})"


def _sync_ranking_snapshot(gs: GameState) -> None:
    gs.all_time_ranking = load_all_time_ranking()


def _persist_all_time_ranking_entry(entry: AllTimeRankingEntry) -> None:
    ranking_entries = load_all_time_ranking()
    ranking_entries = [existing for existing in ranking_entries if existing.id != entry.id]
    ranking_entries.append(entry)
    save_all_time_ranking(ranking_entries)


def _record_all_time_ranking_result(gs: GameState) -> None:
    if gs.ranking_recorded:
        if not gs.all_time_ranking:
            _sync_ranking_snapshot(gs)
        return

    escaped_players = _escaped_players(gs)
    if not escaped_players:
        gs.latest_all_time_ranking_entry_id = None
        gs.final_result_note = _ranking_summary_text([], 0)
        gs.ranking_recorded = True
        gs.ranking_name_prompt_pending = False
        _sync_ranking_snapshot(gs)
        return

    player_names = [player.name for player in escaped_players]
    diamond_total = _escaped_diamond_total(gs)
    entry = AllTimeRankingEntry(
        id=gs.game_id,
        game_id=gs.game_id,
        created_at=time.time(),
        player_names=player_names,
        escaped_player_count=len(player_names),
        diamond_total=diamond_total,
    )

    _persist_all_time_ranking_entry(entry)
    gs.latest_all_time_ranking_entry_id = entry.id
    gs.final_result_note = _ranking_summary_text(player_names, diamond_total)
    gs.ranking_recorded = True
    gs.ranking_name_prompt_pending = True
    _sync_ranking_snapshot(gs)
    _log(gs, "All time ranking bijgewerkt: " + gs.final_result_note)


EVALUATION_THEME_ORDER = ["werking", "leefwereld", "kritisch", "kansen", "beeld", "algemeen"]
EVALUATION_THEME_FEEDBACK = {
    "werking": {
        "background": "AI zoekt patronen in voorbeelden en maakt daarna een waarschijnlijk antwoord. Dat is nuttig, maar AI begrijpt de wereld niet zoals jullie dat doen.",
        "strength": "Dit loopt al goed: jullie lijken te zien dat AI niet echt denkt als een mens. Daardoor is de kans kleiner dat jullie een antwoord zomaar geloven omdat het slim klinkt.",
        "growth": "Let nog extra op het verschil tussen voorspellen, begrijpen en kopieren. Vraag jezelf af: weet AI dit echt, of klinkt het vooral alsof het zeker is?",
        "risk": "Als je denkt dat AI alles begrijpt, kan een fout antwoord heel betrouwbaar lijken. Dan neem je sneller verkeerde informatie over in een taak of uitleg.",
    },
    "leefwereld": {
        "background": "AI zit in zoekmachines, sociale media, navigatie, vertaalapps, aanbevelingen en chatbots. Vaak bepaalt AI mee wat jullie zien zonder dat dat duidelijk wordt getoond.",
        "strength": "Dit loopt al goed: jullie herkennen AI in herkenbare situaties. Dat helpt om kritischer te kijken naar apps, zoekresultaten en aanbevelingen.",
        "growth": "Let nog extra op waarom een app net die video, route, zoekhit of reclame toont. Vraag jezelf af wie voordeel heeft bij wat jij te zien krijgt.",
        "risk": "Als je AI in je dagelijks leven niet herkent, kan je sneller meegaan in eenzijdige informatie, reclame of inhoud die vooral bedoeld is om je aandacht vast te houden.",
    },
    "kansen": {
        "background": "AI kan helpen bij zoeken, plannen, uitleg geven, vertalen, creatief werken en persoonlijke ondersteuning. Zulke kansen werken het best als je tegelijk kritisch blijft denken.",
        "strength": "Dit loopt al goed: jullie zien waar AI echt nuttig kan zijn. Daardoor kunnen jullie AI sneller als hulpmiddel inzetten zonder er meteen afhankelijk van te worden.",
        "growth": "Let nog extra op wanneer AI echt iets toevoegt en wanneer je beter zelf denkt of extra bronnen gebruikt. Een handige tool is nog niet automatisch de beste keuze.",
        "risk": "Als je alleen de voordelen ziet, kan je te snel vergeten dat AI ook fouten maakt of je te afhankelijk kan maken. Kansen werken pas echt goed als je bewust blijft kiezen.",
    },
    "kritisch": {
        "background": "AI kan fouten maken, iets verzinnen, oude informatie gebruiken of vooroordelen uit data overnemen. Daarom horen kritisch kijken, veilig handelen en verantwoord gebruik altijd samen.",
        "strength": "Dit loopt al goed: jullie zien sneller waar het mis kan gaan en kiezen vaker voor controleren, eerlijk blijven, privacy bewaken en duidelijk zeggen hoe AI hielp.",
        "growth": "Let nog extra op broncontrole, transparant zijn over hulp van AI, privacy en niet te snel vertrouwen op een antwoord dat heel zeker of handig klinkt.",
        "risk": "Als je AI niet kritisch genoeg gebruikt, kan dat leiden tot foutieve leerstof, nepnieuws, privacyproblemen, oneerlijke keuzes of werk dat je niet echt begrijpt.",
    },
    "beeld": {
        "background": "AI-foto's en bewerkte beelden kunnen echt lijken. Details zoals handen, tekst, licht, schaduwen, verhoudingen en context kunnen helpen, maar geven niet altijd zekerheid.",
        "strength": "Dit loopt al goed: jullie kijken kritischer naar beelden en zoeken naar aanwijzingen voordat jullie beslissen of iets echt lijkt.",
        "growth": "Let nog extra op traag kijken, broncontrole en context. Bespreek ook waarom een beeld twijfel oproept in plaats van alleen snel te gokken.",
        "risk": "Als je een AI-foto verkeerd inschat, kan je een nepbeeld delen, iemand onterecht beschuldigen of een gemanipuleerd verhaal geloven.",
    },
    "algemeen": {
        "background": "AI-geletterdheid gaat over herkennen, begrijpen, controleren, privacy, eerlijkheid en zelfstandig denken. Die onderdelen horen samen.",
        "strength": "Dit loopt al goed: jullie passen verschillende afspraken rond AI al samen toe.",
        "growth": "Let nog extra op hardop uitleggen waarom een AI-antwoord betrouwbaar, eerlijk en veilig is.",
        "risk": "Als je maar een deel van AI-geletterdheid toepast, kan het toch misgaan: een antwoord kan fout zijn, privacygevoelig zijn of je eigen denken vervangen.",
    },
}


def evaluation_theme_key(question: dict) -> str:
    question_type = str(question.get("type") or "multiple_choice")
    if question_type == "image_binary":
        return "beeld"

    theme = normalize_theme_key(question.get("theme"))
    if theme in THEMES:
        return theme

    return "algemeen"


def evaluation_theme_label(theme_key: str) -> str:
    if theme_key == "algemeen":
        return "Algemene AI-geletterdheid"
    return THEMES.get(theme_key, {}).get("label", theme_key)


def record_group_question_result(
    gs: GameState,
    question: dict,
    correct: bool,
    chosen_index: Optional[int] = None,
) -> None:
    theme_key = evaluation_theme_key(question)
    theme_stats = gs.group_evaluation.themes.get(theme_key)
    if theme_stats is None:
        theme_stats = GroupEvaluationTheme(label=evaluation_theme_label(theme_key))
        gs.group_evaluation.themes[theme_key] = theme_stats

    theme_stats.answered += 1
    gs.group_evaluation.total_answered += 1

    if correct:
        theme_stats.correct += 1
        gs.group_evaluation.total_correct += 1
        return

    options = list(question.get("options") or [])
    chosen_option = ""
    if isinstance(chosen_index, int) and 0 <= chosen_index < len(options):
        chosen_option = str(options[chosen_index]).strip()

    mistake = GroupEvaluationMistake(
        theme_label=theme_stats.label,
        question=str(question.get("question") or "").strip(),
        chosen_option=chosen_option,
        correct_option=correct_option_text(question),
        explanation=learning_explanation_text(question),
    )
    gs.group_evaluation.mistakes.append(mistake)
    gs.group_evaluation.mistakes = gs.group_evaluation.mistakes[-6:]


def sorted_group_evaluation_themes(evaluation: GroupEvaluation) -> List[Tuple[str, GroupEvaluationTheme]]:
    def sort_key(item: Tuple[str, GroupEvaluationTheme]) -> Tuple[int, str]:
        theme_key = item[0]
        try:
            order_index = EVALUATION_THEME_ORDER.index(theme_key)
        except ValueError:
            order_index = len(EVALUATION_THEME_ORDER)
        return order_index, theme_key

    return sorted(evaluation.themes.items(), key=sort_key)


def score_percent(correct: int, answered: int) -> int:
    if answered <= 0:
        return 0
    return int(round((correct / answered) * 100))


def clean_ai_report_text(value: object, max_length: int = 420) -> str:
    text = re.sub(r"\s+", " ", str(value or "")).strip()
    if not text:
        return ""
    if len(text) <= max_length:
        return text

    trimmed = text[:max_length].rsplit(" ", 1)[0].strip()
    return trimmed or text[:max_length].strip()


def clean_ai_report_list(values: object, max_items: int = 4, max_length: int = 420) -> List[str]:
    if not isinstance(values, list):
        return []

    cleaned: List[str] = []
    for value in values:
        text = clean_ai_report_text(value, max_length=max_length)
        if text:
            cleaned.append(text)
        if len(cleaned) >= max_items:
            break
    return cleaned


def build_group_evaluation_ai_payload(gs: GameState) -> dict:
    evaluation = gs.group_evaluation
    strong_themes: List[str] = []
    growth_themes: List[str] = []
    themes_payload: List[dict] = []

    for theme_key, theme_stats in sorted_group_evaluation_themes(evaluation):
        if theme_stats.answered <= 0:
            continue

        theme_score = score_percent(theme_stats.correct, theme_stats.answered)
        if theme_score >= 75:
            band = "sterk"
            strong_themes.append(theme_stats.label)
        elif theme_score >= 50:
            band = "wisselend"
            growth_themes.append(theme_stats.label)
        else:
            band = "aandachtspunt"
            growth_themes.append(theme_stats.label)

        themes_payload.append(
            {
                "key": theme_key,
                "label": theme_stats.label,
                "answered": theme_stats.answered,
                "correct": theme_stats.correct,
                "score_percent": theme_score,
                "band": band,
            }
        )

    mistakes_payload: List[dict] = []
    for mistake in evaluation.mistakes[:3]:
        mistakes_payload.append(
            {
                "theme_label": clean_ai_report_text(mistake.theme_label, max_length=80),
                "question": clean_ai_report_text(mistake.question, max_length=220),
                "chosen_option": clean_ai_report_text(mistake.chosen_option, max_length=180),
                "correct_option": clean_ai_report_text(mistake.correct_option, max_length=180),
                "explanation": clean_ai_report_text(mistake.explanation, max_length=260),
            }
        )

    return {
        "total_answered": evaluation.total_answered,
        "total_correct": evaluation.total_correct,
        "score_percent": score_percent(evaluation.total_correct, evaluation.total_answered),
        "strong_themes": strong_themes,
        "growth_themes": growth_themes,
        "themes": themes_payload,
        "mistakes": mistakes_payload,
    }


def group_evaluation_ai_report_cache_key(payload: dict) -> str:
    serialized = json.dumps(payload, ensure_ascii=False, sort_keys=True)
    return hashlib.sha256(serialized.encode("utf-8")).hexdigest()


def build_ai_group_evaluation_report_rows(
    gs: GameState,
    allow_ai: bool = False,
    allow_server_key: bool = False,
) -> Optional[List[Tuple[str, int, int]]]:
    if not allow_ai:
        return None
    client = get_openai_client(allow_server_key=allow_server_key)
    if client is None or gs.group_evaluation.total_answered <= 0:
        return None

    payload = build_group_evaluation_ai_payload(gs)
    cache_key = group_evaluation_ai_report_cache_key(payload)
    cached_rows = AI_GROUP_EVALUATION_REPORT_CACHE.get(cache_key)
    if cached_rows:
        return list(cached_rows)

    try:
        response = client.chat.completions.create(
            model=EVALUATION_REPORT_MODEL,
            response_format={"type": "json_object"},
            temperature=0.3,
            timeout=12.0,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je schrijft een kort groepsverslag over AI-geletterdheid voor leerlingen van 12 tot 14 jaar. "
                        "Gebruik alleen de feiten uit de invoer. "
                        "Verzin geen cijfers, thema's, fouten, voorbeelden of conclusies die niet in de data staan. "
                        "Schrijf in eenvoudig, vlot Nederlands dat warm en menselijk klinkt, zonder kinderachtig te worden. "
                        "Spreek de groep rechtstreeks aan als 'jullie'. "
                        "Schrijf actief en concreet, niet droog of schools. "
                        "Vermijd stijve formuleringen zoals 'we hebben gekeken hoe goed leerlingen...' of 'er werd vastgesteld dat'. "
                        "Gebruik geen clichés, geen managementtaal en geen lege opvulzinnen. "
                        "Hou elke tekst kort: maximaal 1 tot 3 zinnen per veld. "
                        "Gebruik geen markdown of opsommingstekens. "
                        "Geef alleen JSON terug."
                    ),
                },
                {
                    "role": "user",
                    "content": (
                        "Maak een kort AI-verslag op basis van deze evaluatiegegevens. "
                        "Gebruik de themalabels exact zoals gegeven. "
                        "Laat geen onderdelen weg als er data voor is. "
                        "Laat het verslag klinken alsof een sterke leerkracht het helder en vlot aan een klas uitlegt. "
                        "Gebruik afwisselende zinnen en benoem zo veel mogelijk concrete sterktes en groeipunten uit de data zelf. "
                        "Maak de intro meteen raak en vermijd algemene openers. "
                        "Geef JSON in dit formaat:\n"
                        "{\n"
                        '  "intro": "...",\n'
                        '  "why_it_matters": ["...", "..."],\n'
                        '  "what_went_well": ["..."],\n'
                        '  "attention_points": ["..."],\n'
                        '  "theme_analysis": [{"theme": "...", "summary": "..."}],\n'
                        '  "mistake_lessons": ["..."],\n'
                        '  "closing": "..."\n'
                        "}\n\n"
                        "Evaluatiegegevens:\n"
                        f"{json.dumps(payload, ensure_ascii=False, indent=2)}"
                    ),
                },
            ],
        )
    except Exception as exc:
        print("AI group evaluation report error:", exc)
        return None

    content = clean_ai_report_text(response.choices[0].message.content or "", max_length=10000)
    if not content:
        return None

    try:
        report = json.loads(content)
    except json.JSONDecodeError:
        return None

    intro = clean_ai_report_text(report.get("intro"), max_length=320)
    why_it_matters = clean_ai_report_list(report.get("why_it_matters"), max_items=3, max_length=360)
    what_went_well = clean_ai_report_list(report.get("what_went_well"), max_items=4, max_length=360)
    attention_points = clean_ai_report_list(report.get("attention_points"), max_items=4, max_length=360)
    mistake_lessons = clean_ai_report_list(report.get("mistake_lessons"), max_items=4, max_length=360)
    closing = clean_ai_report_text(report.get("closing"), max_length=320)

    theme_summaries: Dict[str, str] = {}
    for entry in report.get("theme_analysis") if isinstance(report.get("theme_analysis"), list) else []:
        if not isinstance(entry, dict):
            continue
        theme_label = clean_ai_report_text(entry.get("theme"), max_length=80)
        summary = clean_ai_report_text(entry.get("summary"), max_length=360)
        if theme_label and summary:
            theme_summaries[theme_label] = summary

    if not any([intro, why_it_matters, what_went_well, attention_points, theme_summaries, mistake_lessons, closing]):
        return None

    rows: List[Tuple[str, int, int]] = [("Jullie AI-terugblik", 18, 10)]
    if intro:
        rows.append((intro, 11, 8))

    rows.append(("Jullie score in één oogopslag", 14, 6))
    rows.append((
        f"Jullie beantwoordden {payload['total_answered']} AI-vragen. "
        f"Daarvan waren er {payload['total_correct']} juist. "
        f"Dat is {payload['score_percent']}% correct.",
        11,
        7,
    ))

    if payload["strong_themes"]:
        rows.append(("Jullie sterkste thema's waren: " + ", ".join(payload["strong_themes"]) + ".", 11, 7))
    else:
        rows.append(("Er sprong nog geen duidelijk sterk thema uit, maar dat geeft vooral aan waar extra oefenkansen zitten.", 11, 7))

    if payload["growth_themes"]:
        rows.append(("Hier mogen jullie nog scherper op worden: " + ", ".join(payload["growth_themes"]) + ".", 11, 8))
    else:
        rows.append(("Er sprong geen duidelijk aandachtsthema uit, maar blijven oefenen op kritisch kijken blijft belangrijk.", 11, 8))

    if why_it_matters:
        rows.append(("Waarom dit belangrijk is", 14, 6))
        rows.extend((paragraph, 11, 7) for paragraph in why_it_matters)

    if what_went_well:
        rows.append(("Hier stonden jullie al sterk", 14, 6))
        rows.extend((paragraph, 11, 7) for paragraph in what_went_well)

    if attention_points:
        rows.append(("Hier zit nog groeiruimte", 14, 6))
        rows.extend((paragraph, 11, 7) for paragraph in attention_points)

    if theme_summaries:
        rows.append(("Per thema bekeken", 14, 6))
        for theme_entry in payload["themes"]:
            summary = theme_summaries.get(theme_entry["label"])
            if summary:
                rows.append((f"{theme_entry['label']}: {summary}", 11, 9))

    if mistake_lessons or payload["mistakes"]:
        rows.append(("Fouten waar je slimmer van wordt", 14, 6))
        if mistake_lessons:
            rows.extend((paragraph, 11, 7) for paragraph in mistake_lessons)
        else:
            for mistake in payload["mistakes"]:
                detail_parts = []
                if mistake["chosen_option"]:
                    detail_parts.append(f"Jullie kozen: {mistake['chosen_option']}.")
                if mistake["correct_option"]:
                    detail_parts.append(f"Sterker was: {mistake['correct_option']}.")
                if mistake["explanation"]:
                    detail_parts.append(f"Waarom dit telt: {mistake['explanation']}")
                detail = " ".join(detail_parts).strip() or "Gebruik dit foutje als herinnering om AI-antwoorden altijd te controleren."
                rows.append((f"Bij {mistake['theme_label']} liep het mis bij: {mistake['question']} {detail}", 11, 8))

    if closing:
        rows.append(("Wat jullie hieruit meenemen", 14, 6))
        rows.append((closing, 11, 0))
    elif rows:
        last_text, last_size, _last_gap = rows[-1]
        rows[-1] = (last_text, last_size, 0)

    AI_GROUP_EVALUATION_REPORT_CACHE[cache_key] = list(rows)
    return rows


def group_evaluation_report_rows(gs: GameState) -> List[Tuple[str, int, int]]:
    evaluation = gs.group_evaluation
    rows: List[Tuple[str, int, int]] = [
        ("Groepsevaluatie AI-geletterdheid", 18, 10),
        (
            "Deze evaluatie vat samen wat tijdens het spel zichtbaar werd rond kritisch, veilig en verantwoord omgaan met AI.",
            11,
            8,
        ),
    ]

    if evaluation.total_answered <= 0:
        rows.extend([
            ("Er zijn nog geen AI-vragen geregistreerd tijdens dit spel.", 12, 8),
            (
                "Speel eerst enkele vragen uit verschillende thema's. Bespreek telkens waarom een antwoord klopt, waar twijfel zat en welke controle nodig is.",
                11,
                8,
            ),
            (
                "Een goede AI-reflectie gaat niet alleen over juist of fout antwoorden. Het gaat vooral over uitleggen waarom je AI wel of niet vertrouwt.",
                11,
                8,
            ),
        ])
        return rows

    strong_themes: List[str] = []
    growth_themes: List[str] = []

    for theme_key, theme_stats in sorted_group_evaluation_themes(evaluation):
        if theme_stats.answered <= 0:
            continue
        theme_score = score_percent(theme_stats.correct, theme_stats.answered)
        if theme_score >= 75:
            strong_themes.append(theme_stats.label)
        else:
            growth_themes.append(theme_stats.label)

    rows.append(("Algemene duiding", 14, 6))
    rows.append((
        "AI kan heel bruikbaar zijn om uitleg te krijgen, ideeën te ordenen of voorbeelden te zoeken. Toch blijft controle nodig: een AI-antwoord kan overtuigend klinken en toch fout, onvolledig of eenzijdig zijn.",
        11,
        7,
    ))
    rows.append((
        "Verkeerde antwoorden zijn niet onschuldig. Ze kunnen leiden tot foutieve leerstof, misverstanden in een taak, het verspreiden van nepnieuws, oneerlijke beelden over groepen mensen of het delen van persoonlijke informatie.",
        11,
        10,
    ))

    rows.append(("Wat al goed loopt", 14, 6))
    if strong_themes:
        rows.append(("Deze thema's kwamen sterk naar voren: " + ", ".join(strong_themes) + ".", 11, 7))
        rows.append((
            "Ook bij sterke thema's blijft herhaling zinvol. AI verandert snel en leerlingen komen AI vaak tegen buiten de klas, waar er minder begeleiding is.",
            11,
            8,
        ))
    else:
        rows.append((
            "Er kwam nog geen duidelijk sterk thema naar voren. Gebruik dit als startpunt voor een klassikale bespreking: welke stappen helpen om een AI-antwoord betrouwbaar te controleren?",
            11,
            8,
        ))

    rows.append(("Aandachtspunten", 14, 6))
    if growth_themes:
        rows.append(("Bespreek vooral verder: " + ", ".join(growth_themes) + ".", 11, 7))
        rows.append((
            "Een aandachtspunt betekent niet dat de groep dit niet kan. Het betekent dat leerlingen baat hebben bij extra voorbeelden, hardop redeneren en samen controleren.",
            11,
            8,
        ))
    else:
        rows.append((
            "Er sprong geen duidelijk moeilijk thema uit. Blijf wel oefenen op broncontrole, privacy en zelfstandig denken, want net bij vlotte antwoorden is blind vertrouwen een risico.",
            11,
            8,
        ))

    rows.append(("Analyse per thema", 14, 6))
    for theme_key, theme_stats in sorted_group_evaluation_themes(evaluation):
        if theme_stats.answered <= 0:
            continue

        theme_score = score_percent(theme_stats.correct, theme_stats.answered)
        feedback = EVALUATION_THEME_FEEDBACK.get(theme_key, EVALUATION_THEME_FEEDBACK["algemeen"])
        if theme_score >= 75:
            intro = "Sterk thema"
            advice = f"{feedback['background']} {feedback['strength']} {feedback['risk']}"
        elif theme_score >= 50:
            intro = "Wisselend thema"
            advice = f"{feedback['background']} {feedback['growth']} {feedback['risk']}"
        else:
            intro = "Belangrijk aandachtspunt"
            advice = f"{feedback['background']} {feedback['growth']} {feedback['risk']}"

        rows.append((
            f"{intro}: {theme_stats.label}. {advice}",
            11,
            9,
        ))

    rows.append(("Bespreekvragen voor de klas", 14, 6))
    rows.append((
        "Kies een thema dat extra aandacht vraagt. Laat de groep uitleggen hoe ze een AI-antwoord zouden controleren, welke bron ze zouden gebruiken en welke informatie ze beter niet met AI delen.",
        11,
        7,
    ))
    rows.append((
        "Laat leerlingen ook benoemen waar AI mag helpen en waar eigen denken nodig blijft. Zo wordt AI een hulpmiddel, geen vervanging voor begrijpen.",
        11,
        0,
    ))
    return rows


def student_group_evaluation_report_rows(gs: GameState) -> List[Tuple[str, int, int]]:
    evaluation = gs.group_evaluation
    rows: List[Tuple[str, int, int]] = [
        ("Jullie AI-terugblik", 18, 10),
        (
            "Dit verslag helpt jullie zien wat al goed lukt en waar jullie nog extra op moeten letten bij AI.",
            11,
            8,
        ),
    ]

    if evaluation.total_answered <= 0:
        rows.extend([
            ("Er zijn nog geen AI-vragen geregistreerd tijdens dit spel.", 12, 8),
            (
                "Speel eerst enkele vragen uit verschillende thema's. Bespreek daarna samen waarom een antwoord klopt, waar twijfel zat en welke controle nodig is.",
                11,
                8,
            ),
            (
                "Bij AI gaat het niet alleen over juist of fout antwoorden. Het gaat vooral over uitleggen waarom je AI wel of niet vertrouwt.",
                11,
                8,
            ),
        ])
        return rows

    strong_themes: List[str] = []
    growth_themes: List[str] = []

    for theme_key, theme_stats in sorted_group_evaluation_themes(evaluation):
        if theme_stats.answered <= 0:
            continue
        theme_score = score_percent(theme_stats.correct, theme_stats.answered)
        if theme_score >= 75:
            strong_themes.append(theme_stats.label)
        else:
            growth_themes.append(theme_stats.label)

    rows.append(("Waarom dit belangrijk is", 14, 6))
    rows.append((
        "AI kan jullie helpen om uitleg te krijgen, ideeen te ordenen of voorbeelden te zoeken. Toch blijft controle nodig: een AI-antwoord kan overtuigend klinken en toch fout, onvolledig of eenzijdig zijn.",
        11,
        7,
    ))
    rows.append((
        "Verkeerde antwoorden zijn niet onschuldig. Ze kunnen zorgen voor foutieve leerstof, misverstanden in een taak, het verspreiden van nepnieuws, oneerlijke beelden over mensen of het delen van persoonlijke informatie.",
        11,
        10,
    ))

    rows.append(("Wat al goed loopt", 14, 6))
    if strong_themes:
        rows.append(("Hier lieten jullie zien dat jullie al sterk staan: " + ", ".join(strong_themes) + ".", 11, 7))
        rows.append((
            "Dat betekent niet dat jullie hier nooit meer op moeten letten. Net bij thema's die goed gaan, kan een antwoord te snel vanzelfsprekend lijken.",
            11,
            8,
        ))
    else:
        rows.append((
            "Er kwam nog geen duidelijk sterk thema naar voren. Dat is een goed moment om samen te oefenen: welke stappen helpen om een AI-antwoord betrouwbaar te controleren?",
            11,
            8,
        ))

    rows.append(("Waar jullie op moeten letten", 14, 6))
    if growth_themes:
        rows.append(("Deze thema's vragen extra aandacht: " + ", ".join(growth_themes) + ".", 11, 7))
        rows.append((
            "Een aandachtspunt betekent niet dat jullie dit niet kunnen. Het betekent dat jullie baat hebben bij extra voorbeelden, hardop redeneren en samen controleren.",
            11,
            8,
        ))
    else:
        rows.append((
            "Er sprong geen duidelijk moeilijk thema uit. Blijf toch oefenen op broncontrole, privacy en zelfstandig denken, want net bij vlotte antwoorden is blind vertrouwen een risico.",
            11,
            8,
        ))

    rows.append(("Analyse per thema", 14, 6))
    for theme_key, theme_stats in sorted_group_evaluation_themes(evaluation):
        if theme_stats.answered <= 0:
            continue

        theme_score = score_percent(theme_stats.correct, theme_stats.answered)
        feedback = EVALUATION_THEME_FEEDBACK.get(theme_key, EVALUATION_THEME_FEEDBACK["algemeen"])
        if theme_score >= 75:
            intro = "Dit ging goed"
            advice = f"{feedback['background']} {feedback['strength']} {feedback['risk']}"
        elif theme_score >= 50:
            intro = "Dit ging wisselend"
            advice = f"{feedback['background']} {feedback['growth']} {feedback['risk']}"
        else:
            intro = "Hier moeten jullie extra op letten"
            advice = f"{feedback['background']} {feedback['growth']} {feedback['risk']}"

        rows.append((
            f"{intro}: {theme_stats.label}. {advice}",
            11,
            9,
        ))

    rows.append(("Fouten om van te leren", 14, 6))
    if evaluation.mistakes:
        for mistake in evaluation.mistakes[:3]:
            detail_parts = []
            if mistake.chosen_option:
                detail_parts.append(f"Jullie kozen: {mistake.chosen_option}.")
            if mistake.correct_option:
                detail_parts.append(f"Sterker was: {mistake.correct_option}.")
            if mistake.explanation:
                detail_parts.append(f"Waarom dit telt: {mistake.explanation}")

            detail = " ".join(detail_parts).strip()
            if not detail:
                detail = "Gebruik dit foutje als herinnering om AI-antwoorden altijd te controleren."

            rows.append((
                f"Bij {mistake.theme_label} liep het mis bij: {mistake.question} {detail}",
                11,
                8,
            ))
    else:
        rows.append((
            "Er werden geen foute antwoorden geregistreerd. Dat is mooi, maar blijf opletten: AI kan juist lijken door een nette stijl, niet omdat het antwoord automatisch klopt.",
            11,
            8,
        ))

    rows.append(("Wat jullie kunnen meenemen", 14, 6))
    rows.append((
        "Spreek bij een volgend AI-antwoord hardop af: wat willen we controleren, welke bron gebruiken we, welke persoonlijke informatie delen we niet en welk deel moeten we zelf begrijpen?",
        11,
        7,
    ))
    rows.append((
        "AI mag helpen, maar jullie blijven verantwoordelijk voor wat jullie geloven, delen en inleveren. Gebruik AI dus als hulpmiddel, niet als vervanging voor begrijpen.",
        11,
        0,
    ))
    return rows


def pdf_text_literal(text: str) -> bytes:
    escaped = (
        str(text or "")
        .replace("\r", " ")
        .replace("\n", " ")
        .encode("cp1252", "replace")
    )
    escaped = escaped.replace(b"\\", b"\\\\").replace(b"(", b"\\(").replace(b")", b"\\)")
    return b"(" + escaped + b")"


def pdf_number(value: float) -> bytes:
    return f"{value:.2f}".rstrip("0").rstrip(".").encode("ascii")


def pdf_color(color: Tuple[float, float, float]) -> bytes:
    return b" ".join(pdf_number(channel) for channel in color)


def pdf_rect_operation(
    x: float,
    y: float,
    width: float,
    height: float,
    color: Tuple[float, float, float],
    operator: bytes = b"f",
) -> bytes:
    color_operator = b"rg" if operator == b"f" else b"RG"
    return (
        b"q "
        + pdf_color(color)
        + b" "
        + color_operator
        + b" "
        + pdf_number(x)
        + b" "
        + pdf_number(y)
        + b" "
        + pdf_number(width)
        + b" "
        + pdf_number(height)
        + b" re "
        + operator
        + b" Q\n"
    )


def pdf_polygon_operation(points: List[Tuple[float, float]], color: Tuple[float, float, float]) -> bytes:
    if not points:
        return b""

    chunks = [b"q ", pdf_color(color), b" rg "]
    first_x, first_y = points[0]
    chunks.extend([pdf_number(first_x), b" ", pdf_number(first_y), b" m "])

    for point_x, point_y in points[1:]:
        chunks.extend([pdf_number(point_x), b" ", pdf_number(point_y), b" l "])

    chunks.append(b"h f Q\n")
    return b"".join(chunks)


def pdf_regular_polygon_points(
    center_x: float,
    center_y: float,
    radius: float,
    sides: int = 10,
    rotation: float = 0.0,
) -> List[Tuple[float, float]]:
    points: List[Tuple[float, float]] = []
    total_sides = max(3, int(sides))
    for index in range(total_sides):
        angle = rotation + (math.tau * index / total_sides)
        points.append((center_x + math.cos(angle) * radius, center_y + math.sin(angle) * radius))
    return points


def pdf_circle_operation(
    center_x: float,
    center_y: float,
    radius: float,
    color: Tuple[float, float, float],
    sides: int = 12,
) -> bytes:
    return pdf_polygon_operation(
        pdf_regular_polygon_points(center_x, center_y, radius, sides=sides, rotation=math.pi / sides),
        color,
    )


def pdf_cloud_operation(x: float, y: float, scale: float = 1.0) -> bytes:
    cloud = (0.95, 0.97, 0.99)
    ops = [
        pdf_circle_operation(x, y, 12 * scale, cloud),
        pdf_circle_operation(x + 12 * scale, y + 7 * scale, 16 * scale, cloud),
        pdf_circle_operation(x + 29 * scale, y + 4 * scale, 14 * scale, cloud),
        pdf_circle_operation(x + 42 * scale, y + 8 * scale, 12 * scale, cloud),
        pdf_rect_operation(x - 6 * scale, y - 10 * scale, 56 * scale, 18 * scale, cloud),
    ]
    return b"".join(ops)


def pdf_crate_operation(x: float, y: float, scale: float = 1.0) -> bytes:
    width = 24 * scale
    height = 20 * scale
    crate = (0.78, 0.23, 0.11)
    lid = (0.60, 0.15, 0.08)
    wood = (0.40, 0.20, 0.10)
    ops = [
        pdf_rect_operation(x, y, width, height, crate),
        pdf_rect_operation(x + 2 * scale, y + height - 5 * scale, width - 4 * scale, 3 * scale, lid),
        pdf_rect_operation(x + 4 * scale, y + 3 * scale, width - 8 * scale, 2 * scale, wood),
        pdf_rect_operation(x + width * 0.5 - scale, y + 3 * scale, 2 * scale, height - 6 * scale, wood),
    ]
    return b"".join(ops)


def pdf_ladder_operation(x: float, y: float, scale: float = 1.0) -> bytes:
    wood = (0.72, 0.51, 0.16)
    dark = (0.47, 0.31, 0.11)
    height = 38 * scale
    width = 18 * scale
    ops = [
        pdf_rect_operation(x, y, 3 * scale, height, dark),
        pdf_rect_operation(x + width, y, 3 * scale, height, dark),
    ]
    for rung in range(4):
        rung_y = y + (6 + rung * 9) * scale
        ops.append(pdf_rect_operation(x + 2 * scale, rung_y, width, 2.5 * scale, wood))
    return b"".join(ops)


def pdf_worker_operation(x: float, y: float, scale: float = 1.0, facing: int = 1) -> bytes:
    body = (0.15, 0.40, 0.82)
    shirt = (0.20, 0.52, 0.93)
    skin = (0.97, 0.81, 0.63)
    helmet = (0.98, 0.74, 0.16)
    boots = (0.25, 0.16, 0.10)
    belt = (0.33, 0.19, 0.10)
    tool = (0.33, 0.24, 0.18)
    shadow = (0.71, 0.61, 0.48)
    sign = 1 if facing >= 0 else -1
    ops = [pdf_circle_operation(x + 9 * scale, y + 2 * scale, 9 * scale, shadow, 10)]

    ops.extend([
        pdf_rect_operation(x + 6 * scale, y + 8 * scale, 5 * scale, 14 * scale, body),
        pdf_rect_operation(x + 12 * scale, y + 8 * scale, 5 * scale, 14 * scale, body),
        pdf_rect_operation(x + 4 * scale, y + 22 * scale, 15 * scale, 14 * scale, shirt),
        pdf_rect_operation(x + 5 * scale, y + 20 * scale, 13 * scale, 3 * scale, belt),
        pdf_rect_operation(x + 5 * scale, y + 6 * scale, 6 * scale, 4 * scale, boots),
        pdf_rect_operation(x + 12 * scale, y + 6 * scale, 6 * scale, 4 * scale, boots),
        pdf_circle_operation(x + 11 * scale, y + 43 * scale, 7 * scale, skin, 12),
        pdf_rect_operation(x + 4 * scale, y + 46 * scale, 14 * scale, 3 * scale, helmet),
        pdf_circle_operation(x + 11 * scale, y + 48 * scale, 8 * scale, helmet, 10),
        pdf_rect_operation(x + (18 if sign > 0 else 0) * scale, y + 24 * scale, 6 * scale, 4 * scale, shirt),
        pdf_rect_operation(x + (sign > 0 and 23 or -5) * scale, y + 24 * scale, 10 * scale, 2 * scale, tool),
    ])

    return b"".join(ops)


def pdf_excavator_operation(x: float, y: float, scale: float = 1.0) -> bytes:
    blue = (0.12, 0.47, 0.82)
    yellow = (0.96, 0.75, 0.14)
    dark = (0.20, 0.18, 0.18)
    ops = [
        pdf_rect_operation(x + 10 * scale, y + 10 * scale, 34 * scale, 16 * scale, blue),
        pdf_rect_operation(x + 16 * scale, y + 16 * scale, 14 * scale, 10 * scale, yellow),
        pdf_rect_operation(x + 28 * scale, y + 10 * scale, 16 * scale, 18 * scale, yellow),
        pdf_circle_operation(x + 18 * scale, y + 8 * scale, 6 * scale, dark),
        pdf_circle_operation(x + 40 * scale, y + 8 * scale, 6 * scale, dark),
        pdf_rect_operation(x + 48 * scale, y + 26 * scale, 16 * scale, 4 * scale, yellow),
        pdf_rect_operation(x + 60 * scale, y + 22 * scale, 4 * scale, 10 * scale, yellow),
        pdf_polygon_operation(
            [(x + 63 * scale, y + 20 * scale), (x + 74 * scale, y + 16 * scale), (x + 67 * scale, y + 10 * scale)],
            yellow,
        ),
    ]
    return b"".join(ops)


def load_pdf_background_image(path: Path) -> Optional[dict]:
    if Image is None or not path.exists():
        return None

    try:
        with Image.open(path) as image:
            rgb_image = image.convert("RGB")
            buffer = io.BytesIO()
            rgb_image.save(buffer, format="JPEG", quality=88, optimize=True)
            return {
                "width": rgb_image.width,
                "height": rgb_image.height,
                "data": buffer.getvalue(),
            }
    except Exception:
        return None


def pdf_image_xobject(image: dict) -> bytes:
    image_stream = image["data"]
    return (
        b"<< /Type /XObject /Subtype /Image /Width "
        + str(image["width"]).encode("ascii")
        + b" /Height "
        + str(image["height"]).encode("ascii")
        + b" /ColorSpace /DeviceRGB /BitsPerComponent 8 /Filter /DCTDecode /Length "
        + str(len(image_stream)).encode("ascii")
        + b" >>\nstream\n"
        + image_stream
        + b"\nendstream"
    )


def pdf_image_draw_operation(name: str, x: float, y: float, width: float, height: float) -> bytes:
    return (
        b"q "
        + pdf_number(width)
        + b" 0 0 "
        + pdf_number(height)
        + b" "
        + pdf_number(x)
        + b" "
        + pdf_number(y)
        + b" cm /"
        + name.encode("ascii")
        + b" Do Q\n"
    )


def pdf_stone_operation(
    center_x: float,
    center_y: float,
    width: float,
    height: float,
    color: Tuple[float, float, float],
    angle: float = 0.0,
) -> bytes:
    base_points = [
        (-0.48, -0.12),
        (-0.28, 0.40),
        (0.12, 0.48),
        (0.48, 0.20),
        (0.38, -0.36),
        (-0.08, -0.50),
    ]
    cosine = math.cos(angle)
    sine = math.sin(angle)
    points: List[Tuple[float, float]] = []

    for point_x, point_y in base_points:
        scaled_x = point_x * width
        scaled_y = point_y * height
        rotated_x = scaled_x * cosine - scaled_y * sine
        rotated_y = scaled_x * sine + scaled_y * cosine
        points.append((center_x + rotated_x, center_y + rotated_y))

    return pdf_polygon_operation(points, color)


def pdf_board_edge_background(page_width: int, page_height: int, page_index: int) -> bytes:
    rng = random.Random(4317 + page_index)
    operations: List[bytes] = []
    rock_palette = [
        (0.47, 0.39, 0.30),
        (0.56, 0.48, 0.37),
        (0.64, 0.56, 0.43),
        (0.39, 0.33, 0.27),
        (0.74, 0.66, 0.53),
    ]
    sky = (0.66, 0.82, 0.98)
    horizon = (0.80, 0.73, 0.60)
    sand = (0.93, 0.87, 0.76)
    inner_paper = (0.97, 0.92, 0.84)
    inner_shadow = (0.90, 0.84, 0.73)
    border_edge = (0.40, 0.32, 0.24)

    operations.append(pdf_rect_operation(0, 0, page_width, page_height, sand))
    operations.append(pdf_rect_operation(0, page_height - 78, page_width, 78, sky))
    operations.append(pdf_rect_operation(0, page_height - 112, page_width, 34, horizon))

    border_zones = [
        (0, 0, 74, page_height),
        (page_width - 74, 0, 74, page_height),
        (0, page_height - 118, page_width, 118),
        (0, 0, page_width, 88),
    ]

    for _ in range(220):
        zone_x, zone_y, zone_w, zone_h = rng.choice(border_zones)
        stone_x = zone_x + rng.random() * zone_w
        stone_y = zone_y + rng.random() * zone_h
        stone_w = rng.uniform(12, 30)
        stone_h = rng.uniform(9, 24)
        color = rng.choice(rock_palette)
        operations.append(pdf_stone_operation(stone_x, stone_y, stone_w, stone_h, color, rng.uniform(0, math.pi)))

    for cloud_x, cloud_y, cloud_scale in (
        (44, page_height - 30, 0.9),
        (138, page_height - 24, 0.7),
        (246, page_height - 28, 0.85),
        (370, page_height - 22, 0.95),
        (480, page_height - 30, 0.75),
    ):
        operations.append(pdf_cloud_operation(cloud_x, cloud_y, cloud_scale))

    cone = (0.92, 0.46, 0.14)
    for cone_x in (118, 178, 238, 462, 522):
        operations.append(pdf_polygon_operation([(cone_x - 9, 34), (cone_x, 62), (cone_x + 9, 34)], cone))
        operations.append(pdf_rect_operation(cone_x - 12, 30, 24, 5, (0.95, 0.90, 0.80)))

    for crate_x, crate_y, crate_scale in (
        (144, page_height - 66, 1.05),
        (188, page_height - 72, 0.9),
        (336, page_height - 62, 1.0),
        (34, 150, 1.0),
        (page_width - 66, 214, 1.05),
        (page_width - 58, 112, 0.95),
    ):
        operations.append(pdf_crate_operation(crate_x, crate_y, crate_scale))

    operations.append(pdf_ladder_operation(68, page_height - 74, 1.15))
    operations.append(pdf_ladder_operation(34, 346, 1.1))
    operations.append(pdf_excavator_operation(page_width - 190, 24, 1.2))

    for worker_x, worker_y, worker_scale, facing in (
        (16, page_height - 84, 0.92, 1),
        (108, page_height - 80, 0.90, 1),
        (206, page_height - 82, 0.88, 1),
        (316, page_height - 80, 0.88, -1),
        (452, page_height - 82, 0.92, -1),
        (14, 540, 0.95, 1),
        (18, 432, 0.95, -1),
        (22, 248, 0.95, 1),
        (page_width - 44, 580, 0.95, -1),
        (page_width - 42, 486, 0.95, -1),
        (page_width - 40, 176, 0.95, -1),
        (page_width - 120, 10, 0.95, 1),
    ):
        operations.append(pdf_worker_operation(worker_x, worker_y, worker_scale, facing))

    inner_x = 76
    inner_y = 84
    inner_width = page_width - inner_x * 2
    inner_height = page_height - 184
    operations.append(pdf_rect_operation(inner_x, inner_y, inner_width, inner_height, inner_shadow))
    operations.append(pdf_rect_operation(inner_x + 8, inner_y + 8, inner_width - 16, inner_height - 16, inner_paper))
    operations.append(pdf_rect_operation(inner_x, inner_y, inner_width, inner_height, border_edge, b"S"))

    return b"".join(operations)


def build_text_pdf(rows: List[Tuple[str, int, int]]) -> bytes:
    page_width = 595
    page_height = 842
    margin_x = 84
    top_y = 718
    bottom_y = 100
    inner_right_x = page_width - margin_x
    pages: List[bytes] = []
    operations: List[bytes] = []
    y = top_y
    current_page_index = 0

    aico_image = load_pdf_background_image(AICO_REPORT_IMAGE_FILE)
    aico_layout: Optional[dict] = None
    if aico_image is not None:
        max_width = 148.0
        max_height = 196.0
        scale = min(
            max_width / max(1, aico_image["width"]),
            max_height / max(1, aico_image["height"]),
        )
        draw_width = max(1.0, aico_image["width"] * scale)
        draw_height = max(1.0, aico_image["height"] * scale)
        top = top_y + 6
        draw_y = top - draw_height
        draw_x = inner_right_x - draw_width + 4
        aico_layout = {
            "x": draw_x,
            "y": draw_y,
            "width": draw_width,
            "height": draw_height,
            "top": top,
            "bottom": draw_y,
        }

    def flush_page() -> None:
        nonlocal operations, y, current_page_index
        if operations:
            pages.append(b"".join(operations))
            operations = []
            current_page_index += 1
        y = top_y

    for text, font_size, gap_after in rows:
        wrap_width = 54 if font_size >= 14 else 72
        if (
            aico_layout is not None
            and current_page_index == 0
            and y >= aico_layout["bottom"] - 4
        ):
            wrap_width = 42 if font_size >= 14 else 50
        wrapped_lines = textwrap.wrap(
            str(text or ""),
            width=wrap_width,
            break_long_words=False,
            replace_whitespace=True,
        ) or [""]
        line_height = max(13, int(font_size * 1.45))

        for line in wrapped_lines:
            if y < bottom_y:
                flush_page()

            text_color = (0.31, 0.19, 0.11) if font_size >= 14 else (0.17, 0.14, 0.10)
            operations.append(
                b"q "
                + pdf_color(text_color)
                + b" rg BT /F1 "
                + str(font_size).encode("ascii")
                + b" Tf "
                + str(margin_x).encode("ascii")
                + b" "
                + str(y).encode("ascii")
                + b" Td "
                + pdf_text_literal(line)
                + b" Tj ET Q\n"
            )
            y -= line_height

        y -= gap_after

    flush_page()
    if not pages:
        pages.append(b"")

    background_image = load_pdf_background_image(GROUP_EVALUATION_BACKGROUND_FILE)
    objects: List[Optional[bytes]] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    page_ids: List[int] = []

    background_object_id: Optional[int] = None
    if background_image is not None:
        background_object_id = len(objects) + 1
        objects.append(pdf_image_xobject(background_image))

    aico_object_id: Optional[int] = None
    if aico_image is not None:
        aico_object_id = len(objects) + 1
        objects.append(pdf_image_xobject(aico_image))

    for page_index, stream in enumerate(pages):
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        xobject_parts: List[str] = []
        page_prefix = b""
        if background_object_id is not None:
            page_prefix += pdf_image_draw_operation("BG", 0, 0, page_width, page_height)
            xobject_parts.append(f"/BG {background_object_id} 0 R")
        else:
            page_prefix += pdf_board_edge_background(page_width, page_height, page_index)

        if page_index == 0 and aico_object_id is not None and aico_layout is not None:
            page_prefix += pdf_image_draw_operation(
                "AICO",
                aico_layout["x"],
                aico_layout["y"],
                aico_layout["width"],
                aico_layout["height"],
            )
            xobject_parts.append(f"/AICO {aico_object_id} 0 R")

        stream = page_prefix + stream

        page_resources = "/Font << /F1 3 0 R >>"
        if xobject_parts:
            page_resources += " /XObject << " + " ".join(xobject_parts) + " >>"

        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << {page_resources} >> /Contents {content_id} 0 R >>"
            ).encode("ascii")
        )
        objects.append(
            b"<< /Length " + str(len(stream)).encode("ascii") + b" >>\nstream\n" + stream + b"endstream"
        )

    kids = " ".join(f"{page_id} 0 R" for page_id in page_ids)
    objects[1] = f"<< /Type /Pages /Kids [{kids}] /Count {len(page_ids)} >>".encode("ascii")

    pdf = b"%PDF-1.4\n%\xe2\xe3\xcf\xd3\n"
    offsets = [0]

    for object_index, obj in enumerate(objects, start=1):
        assert obj is not None
        offsets.append(len(pdf))
        pdf += f"{object_index} 0 obj\n".encode("ascii") + obj + b"\nendobj\n"

    xref_offset = len(pdf)
    pdf += f"xref\n0 {len(objects) + 1}\n".encode("ascii")
    pdf += b"0000000000 65535 f \n"
    for offset in offsets[1:]:
        pdf += f"{offset:010d} 00000 n \n".encode("ascii")
    pdf += (
        b"trailer\n"
        + f"<< /Size {len(objects) + 1} /Root 1 0 R >>\n".encode("ascii")
        + b"startxref\n"
        + str(xref_offset).encode("ascii")
        + b"\n%%EOF\n"
    )
    return pdf


def build_group_evaluation_pdf(gs: GameState, allow_ai: bool = False, allow_server_key: bool = False) -> bytes:
    rows = build_ai_group_evaluation_report_rows(
        gs,
        allow_ai=allow_ai,
        allow_server_key=allow_server_key,
    ) or student_group_evaluation_report_rows(gs)
    return build_text_pdf(rows)

def _choose_start_coords(names: List[str], min_dist: int, seed: Optional[int]) -> List[Coord]:
    rng = random.Random(seed)
    coords = all_coords()
    rng.shuffle(coords)

    chosen: List[Coord] = []
    for _name in names:
        # pick first coord far enough from all chosen (soft)
        pick = None
        for c in coords:
            if all(manhattan(c, x) >= min_dist for x in chosen):
                pick = c
                break
        if pick is None:
            # fallback: just pick any unused
            pick = next(c for c in coords if c not in chosen)
        chosen.append(pick)
    return chosen

def _choose_exit_coord(gs: GameState) -> Coord:
    occupied = gs.occupied_coords(include_start_coords=True)
    # optional: keep it away from starts a bit
    starts = [p.start_coord for p in gs.players]
    candidates = [c for c in all_coords() if c not in occupied]
    # prefer those at least 6 away from all starts if possible
    far = [c for c in candidates if all(manhattan(c, s) >= 6 for s in starts)]
    if far:
        return random.choice(far)
    return random.choice(candidates)

def _reveal_exit(gs: GameState, reason: str) -> None:
    if gs.exit_known:
        return
    gs.exit_coord = _choose_exit_coord(gs)
    gs.exit_known = True
    _log(gs, f"Uitgang onthuld ({reason}) op {gs.exit_coord}.")


def _shift_timer_value(value: Optional[float], delta_seconds: float) -> Optional[float]:
    if value is None:
        return None
    return value + delta_seconds


def _pause_game_clock(
    gs: GameState,
    reason: str = "manual",
    paused_at: Optional[float] = None,
) -> None:
    normalized_reason = str(reason or "manual").strip().lower() or "manual"
    if normalized_reason in gs.pause_reasons:
        return

    if not gs.pause_reasons:
        gs.timer_paused = True
        gs.paused_at = paused_at or time.time()

    gs.pause_reasons.append(normalized_reason)


def _resume_game_clock(
    gs: GameState,
    reason: str = "manual",
    resumed_at: Optional[float] = None,
) -> float:
    normalized_reason = str(reason or "manual").strip().lower() or "manual"
    if normalized_reason not in gs.pause_reasons:
        return 0.0

    gs.pause_reasons = [item for item in gs.pause_reasons if item != normalized_reason]
    if gs.pause_reasons:
        return 0.0

    if not gs.timer_paused or gs.paused_at is None:
        gs.timer_paused = False
        gs.paused_at = None
        return 0.0

    resume_time = resumed_at or time.time()
    pause_duration = max(0.0, resume_time - gs.paused_at)

    gs.deadline_at = _shift_timer_value(gs.deadline_at, pause_duration)
    gs.auto_exit_reveal_at = _shift_timer_value(gs.auto_exit_reveal_at, pause_duration)
    gs.next_diamond_spawn_at = _shift_timer_value(gs.next_diamond_spawn_at, pause_duration)
    gs.next_dynamite_spawn_at = _shift_timer_value(gs.next_dynamite_spawn_at, pause_duration)
    gs.timer_paused = False
    gs.paused_at = None
    gs.pause_reasons = []

    return pause_duration

def _explode(gs: GameState, reason: str) -> None:
    if gs.phase in ("exploded", "finished"):
        return
    gs.phase = "exploded"
    _log(gs, f"Explosie! ({reason})")
    _log(gs, "Wie nog binnen is, verliest het spel.")
    # Determine winner among escaped players: most info_cards, tie-breaker earliest escaped_at
    escaped = [p for p in gs.players if p.escaped]
    if not escaped:
        _log(gs, "Niemand is ontsnapt. Iedereen verliest.")
        gs.phase = "finished"
        _record_all_time_ranking_result(gs)
        return
    escaped.sort(key=lambda p: (-p.info_cards, p.escaped_at or 10**18))
    winner = escaped[0]
    _log(gs, f"Winnaar: {winner.name} (diamanten: {winner.info_cards}).")
    gs.phase = "finished"
    _record_all_time_ranking_result(gs)


def _finish_immediately_if_all_players_escaped(gs: GameState) -> bool:
    if not gs.players or not all(player.escaped for player in gs.players):
        return False
    if gs.phase not in ("running", "endgame"):
        return False

    now = time.time()
    gs.deadline_at = now
    gs.timer_paused = False
    gs.paused_at = None
    gs.pause_reasons = []
    _log(gs, "Alle spelers zijn buiten. De teller springt naar 0 en de mijn ontploft meteen.")
    _explode(gs, reason="alle spelers ontsnapt")
    return True


def _schedule_next_spawn(kind: Literal["diamond", "dynamite"], now: Optional[float] = None) -> float:
    base_time = now if now is not None else time.time()
    min_key = f"{kind}_spawn_min_seconds"
    max_key = f"{kind}_spawn_max_seconds"
    return base_time + random.randint(CONFIG[min_key], CONFIG[max_key])


def _choose_dynamite_hole_block(
    gs: GameState,
    anchor_coord: Coord,
    reserved: Optional[set[str]] = None,
) -> List[Coord]:
    reserved_coords = set(reserved or set())
    protected = {player.start_coord for player in gs.players}
    if gs.exit_known and gs.exit_coord:
        protected.add(gs.exit_coord)

    candidates = two_by_two_block_candidates(anchor_coord)
    if not candidates:
        return [anchor_coord]

    def score(block: List[Coord]) -> Tuple[int, int, int, int]:
        block_set = set(block)
        protected_hits = len(block_set & protected)
        reserved_hits = len(block_set & reserved_coords)
        existing_hits = len(block_set & set(gs.destroyed_tiles))
        shift_cost = 0 if block[0] == anchor_coord else 1
        return (protected_hits, reserved_hits, existing_hits, shift_cost)

    return min(candidates, key=score)


def _trigger_dynamite_chain_blast(gs: GameState) -> bool:
    board_dynamite = [item for item in gs.items if item.kind == "dynamite"]
    player_dynamite_total = sum(max(0, int(player.dynamite or 0)) for player in gs.players)

    if not board_dynamite and player_dynamite_total <= 0:
        gs.distributed_dynamite_count = 0
        return False

    destroyed_blocks: List[List[Coord]] = []
    reserved_coords: set[str] = set()

    for item in board_dynamite:
        block = _choose_dynamite_hole_block(gs, item.coord, reserved_coords)
        destroyed_blocks.append(block)
        reserved_coords.update(block)
        for coord in block:
            if coord not in gs.destroyed_tiles:
                gs.destroyed_tiles.append(coord)

    blast_coords = {coord for block in destroyed_blocks for coord in block}
    removed_non_dynamite_items = [
        item for item in gs.items
        if item.kind != "dynamite" and item.coord in blast_coords
    ]
    gs.items = [
        item for item in gs.items
        if item.kind != "dynamite" and item.coord not in blast_coords
    ]

    affected_players: List[str] = []
    for player in gs.players:
        if player.dynamite <= 0:
            continue
        affected_players.append(f"{player.name} ({player.dynamite})")
        player.dynamite = 0

    board_count = len(board_dynamite)
    player_count = player_dynamite_total
    hole_count = len(destroyed_blocks)

    summary_parts = []
    if board_count:
        if board_count == 1:
            summary_parts.append("1 dynamietstaaf op het bord ontploft")
        else:
            summary_parts.append(f"{board_count} dynamietstaven op het bord ontploffen")
    if player_count:
        if player_count == 1:
            summary_parts.append("1 dynamietstaaf bij een speler moet terug naar de voorraad")
        else:
            summary_parts.append(f"{player_count} dynamietstaven bij spelers moeten terug naar de voorraad")
    if hole_count:
        if hole_count == 1:
            summary_parts.append("1 holte van 2 op 2 verschijnt")
        else:
            summary_parts.append(f"{hole_count} holtes van 2 op 2 verschijnen")

    summary = ". ".join(summary_parts).strip()
    if summary:
        summary += "."
    else:
        summary = "Alle dynamiet ontploft tegelijk."

    gs.last_dynamite_blast_id += 1
    gs.last_dynamite_blast_blocks = destroyed_blocks
    gs.last_dynamite_blast_board_count = board_count
    gs.last_dynamite_blast_player_count = player_count
    gs.last_dynamite_blast_summary = summary
    gs.distributed_dynamite_count = 0

    _log(gs, f"DYNAMIETKETTING: {summary}")
    for index, block in enumerate(destroyed_blocks, start=1):
        _log(gs, f"Holte {index}: {', '.join(block)}.")
    if affected_players:
        _log(gs, "Dynamiet terug van spelers: " + ", ".join(affected_players) + ".")
    if removed_non_dynamite_items:
        removed_labels = ", ".join(
            f"{'diamant' if item.kind == 'diamond' else item.kind} op {item.coord}"
            for item in removed_non_dynamite_items
        )
        _log(gs, "Door de holtes verdwijnen ook: " + removed_labels + ".")
    return True


def _register_distributed_dynamite(gs: GameState) -> bool:
    gs.distributed_dynamite_count += 1
    if not should_trigger_random_dynamite_blast(gs.distributed_dynamite_count):
        return False
    return _trigger_dynamite_chain_blast(gs)


def _spawn_random_item(gs: GameState, kind: Literal["diamond", "dynamite"], max_simultaneous: int, now: float) -> bool:
    existing = [it for it in gs.items if it.kind == kind]
    if len(existing) >= max_simultaneous:
        return False

    coord = random_empty_coord(gs.occupied_coords(include_start_coords=True))
    gs.items.append(SpawnItem(kind=kind, coord=coord, spawned_at=now))

    label = "Diamant" if kind == "diamond" else "Dynamiet"
    _log(gs, f"ALARM: {label} leggen op {coord}.")
    if kind == "dynamite":
        _register_distributed_dynamite(gs)
    return True


def _seed_initial_board_items(
    gs: GameState,
    *,
    diamond_count: int = 6,
    dynamite_count: int = 4,
    now: Optional[float] = None,
) -> None:
    spawned_at = now if now is not None else time.time()
    occupied = gs.occupied_coords(include_start_coords=True)
    seeded: Dict[str, List[Coord]] = {"diamond": [], "dynamite": []}

    for kind, count in (("diamond", diamond_count), ("dynamite", dynamite_count)):
        for _ in range(max(0, count)):
            coord = random_empty_coord(occupied)
            occupied.add(coord)
            gs.items.append(SpawnItem(kind=kind, coord=coord, spawned_at=spawned_at))
            seeded[kind].append(coord)

    if seeded["diamond"]:
        _log(gs, "Startverdeling diamanten: " + ", ".join(seeded["diamond"]) + ".")
    if seeded["dynamite"]:
        _log(gs, "Startverdeling dynamiet: " + ", ".join(seeded["dynamite"]) + ".")


# ----------------------------
# Background loop
# ----------------------------

def preload_runtime_caches() -> None:
    load_core_questions()
    load_image_questions()
    load_consensus_dilemmas()
    load_disabled_consensus_ids()
    load_all_time_ranking()


async def ensure_ai_image_pool_background(allow_ai: bool = False, allow_server_key: bool = False) -> int:
    if not allow_ai:
        return 0
    if get_openai_client(allow_server_key=allow_server_key) is None:
        return 0
    if AI_IMAGE_POOL_LOCK.locked():
        return 0

    async with AI_IMAGE_POOL_LOCK:
        try:
            return await asyncio.to_thread(seed_ai_image_question_pool_if_needed, allow_server_key)
        except Exception as exc:
            print("AI image pool seed error:", exc)
            return 0


@app.on_event("startup")
async def startup_loop():
    preload_runtime_caches()
    asyncio.create_task(game_loop())

async def game_loop():
    while True:
        await asyncio.sleep(0.5)
        async with STATE_LOCK:
            now = time.time()
            prune_game_sessions(now)

            for gs in list(GAME_SESSIONS.values()):
                if gs.phase not in ("running", "endgame"):
                    continue

                if gs.timer_paused:
                    continue

                # Auto reveal exit at configured time if not revealed
                if gs.started_at and not gs.exit_known and gs.auto_exit_reveal_at and now >= gs.auto_exit_reveal_at:
                    _reveal_exit(gs, reason="automatisch (25 minuten)")

                if gs.next_diamond_spawn_at and now >= gs.next_diamond_spawn_at:
                    _spawn_random_item(
                        gs,
                        kind="diamond",
                        max_simultaneous=CONFIG["diamond_max_simultaneous"],
                        now=now,
                    )
                    gs.next_diamond_spawn_at = _schedule_next_spawn("diamond", now)

                if gs.next_dynamite_spawn_at and now >= gs.next_dynamite_spawn_at:
                    _spawn_random_item(
                        gs,
                        kind="dynamite",
                        max_simultaneous=CONFIG["dynamite_max_simultaneous"],
                        now=now,
                    )
                    gs.next_dynamite_spawn_at = _schedule_next_spawn("dynamite", now)

                # Explosion check
                if gs.deadline_at and now >= gs.deadline_at:
                    _explode(gs, reason="timer")


# ----------------------------
# API Endpoints
# ----------------------------

@app.post("/api/new", response_model=ActionResponse)
async def new_game(req: NewGameRequest, x_game_session: Optional[str] = Header(None)):
    global CONFIG
    session_id = normalize_game_session_id(x_game_session)
    if req.seed is not None:
        random.seed(req.seed)

    game_id = f"SG-{int(time.time())}"
    start_coords = _choose_start_coords(req.player_names, req.min_start_distance, req.seed)

    players = []
    for i, name in enumerate(req.player_names):
        players.append(Player(
            id=f"p{i+1}",
            name=name.strip() or f"Speler {i+1}",
            start_coord=start_coords[i],
        ))

    now = time.time()
    active_question_mode = normalize_question_difficulty_mode(QUESTION_DIFFICULTY_MODE)
    gs = GameState(
        game_id=game_id,
        phase="running",
        question_difficulty_mode=active_question_mode,
        started_at=now,
        deadline_at=now + req.timer_minutes * 60,
        auto_exit_reveal_at=now + req.auto_exit_reveal_minute * 60,
        next_diamond_spawn_at=_schedule_next_spawn("diamond", now),
        next_dynamite_spawn_at=_schedule_next_spawn("dynamite", now),
        players=players,
        turn_index=0,
        all_time_ranking=load_all_time_ranking(),
    )
    reset_questions()
    CONFIG = {
        "timer_minutes": req.timer_minutes,
        "auto_exit_reveal_minute": req.auto_exit_reveal_minute,
        "emergency_endgame_minutes": req.emergency_endgame_minutes,
        **DEFAULT_RANDOM_SPAWN_CONFIG,
    }

    _log(
        gs,
        f"Nieuw spel gestart met {len(players)} spelers. Timer: {req.timer_minutes} min. "
        f"Vraagniveau: {question_difficulty_mode_label(active_question_mode)}."
    )
    _seed_initial_board_items(gs, diamond_count=6, dynamite_count=4, now=now)
    for p in players:
        _log(gs, f"Startcoordinaat {p.name}: {p.start_coord}")

    async with STATE_LOCK:
        set_game_state(session_id, gs)

    return ActionResponse(
        ok=True,
        message=(
            "Spel gestart. Vraagniveau: "
            + question_difficulty_mode_label(active_question_mode)
            + "."
        ),
        state=gs,
    )

@app.post("/api/question/next")
async def next_question(
    payload: dict,
    x_game_session: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
):
    session_id = normalize_game_session_id(x_game_session)
    theme_key = normalize_theme_key(payload.get("theme"))

    if theme_key not in THEMES:
        raise HTTPException(400, "Ongeldig thema.")

    selected_question = None
    if theme_key == "beeld":
        available_image_questions = load_round_image_questions(include_used=False)
        if available_image_questions:
            selected_question = choose_image_round_question(available_image_questions)
    else:
        async with STATE_LOCK:
            gs = get_game_state(session_id)
        if (
            theme_key == "kansen"
            and random.random() < PROMPT_IMPROVEMENT_CHANCE
            and get_openai_client(allow_server_key=has_valid_ai_owner_password(x_ai_owner_password)) is not None
        ):
            return build_prompt_improvement_payload()
        core_questions = rebalance_ai_question_answer_positions()
        selected_question = choose_core_question_for_mode(
            core_questions,
            theme_key,
            current_question_difficulty_mode(gs),
        )

    if selected_question:
        return build_question_payload(selected_question, theme_key)

    return {"message": "Geen beschikbare vragen meer voor dit thema."}
@app.post("/api/question/generate")
async def generate_ai_question(
    theme: str,
    x_teacher_password: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)

    theme = normalize_theme_key(theme)

    if theme not in THEMES:
        raise HTTPException(400, "Ongeldig thema.")
    if theme == "beeld":
        raise HTTPException(
            400,
            "De beeldronde gebruikt alleen beeldvragen. Gebruik de automatische beeldmix of voeg handmatig een beeldvraag toe.",
        )

    client = get_openai_client(allow_server_key=has_valid_ai_owner_password(x_ai_owner_password))
    if client is None:
        raise HTTPException(500, openai_unavailable_message())

    try:
        questions = prune_duplicate_pending_ai_questions()
        rejected_variants: List[str] = []
        duplicate_match: Optional[dict] = None
        last_quality_feedback: List[str] = []
        target_difficulty = choose_generation_difficulty(theme, questions)

        for _attempt in range(AI_GENERATION_MAX_ATTEMPTS):
            avoid_list = build_generation_avoid_list(questions, theme, rejected_variants)
            duplicate_instruction = ""
            if avoid_list:
                duplicate_instruction = (
                    "Maak GEEN vraag die inhoudelijk hetzelfde is als of sterk lijkt op een van deze bestaande of afgekeurde vragen:\n"
                    f"{avoid_list}\n\n"
                    "Kies dus bewust een andere invalshoek, situatie of redenering.\n\n"
                )

            quality_instruction = ""
            if last_quality_feedback:
                quality_instruction = (
                    "Verbeter deze zwakke punten uit je vorige poging:\n"
                    + "\n".join(f"- {feedback}" for feedback in last_quality_feedback)
                    + "\n\n"
                )

            resp = client.chat.completions.create(
                model=QUESTION_GENERATION_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": SYSTEM_PROMPT
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Thema: {THEMES[theme]['label']}\n\n"
                            f"Mik op deze moeilijkheidsgraad: {QUESTION_DIFFICULTIES[target_difficulty]['label']}\n"
                            f"Richtlijn voor dit niveau: {QUESTION_DIFFICULTY_GENERATION_GUIDANCE[target_difficulty]}\n\n"
                            f"Extra richtlijnen voor dit thema:\n{THEME_GENERATION_GUIDANCE[theme]}\n\n"
                            f"{duplicate_instruction}"
                            f"{quality_instruction}"
                            "Maak 1 korte, concrete meerkeuzevraag die leerlingen echt laat nadenken over AI-geletterdheid. "
                            "Laat de vraag aansluiten bij een herkenbare leerlingensituatie. "
                            "Gebruik gewone taal, maar maak de vraag niet flauw of te simplistisch. "
                            "Zorg dat de 3 foute opties inhoudelijk dicht bij het juiste antwoord liggen: ze moeten plausibel of gedeeltelijk logisch klinken, "
                            "maar net om een subtiele reden fout zijn. "
                            "Laat het juiste antwoord niet opvallen door veel meer detail, lengte of precisie dan de andere opties. "
                            "Gebruik geen grapantwoorden, extreme onzin of overduidelijke afleiders. "
                            "Geef alleen JSON terug."
                        )
                    }
                ],
                temperature=0.8
            )

            content = (resp.choices[0].message.content or "").strip()
            if not content:
                raise HTTPException(500, "AI gaf geen vraag terug.")

            try:
                ai_question = json.loads(content)
            except json.JSONDecodeError:
                raise HTTPException(
                    status_code=500,
                    detail=f"AI gaf geen geldige JSON terug: {content}"
                )

            if not isinstance(ai_question, dict):
                raise HTTPException(500, "AI gaf geen geldig vraagobject terug.")

            required_keys = {"question", "options", "correct_index"}
            if not required_keys.issubset(ai_question):
                raise HTTPException(500, "AI-vraag mist verplichte velden.")

            ai_question["question"] = str(ai_question["question"]).strip()
            if len(ai_question["question"]) < 24:
                raise HTTPException(500, "AI-vraag is te kort of te simplistisch.")

            ai_question["options"] = normalize_question_options(ai_question["options"])
            if len({option.casefold() for option in ai_question["options"]}) != 4:
                raise HTTPException(500, "AI-vraag heeft dubbele antwoordopties.")

            if not isinstance(ai_question["correct_index"], int) or not 0 <= ai_question["correct_index"] < 4:
                raise HTTPException(500, "AI-vraag heeft een ongeldige correct_index.")

            ai_question["theme"] = theme
            ai_question["source"] = "ai"
            ai_question["approved"] = False
            ai_question["rejected"] = False
            ai_question["used"] = False
            ai_question["difficulty"] = target_difficulty

            quality_issues = multiple_choice_quality_issues(ai_question, target_difficulty)
            if quality_issues:
                last_quality_feedback = quality_issues
                rejected_variants.append(ai_question["question"])
                continue

            duplicate_match = find_similar_question(ai_question, questions)
            if duplicate_match is not None:
                rejected_variants.append(ai_question["question"])
                continue

            ai_question["id"] = next_ai_question_id(questions)
            move_correct_option_to_index(ai_question, stable_question_correct_index(ai_question))
            ai_question["explanation"] = learning_explanation_text(ai_question)
            questions.append(ai_question)
            save_core_questions(questions)
            return with_question_difficulty_metadata(ai_question)

        if duplicate_match is not None:
            raise HTTPException(
                409,
                "AI blijft te gelijkaardige vragen voorstellen. Probeer opnieuw voor meer variatie."
            )

        if last_quality_feedback:
            raise HTTPException(
                500,
                "AI maakte nog geen sterke vraag met plausibele afleiders. Probeer opnieuw voor een betere variant."
            )

        raise HTTPException(500, "AI vraag kon niet uniek genoeg gegenereerd worden.")

    except HTTPException:
        raise
    except Exception as e:
        print("AI generation error:", e)
        raise HTTPException(500, "AI vraag kon niet gegenereerd worden.")
@app.post("/api/question/answer")
async def answer_question(
    payload: dict,
    x_game_session: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
):
    session_id = normalize_game_session_id(x_game_session)
    question_id = payload.get("id")
    chosen_index = payload.get("chosen_index")

    if str(question_id or "").startswith("prompt-improvement-"):
        submitted_prompt = str(payload.get("submitted_prompt") or "").strip()
        situation = str(payload.get("situation") or "").strip()
        weak_prompt = str(payload.get("weak_prompt") or "").strip()
        goal = str(payload.get("goal") or "").strip()
        if len(submitted_prompt) < 12:
            raise HTTPException(400, "Schrijf eerst een iets duidelijkere verbeterde prompt.")

        client = get_openai_client(allow_server_key=has_valid_ai_owner_password(x_ai_owner_password))
        if client is None:
            raise HTTPException(400, "Deze promptmissie kan alleen beoordeeld worden wanneer AI actief is.")

        try:
            resp = client.chat.completions.create(
                model=QUESTION_GENERATION_MODEL,
                response_format={"type": "json_object"},
                messages=[
                    {
                        "role": "system",
                        "content": (
                            "Je beoordeelt een verbeterde prompt van leerlingen van 12 tot 14 jaar. "
                            "Geef mild maar inhoudelijk feedback in eenvoudig Nederlands. "
                            "Score van 1 tot 4. Vanaf 2 is voldoende. Geef JSON met score, feedback en voorbeeld_prompt."
                        ),
                    },
                    {
                        "role": "user",
                        "content": (
                            f"Situatie: {situation}\n"
                            f"Zwakke prompt: {weak_prompt}\n"
                            f"Doel: {goal}\n"
                            f"Verbeterde prompt van leerlingen: {submitted_prompt}\n\n"
                            "Beoordeel op: duidelijk doel, context, gewenste vorm, grenzen/verantwoord gebruik."
                        ),
                    },
                ],
                temperature=0.2,
                timeout=10.0,
            )
            content = (resp.choices[0].message.content or "").strip()
            data = json.loads(content)
            score = max(1, min(4, int(data.get("score") or 1)))
            feedback = str(data.get("feedback") or "").strip()
            example_prompt = str(data.get("voorbeeld_prompt") or data.get("example_prompt") or "").strip()
        except Exception as exc:
            print("Prompt evaluation error:", exc)
            raise HTTPException(500, "Aico kon de verbeterde prompt nu niet beoordelen.")

        is_correct = score >= 2
        async with STATE_LOCK:
            gs = get_game_state(session_id)
            if gs is not None:
                label = "voldoende" if is_correct else "nog niet sterk genoeg"
                _log(gs, f"Promptmissie beoordeeld: {score}/4 ({label}).")

        return {
            "correct": is_correct,
            "correct_index": None,
            "correct_option": example_prompt or submitted_prompt,
            "correct_label": f"Score {score}/4",
            "question_type": "prompt_improvement",
            "score": score,
            "explanation": feedback or "Bespreek samen of de prompt duidelijk genoeg zegt wat AI moet doen.",
        }

    question = mark_question_used(question_id)
    if question is not None:
        question_type = str(question.get("type") or "multiple_choice")
        correct_index = question["correct_index"]
        is_correct = chosen_index == correct_index
        async with STATE_LOCK:
            gs = get_game_state(session_id)
            if gs is not None:
                record_group_question_result(gs, question, is_correct, chosen_index)
        correct_option = correct_option_text(question)
        return {
            "correct": is_correct,
            "correct_index": correct_index,
            "correct_option": correct_option,
            "correct_label": (
                image_binary_answer_label(correct_index)
                if question_type == "image_binary"
                else answer_label_from_index(correct_index)
            ),
            "question_type": question_type,
            "explanation": learning_explanation_text(question),
        }

    raise HTTPException(404, "Vraag niet gevonden.")


@app.post("/api/consensus/start")
async def start_consensus_challenge(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")

        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")

        if gs.consensus_active:
            return {
                "ok": True,
                "message": "De rode ethiekknop is al actief.",
                "question_id": gs.consensus_question_id,
                "question": gs.consensus_question,
                "guidance": gs.consensus_guidance,
                "state": gs,
            }

        if gs.consensus_used_count >= CONSENSUS_MAX_USES:
            raise HTTPException(400, "De rode ethiekknop is in dit spel al 3 keer gebruikt.")

        all_dilemmas = load_all_consensus_dilemmas()
        if not all_dilemmas:
            raise HTTPException(400, "Er zijn momenteel geen groepsdilemma's beschikbaar.")

        unused_dilemmas = [
            dilemma for dilemma in all_dilemmas
            if dilemma.get("id") not in gs.consensus_used_ids
        ]
        dilemma = random.choice(unused_dilemmas or all_dilemmas)
        _pause_game_clock(gs, reason="consensus")
        gs.consensus_active = True
        gs.consensus_question_id = dilemma["id"]
        gs.consensus_question = dilemma["question"]
        gs.consensus_guidance = dilemma["guidance"]
        if dilemma["id"] not in gs.consensus_used_ids:
            gs.consensus_used_ids.append(dilemma["id"])
        if dilemma.get("source") == "teacher":
            mark_consensus_dilemma_used(dilemma["id"])

        _log(gs, "Rode ethiekknop geactiveerd. De groep bespreekt een ethisch AI-dilemma.")
        _log(gs, "De spelklok is gepauzeerd zolang dit groepsdilemma actief is.")
        _log(gs, "Roep de leerkracht wanneer de groep tot een consensus is gekomen.")

        return {
            "ok": True,
            "message": "Ethische groepsvraag gestart.",
            "question_id": gs.consensus_question_id,
            "question": gs.consensus_question,
            "guidance": gs.consensus_guidance,
            "state": gs,
        }


@app.post("/api/consensus/evaluate")
async def evaluate_consensus(
    payload: ConsensusEvaluationRequest,
    x_teacher_password: Optional[str] = Header(None),
    x_game_session: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    session_id = normalize_game_session_id(x_game_session)

    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")

        if not gs.consensus_active or not gs.consensus_question:
            raise HTTPException(400, "Er is momenteel geen actieve ethische groepsvraag.")

        destroyed_tiles: List[Coord] = []
        removed_items: List[SpawnItem] = []
        question_text = gs.consensus_question
        pause_duration = _resume_game_clock(gs, reason="consensus")

        if payload.decision == "approve":
            gs.passage_bonus_tiles += CONSENSUS_PASSAGE_REWARD
            message = (
                f"Consensus goedgekeurd. De groep mag samen een doorgang van "
                f"{CONSENSUS_PASSAGE_REWARD} tegels creëren."
            )
            _log(gs, f"Leerkracht keurt de consensus goed voor vraag: {question_text}")
            _log(gs, f"Beloning: de groep mag een doorgang van {CONSENSUS_PASSAGE_REWARD} tegels maken.")
        else:
            destroyed_tiles = random_destroyed_coords(gs, CONSENSUS_EXPLOSION_PENALTY)
            gs.destroyed_tiles.extend(destroyed_tiles)

            for item in list(gs.items):
                if item.coord in destroyed_tiles:
                    removed_items.append(item)
                    gs.items.remove(item)

            coords_text = ", ".join(destroyed_tiles)
            message = (
                f"Consensus onvoldoende. Tegels {coords_text} ontploffen en kunnen niet meer gebruikt worden."
            )
            _log(gs, f"Leerkracht beoordeelt de consensus als onvoldoende voor vraag: {question_text}")
            _log(gs, f"Straf: tegels {coords_text} zijn verwoest en blijven afgesloten.")
            if removed_items:
                removed_labels = ", ".join(
                    f"{'diamant' if item.kind == 'diamond' else 'dynamiet'} op {item.coord}"
                    for item in removed_items
                )
                _log(gs, f"Door de ontploffing verdwijnen ook: {removed_labels}.")

        gs.consensus_active = False
        gs.consensus_used_count += 1
        gs.consensus_question_id = None
        gs.consensus_question = None
        gs.consensus_guidance = None
        if pause_duration > 0:
            _log(gs, f"De spelklok hervat na {int(round(pause_duration))} seconden pauze.")

        return {
            "ok": True,
            "message": message,
            "destroyed_tiles": destroyed_tiles,
            "passage_bonus_tiles": gs.passage_bonus_tiles,
            "state": gs,
        }


@app.get("/api/state", response_model=Optional[GameState])
async def get_state(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        return get_game_state(session_id)


@app.post("/api/reset", response_model=OptionalStateActionResponse)
async def reset_game_state(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is not None:
            _log(gs, "Spel automatisch teruggezet naar het startscherm na 3 minuten zonder activiteit.")
        clear_game_state(session_id)

    reset_questions()
    return OptionalStateActionResponse(
        ok=True,
        message="Geen activiteit gedetecteerd. De spel-app staat opnieuw op het startscherm.",
        state=None,
    )


@app.get("/api/ranking", response_model=List[AllTimeRankingEntry])
async def get_all_time_ranking():
    return load_all_time_ranking()


@app.post("/api/ranking/finalize", response_model=ActionResponse)
async def finalize_all_time_ranking(payload: RankingFinalizeRequest, x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")

        if gs.phase != "finished":
            raise HTTPException(400, "De ranking kan pas na het einde van het spel bevestigd worden.")

        if not gs.ranking_name_prompt_pending:
            raise HTTPException(400, "De rankingnamen zijn voor dit spel al bevestigd.")

        escaped_players = _escaped_players(gs)
        if not escaped_players:
            raise HTTPException(400, "Er zijn geen ontsnapte spelers om in de ranking te zetten.")

        normalized_names = _normalize_ranking_player_names(payload.player_names, len(escaped_players))
        for player, name in zip(escaped_players, normalized_names):
            player.name = name

        diamond_total = _escaped_diamond_total(gs)
        entry_id = gs.latest_all_time_ranking_entry_id or gs.game_id
        existing_entry = next((entry for entry in load_all_time_ranking() if entry.id == entry_id), None)
        entry = AllTimeRankingEntry(
            id=entry_id,
            game_id=gs.game_id,
            created_at=existing_entry.created_at if existing_entry else time.time(),
            player_names=normalized_names,
            escaped_player_count=len(normalized_names),
            diamond_total=diamond_total,
        )

        _persist_all_time_ranking_entry(entry)
        gs.latest_all_time_ranking_entry_id = entry.id
        gs.final_result_note = _ranking_summary_text(normalized_names, diamond_total)
        gs.ranking_name_prompt_pending = False
        _sync_ranking_snapshot(gs)
        _log(gs, "Rankingnamen bevestigd: " + ", ".join(normalized_names) + ".")

        return ActionResponse(
            ok=True,
            message="De all time ranking is opgeslagen met de bevestigde namen.",
            state=gs,
        )


@app.get("/api/evaluation/pdf")
async def download_group_evaluation_pdf(
    x_teacher_password: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
    x_game_session: Optional[str] = Header(None),
):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        state_snapshot = gs.model_copy(deep=True)

    pdf_bytes = build_group_evaluation_pdf(
        state_snapshot,
        allow_ai=has_valid_teacher_password(x_teacher_password),
        allow_server_key=has_valid_ai_owner_password(x_ai_owner_password),
    )

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="groepsevaluatie-ai-geletterdheid.pdf"',
        },
    )


@app.post("/api/timer/pause", response_model=ActionResponse)
async def pause_timer(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")

        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "De spelklok kan nu niet gepauzeerd worden.")

        already_manual = "manual" in gs.pause_reasons
        _pause_game_clock(gs, reason="manual")
        if already_manual:
            message = "De spelklok stond al handmatig op pauze."
        else:
            _log(gs, "De spelklok wordt handmatig gepauzeerd.")
            message = "De spelklok is gepauzeerd."

        return ActionResponse(ok=True, message=message, state=gs)


@app.post("/api/timer/resume", response_model=ActionResponse)
async def resume_timer(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")

        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "De spelklok kan nu niet hervat worden.")

        if "manual" not in gs.pause_reasons:
            raise HTTPException(400, "De handmatige pauze staat momenteel niet aan.")

        pause_duration = _resume_game_clock(gs, reason="manual")
        if gs.timer_paused:
            message = "De handmatige pauze is opgeheven, maar een andere spelpauze blijft actief."
        else:
            resumed_seconds = int(round(pause_duration))
            _log(gs, f"De spelklok hervat na een handmatige pauze van {resumed_seconds} seconden.")
            message = "De spelklok loopt opnieuw."

        return ActionResponse(ok=True, message=message, state=gs)


@app.get("/api/teacher/auth-check")
async def teacher_auth_check(x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)
    return {"ok": True}


@app.get("/api/teacher/ai-settings")
async def get_teacher_ai_settings(
    x_teacher_password: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    return build_ai_runtime_status(owner_verified=has_valid_ai_owner_password(x_ai_owner_password))


@app.post("/api/teacher/ai-settings")
async def update_teacher_ai_settings(
    payload: TeacherAISettingsRequest,
    x_teacher_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    owner_verified = has_valid_ai_owner_password(payload.owner_password)

    if payload.mode == "disabled":
        AI_RUNTIME_CONFIG.update({
            "mode": "disabled",
            "byok_client": None,
            "byok_expires_at": 0.0,
            "byok_last4": "",
        })
        return {
            "ok": True,
            "message": "AI staat uit. De app blijft werken met lokale hulp en bestaande vragen.",
            "status": build_ai_runtime_status(owner_verified=owner_verified),
        }

    if payload.mode == "default":
        if _client is not None:
            if not AI_OWNER_PASSWORD:
                raise HTTPException(
                    403,
                    "Serverkey is beschermd. Stel eerst AI_OWNER_PASSWORD in als environment variable.",
                )
            if not owner_verified:
                raise HTTPException(403, "Alleen de eigenaar kan de serverkey gebruiken.")
        AI_RUNTIME_CONFIG.update({
            "mode": "default",
            "byok_client": None,
            "byok_expires_at": 0.0,
            "byok_last4": "",
        })
        message = (
            "De app gebruikt opnieuw de serverkey uit de omgeving."
            if _client is not None
            else "Er is geen serverkey ingesteld. De app werkt zonder AI tot er een BYOK-sleutel wordt ingesteld."
        )
        return {"ok": True, "message": message, "status": build_ai_runtime_status(owner_verified=owner_verified)}

    api_key = str(payload.api_key or "").strip()
    if not api_key:
        raise HTTPException(400, "Geef eerst een OpenAI API-sleutel in.")
    if OpenAI is None:
        raise HTTPException(500, "De OpenAI-bibliotheek is niet beschikbaar op deze server.")

    ttl_minutes = max(5, min(int(payload.ttl_minutes), AI_BYOK_MAX_TTL_MINUTES))
    AI_RUNTIME_CONFIG.update({
        "mode": "byok",
        "byok_client": OpenAI(api_key=api_key),
        "byok_expires_at": time.time() + ttl_minutes * 60,
        "byok_last4": api_key[-4:],
    })
    return {
        "ok": True,
        "message": f"BYOK is actief voor {ttl_minutes} minuten. De sleutel wordt niet getoond en vervalt automatisch.",
        "status": build_ai_runtime_status(owner_verified=owner_verified),
    }


@app.post("/api/ranking/clear")
async def clear_all_time_ranking(
    x_teacher_password: Optional[str] = Header(None),
    x_game_session: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    session_id = normalize_game_session_id(x_game_session)
    save_all_time_ranking([])

    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is not None:
            gs.all_time_ranking = []

        state_payload = gs

    return {
        "ok": True,
        "message": "De all time ranking is leeggemaakt.",
        "state": state_payload,
    }


@app.get("/api/question/pending")
async def pending_questions(x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)

    questions = prune_duplicate_pending_ai_questions()

    pending = [
        q for q in questions
        if q.get("approved") is False and not q.get("rejected", False)
    ]

    return [with_question_difficulty_metadata(question) for question in pending]


@app.get("/api/question/settings")
async def get_question_settings(
    x_teacher_password: Optional[str] = Header(None),
    x_game_session: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    session_id = normalize_game_session_id(x_game_session)

    async with STATE_LOCK:
        state_payload = get_game_state(session_id)

    mode = normalize_question_difficulty_mode(
        getattr(state_payload, "question_difficulty_mode", None) if state_payload is not None else QUESTION_DIFFICULTY_MODE
    )
    return {
        "mode": mode,
        "label": question_difficulty_mode_label(mode),
        "description": question_difficulty_mode_description(mode),
        "state": state_payload,
    }


@app.post("/api/question/settings")
async def update_question_settings(
    payload: QuestionDifficultyModeRequest,
    x_teacher_password: Optional[str] = Header(None),
    x_game_session: Optional[str] = Header(None),
):
    global QUESTION_DIFFICULTY_MODE

    require_teacher_password(x_teacher_password)
    session_id = normalize_game_session_id(x_game_session)
    normalized_mode = normalize_question_difficulty_mode(payload.mode)
    QUESTION_DIFFICULTY_MODE = normalized_mode

    async with STATE_LOCK:
        state_payload = get_game_state(session_id)
        if state_payload is not None:
            state_payload.question_difficulty_mode = normalized_mode

    return {
        "ok": True,
        "message": (
            "Het vraagniveau staat nu op "
            + question_difficulty_mode_label(normalized_mode)
            + ". Deze keuze geldt voor het huidige en volgende spel."
        ),
        "mode": normalized_mode,
        "label": question_difficulty_mode_label(normalized_mode),
        "description": question_difficulty_mode_description(normalized_mode),
        "state": state_payload,
    }


@app.get("/api/question/removable")
async def removable_questions(x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)
    return load_removable_questions()


@app.post("/api/question/remove")
async def remove_question(
    payload: TeacherQuestionDeleteRequest,
    x_teacher_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)

    if delete_removable_question(payload.id):
        return {"ok": True, "message": "Item verwijderd uit de app."}

    raise HTTPException(404, "Vraag niet gevonden.")


@app.post("/api/question/review")
async def review_question(payload: QuestionReviewRequest, x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)

    questions = load_core_questions()

    for index, question in enumerate(questions):
        if question.get("id") != payload.id:
            continue

        if payload.action == "delete":
            questions.pop(index)
            save_core_questions(questions)
            return {"ok": True, "message": "Vraag verwijderd."}

        if payload.action == "reject":
            question["approved"] = False
            question["rejected"] = True
            save_core_questions(questions)
            return {"ok": True, "message": "Vraag afgekeurd."}

        if payload.question is None or payload.options is None or payload.correct_index is None:
            raise HTTPException(400, "Vraagtekst, opties en juiste antwoordindex zijn verplicht.")

        normalized_question = payload.question.strip()
        if not normalized_question:
            raise HTTPException(400, "De vraagtekst mag niet leeg zijn.")

        normalized_options = normalize_question_options(payload.options)
        if not 0 <= payload.correct_index < 4:
            raise HTTPException(400, "Kies een geldig correct antwoord.")

        question["question"] = normalized_question
        question["options"] = normalized_options
        question["correct_index"] = payload.correct_index
        question["difficulty"] = infer_question_difficulty(question)
        question["approved"] = True
        question["rejected"] = False

        duplicate_match = find_similar_question(
            question,
            [
                existing
                for existing in questions
                if existing.get("id") != payload.id and not existing.get("rejected", False)
            ],
        )
        if duplicate_match is not None:
            raise HTTPException(
                409,
                f"Deze vraag staat al bijna hetzelfde in de lijst: {duplicate_match.get('question', 'bestaande vraag')}",
            )

        save_core_questions(questions)
        return {"ok": True, "message": "Vraag goedgekeurd en opgeslagen."}

    raise HTTPException(404, "Vraag niet gevonden.")


@app.post("/api/question/image-upload")
async def upload_teacher_image(
    payload: TeacherImageUploadRequest,
    x_teacher_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)

    image_url = save_teacher_uploaded_image(payload.data_url, str(payload.filename or ""))
    return {
        "ok": True,
        "message": "Afbeelding opgeslagen en klaar voor je beeldvraag.",
        "image_url": image_url,
    }


@app.post("/api/question/image-set/generate")
async def generate_teacher_image_set(
    payload: TeacherAutoImageSetRequest,
    x_teacher_password: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    allow_server_key = has_valid_ai_owner_password(x_ai_owner_password)

    focus = str(payload.focus or "").strip()
    existing_image_questions = load_image_questions()
    real_candidates = unique_real_image_candidates(load_round_image_questions())
    local_ai_candidates = unique_ai_image_candidates(existing_image_questions)

    if not real_candidates:
        raise HTTPException(
            400,
            "Er zijn momenteel geen betrouwbare echte foto's beschikbaar voor de beeldronde.",
        )

    real_count = 1
    target_ai_count = payload.count - real_count
    if target_ai_count <= 0:
        raise HTTPException(400, "De automatische beeldmix heeft minstens een AI-beeld nodig.")

    selected_real_questions = random.sample(real_candidates, k=real_count)
    selected_scenes = choose_auto_image_scene_seeds_for_generation(target_ai_count, local_ai_candidates)

    new_questions: List[dict] = []
    preview_questions: List[dict] = [
        build_auto_image_preview_item(selected_real_questions[0], "bestaand")
    ]
    working_questions = list(existing_image_questions)
    generated_ai_count = 0
    fallback_ai_count = 0
    openai_failed = False
    client_available = get_openai_client(allow_server_key=allow_server_key) is not None

    for scene in selected_scenes:
        if openai_failed or not client_available:
            break

        try:
            generated_image = generate_ai_mix_image(scene, focus, allow_server_key=allow_server_key)
        except HTTPException as exc:
            print("AI image mix fallback:", exc.detail)
            if exc.status_code in (502, 503):
                openai_failed = True
                break
            raise

        generated_question = build_auto_image_question(
            working_questions,
            correct_index=0,
            image_url=generated_image["image_url"],
            image_alt=generated_image["image_alt"],
            explanation=str(generated_image.get("explanation") or "").strip() or (
                "Dit beeld werd met AI gemaakt voor deze automatische beeldmix. "
                "Tip: let op kleine details zoals tekst, randen, reflecties, vingers en schaduwen die net niet logisch blijven."
            ),
            source="ai",
        )
        working_questions.append(generated_question)
        new_questions.append(generated_question)
        preview_questions.append(generated_question)
        generated_ai_count += 1

    remaining_ai_count = target_ai_count - generated_ai_count
    if remaining_ai_count > 0:
        if not local_ai_candidates:
            raise HTTPException(
                500,
                "De server kon geen nieuwe AI-beelden genereren en er staan ook geen lokale AI-beeldvragen klaar als fallback.",
            )

        selected_local_ai_questions = random.sample(
            local_ai_candidates,
            k=min(remaining_ai_count, len(local_ai_candidates)),
        )

        if len(selected_local_ai_questions) < remaining_ai_count:
            raise HTTPException(
                500,
                "Er zijn niet genoeg lokale AI-beeldvragen beschikbaar om de automatische beeldmix aan te vullen.",
            )

        for ai_question in selected_local_ai_questions:
            preview_questions.append(build_auto_image_preview_item(ai_question, "bestaand"))
            fallback_ai_count += 1

    if new_questions:
        existing_image_questions.extend(new_questions)
        save_image_questions(existing_image_questions)

    ai_total = generated_ai_count + fallback_ai_count
    ai_suffix = "AI-beeld" if ai_total == 1 else "AI-beelden"
    generation_note = ""
    if generated_ai_count and fallback_ai_count:
        generation_note = (
            f" {generated_ai_count} {('AI-beeld' if generated_ai_count == 1 else 'AI-beelden')} "
            "zijn nieuw gegenereerd; de rest komt uit de bestaande beeldpool."
        )
    elif generated_ai_count:
        generation_note = " Alle AI-beelden zijn nieuw gegenereerd via OpenAI."
    elif fallback_ai_count:
        generation_note = " De AI-beelden voor deze mix komen uit de bestaande beeldpool en zijn niet opnieuw opgeslagen."

    return {
        "ok": True,
        "message": (
            f"Automatische beeldmix klaar: 1 betrouwbare echte foto en {ai_total} {ai_suffix}."
            f"{generation_note}"
        ),
        "real_count": real_count,
        "ai_count": ai_total,
        "generated_ai_count": generated_ai_count,
        "fallback_ai_count": fallback_ai_count,
        "questions": preview_questions,
        "saved_count": len(new_questions),
        "preview_message": (
            f"De mix hieronder gebruikt 1 betrouwbare echte foto en {ai_total} {ai_suffix.lower()}."
            " Alleen echt nieuwe AI-vragen worden extra toegevoegd onder 'Vragen verwijderen'."
        ),
    }


@app.post("/api/question/manual")
async def create_teacher_question(
    payload: TeacherQuestionCreateRequest,
    x_teacher_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)
    theme_key = normalize_theme_key(payload.theme)

    normalized_question = payload.question.strip()
    if not normalized_question:
        raise HTTPException(400, "De vraagtekst mag niet leeg zijn.")

    if payload.question_type == "consensus_dilemma":
        guidance = str(payload.guidance or "").strip()
        if not guidance:
            raise HTTPException(400, "Voeg korte besprekingshulp toe voor dit groepsdilemma.")

        dilemmas = load_consensus_dilemmas()
        teacher_dilemma = {
            "id": next_teacher_consensus_id(dilemmas),
            "source": "teacher",
            "type": "consensus_dilemma",
            "display_theme": "Groepsdilemma",
            "question": normalized_question,
            "guidance": guidance,
            "used": False,
        }

        dilemmas.append(teacher_dilemma)
        save_consensus_dilemmas(dilemmas)

        return {
            "ok": True,
            "message": "Eigen groepsdilemma opgeslagen en meteen toegevoegd aan de rode ethiekknop.",
            "question": teacher_dilemma,
        }

    if payload.question_type == "image_binary":
        image_url = str(payload.image_url or "").strip()
        if not image_url:
            raise HTTPException(400, "Geef een afbeeldingspad of afbeeldings-URL op.")

        if payload.correct_index not in (0, 1):
            raise HTTPException(400, "Kies bij een beeldvraag of het beeld AI-gegenereerd of echt is.")

        explanation = str(payload.explanation or "").strip()
        if not explanation:
            raise HTTPException(400, "Voeg korte uitleg toe met een tip waar leerlingen op moeten letten.")

        if payload.correct_index == 1 and not is_trusted_real_image_url(image_url):
            raise HTTPException(
                400,
                "Echte foto's voor de beeldronde moeten uit Wikimedia Commons komen.",
            )

        image_questions = load_image_questions()
        duplicate_image = find_duplicate_image_question(
            {"type": "image_binary", "image_url": image_url},
            image_questions + build_trusted_real_image_questions(),
        )
        if duplicate_image is not None:
            raise HTTPException(409, "Dit beeld staat al in de lijst. Kies een andere afbeelding.")

        teacher_question = {
            "id": next_prefixed_question_id(image_questions, "image_round_"),
            "source": "teacher",
            "type": "image_binary",
            "theme": "beeld",
            "display_theme": THEMES["beeld"]["label"],
            "question": normalized_question,
            "options": list(IMAGE_BINARY_OPTIONS),
            "correct_index": payload.correct_index,
            "image_url": image_url,
            "image_alt": str(payload.image_alt or "").strip() or "Beeld bij de vraag",
            "explanation": explanation,
            "approved": True,
            "rejected": False,
            "used": False,
        }

        image_questions.append(teacher_question)
        save_image_questions(image_questions)

        return {
            "ok": True,
            "message": "Eigen beeldvraag opgeslagen en meteen toegevoegd aan het spel.",
            "question": teacher_question,
        }

    if payload.theme is None:
        raise HTTPException(400, "Kies eerst een thema voor deze meerkeuzevraag.")
    if theme_key not in THEMES:
        raise HTTPException(400, "Ongeldig thema.")
    if theme_key == "beeld":
        raise HTTPException(
            400,
            "De beeldronde bevat alleen beeldvragen. Gebruik daarvoor het beeldformulier of de automatische beeldmix.",
        )

    if payload.options is None:
        raise HTTPException(400, "Voeg vier antwoordopties toe voor deze meerkeuzevraag.")

    normalized_options = normalize_question_options(payload.options)
    if len({option.casefold() for option in normalized_options}) != 4:
        raise HTTPException(400, "De antwoordopties moeten van elkaar verschillen.")

    if not 0 <= payload.correct_index < 4:
        raise HTTPException(400, "Kies een geldig correct antwoord.")

    questions = load_core_questions()
    teacher_question = {
        "id": next_teacher_question_id(questions),
        "theme": theme_key,
        "source": "teacher",
        "question": normalized_question,
        "options": normalized_options,
        "correct_index": payload.correct_index,
        "difficulty": infer_question_difficulty({
            "type": "multiple_choice",
            "theme": theme_key,
            "source": "teacher",
            "question": normalized_question,
            "options": normalized_options,
        }),
        "approved": True,
        "rejected": False,
        "used": False,
    }

    duplicate_question = find_similar_question(
        teacher_question,
        [question for question in questions if not question.get("rejected", False)],
    )
    if duplicate_question is not None:
        raise HTTPException(
            409,
            f"Deze vraag lijkt al te bestaan: {duplicate_question.get('question', 'bestaande vraag')}",
        )

    questions.append(teacher_question)
    save_core_questions(questions)

    return {
        "ok": True,
        "message": "Eigen vraag opgeslagen en meteen toegevoegd aan het spel.",
        "question": with_question_difficulty_metadata(teacher_question),
    }
    
@app.post("/api/next_turn", response_model=ActionResponse)
async def next_turn(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, f"Spel is niet actief (phase={gs.phase}).")

        # Advance to next non-escaped player
        for _ in range(len(gs.players)):
            gs.turn_index = (gs.turn_index + 1) % len(gs.players)
            if not gs.players[gs.turn_index].escaped:
                break

        cp = gs.current_player()
        if cp is None:
            _finish_immediately_if_all_players_escaped(gs)
            return ActionResponse(
                ok=True,
                message="Alle spelers zijn buiten. De teller staat op 0 en de mijn ontploft meteen.",
                state=gs,
            )

        _log(gs, f"Beurt: {cp.name}")
        return ActionResponse(ok=True, message=f"Aan beurt: {cp.name}", state=gs)


@app.post("/api/spawn", response_model=ActionResponse)
async def spawn_item(req: SpawnRequest, x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")

        # Enforce max simultaneous for this kind
        existing = [it for it in gs.items if it.kind == req.kind]
        if len(existing) >= req.max_simultaneous:
            return ActionResponse(ok=False, message=f"Max {req.max_simultaneous} {req.kind} al op bord.", state=gs)

        # Itemspawns zijn los van spelerposities: spelers houden die fysiek op het bord bij.
        coord = random_empty_coord(gs.occupied_coords(include_start_coords=True))
        gs.items.append(SpawnItem(kind=req.kind, coord=coord, spawned_at=time.time()))
        _log(gs, f"{req.kind.upper()} verschijnt op {coord}.")
        chain_blast_triggered = False
        if req.kind == "dynamite":
            chain_blast_triggered = _register_distributed_dynamite(gs)

        message = f"{req.kind} op {coord}"
        if chain_blast_triggered:
            message += " en meteen gevolgd door een dynamietketting."
        return ActionResponse(ok=True, message=message, state=gs)


@app.post("/api/item/remove", response_model=ActionResponse)
async def remove_item(req: RemoveItemRequest, x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")

        try:
            parse_coord(req.coord)
        except ValueError as e:
            raise HTTPException(400, str(e))

        item = next((it for it in gs.items if it.coord == req.coord), None)
        if item is None:
            return ActionResponse(ok=False, message="Geen actief item op dit coordinaat.", state=gs)

        player = gs.current_player()
        if player is None:
            return ActionResponse(
                ok=False,
                message="Er is geen actieve speler aan beurt om dit item aan te koppelen.",
                state=gs,
            )

        gs.items.remove(item)
        message = _collect_item_for_player(gs, player, item)
        return ActionResponse(ok=True, message=message, state=gs)


@app.post("/api/reveal_exit", response_model=ActionResponse)
async def reveal_exit_manual(x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")
        _reveal_exit(gs, reason="handmatig")
        return ActionResponse(ok=True, message=f"Uitgang: {gs.exit_coord}", state=gs)


@app.post("/api/emergency/{player_id}", response_model=ActionResponse)
async def press_emergency(player_id: str, x_game_session: Optional[str] = Header(None)):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")
        if gs.emergency_pressed:
            return ActionResponse(ok=False, message="De groene exitknop is al gebruikt.", state=gs)

        current_player = gs.current_player()
        if current_player is None:
            raise HTTPException(400, "Er is momenteel geen actieve speler aan beurt.")
        if current_player.id != player_id:
            return ActionResponse(
                ok=False,
                message="Alleen de speler die aan beurt is mag de groene exitknop indrukken.",
                state=gs,
            )

        # Reveal exit + start 5-minute endgame
        reference_now = gs.paused_at if gs.timer_paused and gs.paused_at else time.time()

        gs.emergency_pressed = True
        gs.emergency_pressed_by = player_id
        gs.emergency_pressed_at = time.time()
        gs.phase = "endgame"

        _reveal_exit(gs, reason=f"groene exitknop door {current_player.name}")

        gs.deadline_at = reference_now + CONFIG["emergency_endgame_minutes"] * 60
        _log(
            gs,
            f"GROENE EXITKNOP ingedrukt door {current_player.name}. "
            f"Explosie over {CONFIG['emergency_endgame_minutes']} min."
        )
        _log(gs, "Regel: groene exitknop indrukken = beurt en uitgang wordt meteen onthuld.")

        return ActionResponse(ok=True, message="Groene exitknop geactiveerd. Eindfase gestart.", state=gs)


@app.post("/api/collect/{player_id}", response_model=ActionResponse)
async def collect_on_tile(
    player_id: str,
    coord: Coord,
    x_game_session: Optional[str] = Header(None),
):
    """
    Semi-manual helper:
    Call this when a player ends movement on a coord.
    If there's a diamond/dynamite there, it's collected.
    For diamonds: +1 info card
    For dynamite: +1 dynamite
    """
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")

        try:
            parse_coord(coord)
        except ValueError as e:
            raise HTTPException(400, str(e))

        player = next((p for p in gs.players if p.id == player_id), None)
        if not player:
            raise HTTPException(404, "Speler niet gevonden.")

        found = [it for it in gs.items if it.coord == coord]
        if not found:
            return ActionResponse(ok=True, message="Niets te verzamelen op dit vak.", state=gs)

        # Collect all items at coord (usually max 1)
        for it in found:
            _collect_item_for_player(gs, player, it)
            gs.items.remove(it)

        return ActionResponse(ok=True, message="Verzameld.", state=gs)


@app.post("/api/escape/{player_id}", response_model=ActionResponse)
async def player_escape(
    player_id: str,
    coord: Optional[Coord] = None,
    x_game_session: Optional[str] = Header(None),
):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)
        if gs is None:
            raise HTTPException(404, "Geen actief spel.")
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")
        if not gs.exit_known or not gs.exit_coord:
            raise HTTPException(400, "Uitgang is nog niet bekend.")

        player = next((p for p in gs.players if p.id == player_id), None)
        if not player:
            raise HTTPException(404, "Speler niet gevonden.")
        if player.escaped:
            return ActionResponse(ok=True, message="Speler was al ontsnapt.", state=gs)

        if coord is not None:
            try:
                parse_coord(coord)
            except ValueError as e:
                raise HTTPException(400, str(e))

            if coord != gs.exit_coord:
                return ActionResponse(ok=False, message="Speler staat niet op de uitgang.", state=gs)

        player.escaped = True
        player.escaped_at = time.time()
        if coord is None:
            _log(gs, f"{player.name} is ONTSNAPT en speelt niet meer mee (handmatig bevestigd op fysiek bord).")
        else:
            _log(gs, f"{player.name} is ONTSNAPT en speelt niet meer mee.")

        if all(current_player.escaped for current_player in gs.players):
            _finish_immediately_if_all_players_escaped(gs)
            return ActionResponse(
                ok=True,
                message=f"{player.name} ontsnapt. Iedereen is buiten: de mijn ontploft meteen.",
                state=gs,
            )

        return ActionResponse(ok=True, message=f"{player.name} ontsnapt.", state=gs)


# ----------------------------
# Aico: Chat endpoint
# ----------------------------

def _normalize_bot_rule_text(text: str) -> str:
    normalized = unicodedata.normalize("NFKD", str(text or ""))
    return normalized.encode("ascii", "ignore").decode("ascii").casefold().strip()


def _bot_recent_events(gs: Optional[GameState], limit: int = 6) -> str:
    if not gs or not gs.event_log:
        return "- Nog geen recente gebeurtenissen."
    return "\n".join(f"- {line}" for line in gs.event_log[-limit:])


def _bot_active_items_summary(gs: Optional[GameState]) -> str:
    if not gs:
        return "Diamanten: nog geen actief spel | Dynamiet: nog geen actief spel"

    diamonds = sorted(item.coord for item in gs.items if item.kind == "diamond")
    dynamite = sorted(item.coord for item in gs.items if item.kind == "dynamite")

    parts: List[str] = []
    parts.append("Diamanten: " + (", ".join(diamonds) if diamonds else "geen actieve diamanten"))
    parts.append("Dynamiet: " + (", ".join(dynamite) if dynamite else "geen actieve dynamietstaven"))
    return " | ".join(parts)


def _bot_rulebook(gs: Optional[GameState]) -> str:
    remaining_seconds = gs.remaining_seconds() if gs and gs.remaining_seconds() is not None else "onbekend"
    current_player_name = gs.current_player().name if gs and gs.current_player() else "geen actieve speler"
    phase = gs.phase if gs else "nog geen actief spel"
    exit_known = "ja" if gs and gs.exit_known else "nee"
    exit_coord = gs.exit_coord if gs and gs.exit_known else "nog onbekend"
    destroyed_tiles = len(gs.destroyed_tiles) if gs else 0
    consensus_used = gs.consensus_used_count if gs else 0
    passage_bonus = gs.passage_bonus_tiles if gs else 0

    return f"""
Officiele spelregels van De diamantmijn. Volg deze regels letterlijk en verzin niets erbij.

Algemeen:
- Doel: verzamel diamanten en raak voor de explosie uit de diamantmijn.
- De app beheert timer, startcoördinaten, vragen, itemalarmen, uitgang en eindresultaat.
- Pionbeweging en het echte leggen of wegnemen van fysieke tegels gebeuren op het fysieke bord.

Start van het spel:
- Bij een nieuw spel krijgt elke speler een willekeurig startcoördinaat.
- Bij de start liggen er al 6 diamanten en 4 dynamietstaven op willekeurige vrije vakken.
- Daarna kunnen extra diamanten en dynamietstaven later opnieuw verschijnen.

Beurten en vragen:
- Spelers kiezen meestal een themaknop om een vraag te openen.
- Bij een gewone meerkeuzevraag geldt: juist antwoord = zelf 3 tegels leggen; fout antwoord = de app geeft 1 verplicht plaatsingscoördinaat.
- Bij een beeldvraag kies je of een foto waarschijnlijk echt is, of door AI gegenereerd of bewerkt.
- Na het afronden van een beantwoorde vraag springt de beurt automatisch door naar de volgende speler.
- De knop 'Volgende speler' is een noodknop om handmatig door te geven als een beurt niet via een vraag eindigt.

Diamanten en dynamiet:
- Een diamant op een vak verzamelen geeft +1 diamant/infofiche aan die speler.
- Een dynamietstaaf op een vak verzamelen geeft +1 dynamiet aan die speler.
- Diamanten en dynamiet op het bord worden door de app als actieve locaties getoond.
- Nieuwe diamanten verschijnen willekeurig met enkele minuten ertussen; nieuwe dynamietstaven ook.

Dynamietketting:
- Dynamiet kan onverwacht in een kettingreactie ontploffen.
- Dat gebeurt willekeurig ergens op de 4e, 5e of 6e verdeelde dynamietstaaf.
- Dan ontploffen alle dynamietstaven op het bord tegelijk.
- Ook alle dynamietstaven die spelers al verzameld hebben, moeten dan terug uit het spel.
- Elke dynamietstaaf die op het bord lag, maakt een holte van 2 op 2 vakjes.

Groene exitknop:
- Alleen de speler die op dat moment aan beurt is, mag de groene exitknop indrukken.
- Zodra die knop wordt ingedrukt, wordt de uitgang meteen onthuld.
- Vanaf dan start de eindfase en springt de explosieteller naar 5 minuten.

Ontsnappen en einde:
- Een speler kan pas ontsnappen als de uitgang onthuld is.
- Ontsnapte spelers doen niet meer mee aan volgende beurten.
- Als iedereen al buiten is, springt de teller naar 0 en ontploft de mijn meteen voor het eindresultaat.
- Pas na de explosie verschijnt de all time ranking.
- Voor die ranking tellen alleen diamanten mee van spelers die effectief ontsnapt zijn.

Rode knop / groepsdilemma:
- De rode knop kan maximaal {CONSENSUS_MAX_USES} keer per spel gebruikt worden.
- Terwijl het groepsdilemma actief is, staat de spelklok stil.
- Bij goedkeuring door de leerkracht mag de groep een doorgang van {CONSENSUS_PASSAGE_REWARD} tegels maken.
- Bij afkeuring ontploffen {CONSENSUS_EXPLOSION_PENALTY} willekeurige tegels definitief.

Pauze:
- De paarse pauzeknop zet de spelklok tijdelijk stil.
- Hervatten gebeurt met dezelfde knop.

Vraagselectie:
- Een themaknop probeert eerst een vraag van dat thema te geven.
- De themaknop 'AI-foto's herkennen' geeft beeldvragen en vragen over deepfakes, broncontrole en visuele aanwijzingen.

Huidige live spelstatus:
- Fase: {gs.phase}
- Resterende tijd: {gs.remaining_seconds() if gs.remaining_seconds() is not None else "onbekend"} seconden
- Uitgang zichtbaar: {"ja" if gs.exit_known else "nee"}
- Uitgangcoördinaat: {gs.exit_coord if gs.exit_known else "nog onbekend"}
- Huidige speler: {gs.current_player().name if gs.current_player() else "geen actieve speler"}
- Actieve items: {_bot_active_items_summary(gs)}
- Verwoeste tegels: {len(gs.destroyed_tiles)}
- Rode knop gebruikt: {gs.consensus_used_count}/{CONSENSUS_MAX_USES}
- Bonus doorgangstegels klaar: {gs.passage_bonus_tiles}

Recente spelgebeurtenissen:
{_bot_recent_events(gs)}
"""


def _bot_rule_fallback(gs: Optional[GameState], user_message: str) -> Optional[str]:
    text = _normalize_bot_rule_text(user_message)
    if not text:
        return None

    if ("juist" in text or "goed antwoord" in text or "correct" in text) and ("tegel" in text or "tegels" in text):
        return "Bij een juist antwoord mag je zelf 3 tegels leggen."

    if ("fout" in text or "niet juist" in text or "verkeerd" in text) and ("coord" in text or "tegel" in text):
        return "Bij een fout antwoord geeft de app 1 verplicht plaatsingscoördinaat. Daar moet de tegel gelegd worden."

    if ("groene" in text or "exitknop" in text or "uitgang" in text) and ("wie" in text or "mag" in text or "druk" in text or "knop" in text):
        return "Alleen de speler die aan beurt is mag de groene exitknop indrukken. De uitgang verschijnt meteen en de teller springt naar 5 minuten."

    if "consensus" in text or "groepsdilemma" in text or "rode knop" in text or "ethiekknop" in text:
        return (
            f"De rode knop kan maximaal {CONSENSUS_MAX_USES} keer per spel. Tijdens het groepsdilemma staat de klok stil. "
            f"Bij goedkeuring mag de groep een doorgang van {CONSENSUS_PASSAGE_REWARD} tegels maken; "
            f"bij afkeuring ontploffen {CONSENSUS_EXPLOSION_PENALTY} willekeurige tegels."
        )

    if "dynamiet" in text and ("ontplof" in text or "ketting" in text or "allemaal" in text):
        return (
            "Dynamiet kan onverwacht als kettingreactie ontploffen op een willekeurig moment tussen de 4e en 6e verdeelde dynamietstaaf. "
            "Dan verdwijnt alle dynamiet op het bord en bij spelers, en elke staaf op het bord maakt een holte van 2 op 2."
        )

    if "dynamiet" in text:
        return (
            "Als je dynamiet op een vak verzamelt, krijgt die speler 1 dynamiet. Later kan er een kettingreactie komen waarbij alle dynamiet tegelijk ontploft."
        )

    if "diamant" in text:
        return "Een diamant op een vak verzamelen geeft 1 diamant of infofiche aan die speler."

    if ("ranking" in text or "diamant" in text or "einde" in text) and ("meetel" in text or "tellen" in text or "buiten" in text or "ontsnapt" in text):
        return "Voor de all time ranking tellen alleen diamanten mee van spelers die op tijd ontsnappen. De ranking verschijnt pas na de explosie."

    if ("start" in text or "begin" in text) and ("diamant" in text or "dynamiet" in text):
        return "Bij de start van een spel liggen er 6 diamanten en 4 dynamietstaven op willekeurige vrije vakken."

    if "pauze" in text and ("klok" in text or "timer" in text):
        return "De pauzeknop zet de spelklok stil zonder het spel te resetten. Met dezelfde knop kan je de klok weer hervatten."

    if ("iedereen" in text and ("buiten" in text or "ontsnapt" in text)) or ("wanneer" in text and "ranking" in text):
        return "Als iedereen buiten is, springt de teller naar 0 en ontploft de mijn meteen. Daarna komt het eindresultaat en de all time ranking."

    return None


def _bot_theme_fallback(user_message: str) -> Optional[str]:
    text = _normalize_bot_rule_text(user_message)
    if not text:
        return None

    if "prompt" in text:
        if any(keyword in text for keyword in ("goed", "goede", "beste", "sterk", "sterke", "verbeter")):
            return (
                "Een sterke prompt zegt duidelijk wat je wil, voor wie het antwoord bedoeld is en in welke vorm je het wilt. "
                "Hoe concreter je vraag, hoe bruikbaarder het antwoord van AI meestal wordt."
            )
        return QUESTION_EXPLANATION_FALLBACKS["core_werking_4"]

    if "bias" in text or "bevooroordeeld" in text or "vooroordeel" in text:
        return QUESTION_EXPLANATION_FALLBACKS["core_risicos_1"]

    if "privacy" in text or "persoonlijke gegevens" in text or ("gegevens" in text and "delen" in text):
        return QUESTION_EXPLANATION_FALLBACKS["core_risicos_4"]

    if "hallucin" in text or "verzinn" in text or ("control" in text and "ai" in text):
        return QUESTION_EXPLANATION_FALLBACKS["core_risicos_2"]

    if ("bron" in text and "control" in text) or ("betrouwbare bron" in text):
        return QUESTION_EXPLANATION_FALLBACKS["core_risicos_5"]

    if "chatbot" in text:
        return (
            "Een chatbot kan snel uitleg of ideeën geven, maar je blijft best zelf nadenken en belangrijke info controleren. "
            "Gebruik zo'n antwoord dus als hulp, niet als automatische waarheid."
        )

    if "deepfake" in text or (("beeld" in text or "foto" in text or "afbeelding" in text) and ("ai" in text or "nep" in text)):
        return THEME_EXPLANATION_FALLBACKS["beeld"]

    if "kansen" in text or ("waar" in text and "helpen" in text and "ai" in text):
        return THEME_EXPLANATION_FALLBACKS["kansen"]

    if "leefwereld" in text or "dagelijks leven" in text or ("app" in text and "ai" in text):
        return THEME_EXPLANATION_FALLBACKS["leefwereld"]

    if "beeldthema" in text or "beeldvraag" in text or ("foto" in text and "herken" in text):
        return THEME_EXPLANATION_FALLBACKS["beeld"]

    if "kritisch" in text or "risico" in text or "verantwoord" in text or ("veilig" in text and "ai" in text):
        return THEME_EXPLANATION_FALLBACKS["kritisch"]

    if ("hoe werkt" in text and "ai" in text) or ("werkt ai" in text) or "thema werking" in text:
        return THEME_EXPLANATION_FALLBACKS["werking"]

    return None


def _bot_local_fallback(gs: Optional[GameState], user_message: str) -> Optional[str]:
    return _bot_rule_fallback(gs, user_message) or _bot_theme_fallback(user_message)


def _bot_intro_reply() -> str:
    return (
        "Aico helpt al voor de start. Je kan iets vragen over spelregels, prompts, bias, privacy, broncontrole, "
        "chatbots of AI-foto's."
    )

def _bot_system_prompt(gs: GameState) -> str:
    """
    Aico: spelleider + regel-uitleg + korte coaching, zonder AI-verwijzingen.
    """
    remaining = gs.remaining_seconds()
    remaining_str = f"{remaining//60}:{remaining%60:02d}" if remaining is not None else "onbekend"
    phase = gs.phase
    exit_info = gs.exit_coord if gs.exit_known else "nog onbekend"
    cp = gs.current_player()
    cp_name = cp.name if cp else "geen"

    return f"""
Je bent Aico, een speelse maar duidelijke spelleider van De diamantmijn voor 12-jarigen.
Je helpt met spelregels, volgende stappen en korte verduidelijking van infokaarten.
Je blijft thema-neutraal: je verwijst NIET naar AI of technologie, tenzij de speler dat expliciet als thema gekozen heeft.

Harde regels:
- Houd antwoorden kort (meestal 1-4 zinnen).
- Gebruik altijd eerst de officiële spelregels hieronder; die gaan boven je eigen gokwerk.
- Als de speler een exacte regel of aantal vraagt, geef het exacte antwoord uit de regels.
- Als iets niet in de regels staat, zeg eerlijk dat de leerkracht of het fysieke bord dat bevestigt.
- Geef geen 'optimale zet' die het spel oplost; je mag wel opties benoemen.
- Als een vraag over de regels gaat: geef een duidelijk JA/NEE + 1 zin uitleg.
- Als iets onduidelijk is omdat het fysieke bord niet in de app zit: zeg wat je nodig hebt (bv. coordinaat) of zeg dat de leerkracht bevestigt.

Huidige spelstatus:
- Fase: {phase}
- Resterende tijd: {remaining_str}
- Huidige speler: {cp_name}
- Uitgang: {exit_info}
- Spelers: {", ".join([p.name + ("(ontsnapt)" if p.escaped else "") for p in gs.players])}

Officiële regels:
{_bot_rulebook(gs)}
"""

@app.post("/api/chat", response_model=dict)
async def chat(
    req: ChatRequest,
    x_teacher_password: Optional[str] = Header(None),
    x_ai_owner_password: Optional[str] = Header(None),
    x_game_session: Optional[str] = Header(None),
):
    session_id = normalize_game_session_id(x_game_session)
    async with STATE_LOCK:
        gs = get_game_state(session_id)

        # Minimal context: player inventory if player_id is provided
        player_ctx = ""
        if gs is not None and req.player_id:
            p = next((x for x in gs.players if x.id == req.player_id), None)
            if p:
                player_ctx = f"\nSpelercontext: {p.name}, diamanten={p.info_cards}, dynamiet={p.dynamite}, ontsnapt={p.escaped}\n"

    # Call model outside lock to avoid blocking game loop
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(400, "Bericht mag niet leeg zijn.")

    fallback_reply = _bot_local_fallback(gs, user_msg)
    if fallback_reply:
        async with STATE_LOCK:
            current_state = get_game_state(session_id)
            if current_state is not None:
                _log(current_state, f"Aico regelantwoord op '{user_msg[:40]}...': {fallback_reply[:60]}...")
        return {"reply": fallback_reply}

    if gs is None:
        return {"reply": _bot_intro_reply()}

    client = (
        get_openai_client(allow_server_key=has_valid_ai_owner_password(x_ai_owner_password))
        if has_valid_teacher_password(x_teacher_password)
        else None
    )
    if client is None:
        return {
            "reply": (
                "Aico geeft nu snelle lokale hulp. Vraag zo concreet mogelijk naar een spelregel of een AI-thema zoals prompts, bias, privacy of broncontrole."
            )
        }

    sys_prompt = _bot_system_prompt(gs) + player_ctx

    try:
        resp = client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.2,
            timeout=8.0,
        )
        reply = (resp.choices[0].message.content or "").strip()
        if not reply:
            reply = "Ik heb daar nu even geen goed antwoord op."

        # Log bot interaction briefly
        async with STATE_LOCK:
            current_state = get_game_state(session_id)
            if current_state is not None:
                _log(current_state, f"Aico antwoordt op '{user_msg[:40]}...': {reply[:60]}...")
        return {"reply": reply}
    except Exception:
        return {
            "reply": (
                _bot_theme_fallback(user_msg)
                or "Ik geraak nu niet aan de uitgebreide chat. Vraag gerust concreet naar een spelregel, prompt, bias, privacy of broncontrole."
            )
        }
