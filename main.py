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
from difflib import SequenceMatcher
from typing import Dict, List, Optional, Literal, Tuple

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field
import json
from pathlib import Path

DATA_DIR = Path("data")
CORE_FILE = DATA_DIR / "core_questions.json"
IMAGE_FILE = DATA_DIR / "image_questions.json"
CONSENSUS_FILE = DATA_DIR / "consensus_dilemmas.json"
QUESTION_IMAGE_DIR = Path("static") / "question-images"
UPLOADED_IMAGE_DIR = QUESTION_IMAGE_DIR / "uploads"
GENERATED_IMAGE_DIR = QUESTION_IMAGE_DIR / "generated"
IMAGE_QUESTION_CHANCE = 0.3
AI_GENERATION_MAX_ATTEMPTS = 4
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
    "Waarschijnlijk AI-gegenereerd",
    "Waarschijnlijk niet AI-gegenereerd",
]
AUTO_IMAGE_QUESTION_VARIANTS = [
    "Werd deze foto door AI gegenereerd of niet?",
    "Is dit beeld AI-gegenereerd of niet?",
    "Kijk goed: is deze foto waarschijnlijk met AI gemaakt of niet?",
]
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
    "risicos": {
        "label": "Risico's en valkuilen",
        "color": "#E74C3C"
    },
    "verantwoord": {
        "label": "Verantwoord gebruik",
        "color": "#F39C12"
    }
}
ETHICAL_AI_DILEMMAS = [
    {
        "id": "ethics_1",
        "question": "Een leerling laat een AI bijna een volledige boekbespreking schrijven en past daarna alleen enkele zinnen aan. Is het eerlijk om dat werk als volledig eigen werk in te dienen? Waarom wel of niet?",
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
# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "double diamond").strip()

# OpenAI client (BavoBot Full)
# Works with the "openai" python package (new style client).
try:
    from openai import OpenAI, APIConnectionError, APIStatusError, BadRequestError
    _client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    QUESTION_GENERATION_MODEL = os.getenv("OPENAI_QUESTION_MODEL", "gpt-4.1-mini")
    IMAGE_GENERATION_MODEL = os.getenv("OPENAI_IMAGE_MODEL", "gpt-image-1.5").strip() or "gpt-image-1.5"
    IMAGE_ANALYSIS_MODEL = os.getenv("OPENAI_IMAGE_ANALYSIS_MODEL", QUESTION_GENERATION_MODEL).strip() or QUESTION_GENERATION_MODEL
    IMAGE_GENERATION_QUALITY = os.getenv("OPENAI_IMAGE_QUALITY", "medium").strip() or "medium"
    IMAGE_GENERATION_SIZE = os.getenv("OPENAI_IMAGE_SIZE", "1024x1024").strip() or "1024x1024"
    THEME_GENERATION_GUIDANCE = {
        "werking": """
Focus op hoe AI werkt: data, patronen, voorspellen, trainen, prompten, voorbeelden en beperkingen.
Maak liever een denkvraag of korte praktijksituatie dan een losse definitiesvraag.
""".strip(),
        "leefwereld": """
Focus op situaties uit school, sociale media, zoeken, navigatie, aanbevelingen, beeld of chatbots.
Laat leerlingen nadenken waar AI wel of niet nuttig is in het dagelijks leven.
""".strip(),
        "risicos": """
Focus op bias, hallucinaties, nepbeelden, privacy, verkeerde conclusies en blind vertrouwen in AI.
Maak afleiders geloofwaardig, niet flauw of absurd.
""".strip(),
        "verantwoord": """
Focus op eerlijk gebruik, controleren van informatie, brongebruik, transparantie, privacy en afspraken in de klas.
Laat de vraag gaan over goede keuzes, niet alleen over losse regeltjes.
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
- laat leerlingen nadenken in plaats van alleen een woordje herkennen
- gebruik liefst een korte situatie, vergelijking of redenering
- vermijd té simpele vragen zoals losse woordbetekenissen zonder context
- vermijd onzinnige opties zoals "omdat AI slaapt" of "omdat een robot liegt"

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
    _client = None
    IMAGE_ANALYSIS_MODEL = "gpt-4.1-mini"
    APIConnectionError = Exception
    APIStatusError = Exception
    BadRequestError = Exception


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

def load_core_questions():
    return load_questions_from_file(CORE_FILE)


def load_image_questions():
    return load_questions_from_file(IMAGE_FILE)


def load_consensus_dilemmas():
    return load_questions_from_file(CONSENSUS_FILE)


def load_questions_from_file(path: Path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


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


def save_core_questions(questions):
    save_questions_to_file(CORE_FILE, questions)


def save_image_questions(questions):
    save_questions_to_file(IMAGE_FILE, questions)


def save_consensus_dilemmas(questions):
    save_questions_to_file(CONSENSUS_FILE, questions)


def save_questions_to_file(path: Path, questions):
    with open(path, "w", encoding="utf-8") as f:
        json.dump(questions, f, indent=2, ensure_ascii=False)


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
) -> str:
    fallback = (
        "Dit beeld is AI-gegenereerd. Kijk extra naar kleine details zoals handen, texturen, "
        "schaduwen, symmetrie en elementen die net niet logisch in elkaar passen."
    )

    if _client is None or not image_bytes:
        return fallback

    try:
        response = _client.chat.completions.create(
            model=IMAGE_ANALYSIS_MODEL,
            response_format={"type": "json_object"},
            temperature=0.2,
            messages=[
                {
                    "role": "system",
                    "content": (
                        "Je helpt een leerkracht bij een beeldvraag over AI-beelden voor leerlingen van 12 tot 14 jaar. "
                        "De afbeelding is al zeker AI-gegenereerd. "
                        "Geef 1 of 2 korte Nederlandse zinnen die uitleggen welke zichtbare details leerlingen zouden kunnen opmerken "
                        "om te vermoeden dat het beeld door AI gemaakt is. "
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
        "Keep the composition natural and slightly imperfect. "
        "Do not add text overlays, watermarks, collages, split screens or user interface elements. "
        "If people appear, keep anatomy and proportions realistic."
    )


def generate_ai_mix_image(scene: dict, focus: str = "") -> dict:
    if _client is None:
        raise HTTPException(500, "OpenAI client niet beschikbaar.")

    prompt = build_auto_image_prompt(scene, focus)

    try:
        response = _client.images.generate(
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
        ),
    }


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
        "display_theme": "Beeldronde",
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
        if str(question.get("type") or "") != "image_binary":
            continue
        if not question.get("approved", True) or question.get("rejected", False):
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
    "risicos": "Dit laat zien waarom je AI niet blind mag vertrouwen: systemen kunnen zich vergissen, bevooroordeeld zijn of nepinhoud overtuigend laten lijken.",
    "verantwoord": "Verantwoord AI-gebruik betekent dat je controleert, eerlijk blijft over hulp van AI en zelf blijft nadenken over privacy, betrouwbaarheid en gevolgen.",
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


def build_question_payload(question: dict, fallback_theme: str) -> dict:
    question_type = str(question.get("type") or "multiple_choice")
    is_image_question = question_type == "image_binary"
    fallback_theme_label = THEMES.get(fallback_theme, {}).get("label", fallback_theme)

    if is_image_question:
        instruction = (
            question.get("instruction")
            or "Kijk goed naar het beeld en kies of het waarschijnlijk door AI gemaakt is of niet."
        )
        eyebrow = question.get("eyebrow") or "Beeldvraag"
    else:
        instruction = (
            question.get("instruction")
            or "Kies het beste antwoord. Bij een fout krijg je een plaatsingscoordinaat."
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

    if question.get("image_url"):
        payload["image_url"] = question["image_url"]

    if question.get("image_alt"):
        payload["image_alt"] = question["image_alt"]

    return payload


def build_manageable_question_summary(
    question: dict,
    store: Literal["core", "image", "consensus"],
) -> dict:
    default_type = "consensus_dilemma" if store == "consensus" else "multiple_choice"
    question_type = str(question.get("type") or default_type)
    theme_key = str(question.get("theme") or "")

    if question_type == "image_binary":
        fallback_theme_label = "Beeldronde"
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
        payload["correct_label"] = (
            "Waarschijnlijk AI-gegenereerd"
            if question.get("correct_index") == 0
            else "Waarschijnlijk niet AI-gegenereerd"
        )
    elif question_type == "consensus_dilemma":
        payload["guidance"] = str(question.get("guidance") or "").strip()
    else:
        payload["options"] = list(question.get("options") or [])
        payload["correct_label"] = answer_label_from_index(question.get("correct_index"))

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
        if correct_text:
            return (
                f"Het juiste antwoord is: {correct_text}. "
                "Let op details zoals handen, tekst, schaduwen, verhoudingen en andere onmogelijke elementen."
            )
        return "Let op details zoals handen, tekst, schaduwen, verhoudingen en andere onmogelijke elementen."

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
    built_in = []
    for dilemma in ETHICAL_AI_DILEMMAS:
        entry = dict(dilemma)
        entry["type"] = "consensus_dilemma"
        entry["display_theme"] = entry.get("display_theme") or "Groepsdilemma"
        entry["source"] = entry.get("source") or "system"
        built_in.append(entry)

    custom = []
    for dilemma in load_consensus_dilemmas():
        entry = dict(dilemma)
        entry["type"] = "consensus_dilemma"
        entry["display_theme"] = entry.get("display_theme") or "Groepsdilemma"
        entry["source"] = entry.get("source") or "teacher"
        custom.append(entry)

    return built_in + custom


def load_removable_questions() -> List[dict]:
    removable: List[dict] = []

    for question in load_core_questions():
        if question.get("source") != "teacher":
            continue
        removable.append(build_manageable_question_summary(question, "core"))

    for question in load_image_questions():
        removable.append(build_manageable_question_summary(question, "image"))

    for dilemma in load_consensus_dilemmas():
        removable.append(build_manageable_question_summary(dilemma, "consensus"))

    removable.reverse()
    return removable


def delete_removable_question(question_id: str) -> bool:
    core_questions = load_core_questions()
    for index, question in enumerate(core_questions):
        if question.get("id") != question_id:
            continue
        if question.get("source") != "teacher":
            raise HTTPException(403, "Deze vraag kan niet via de app verwijderd worden.")
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
            save_questions(questions)
            return question

    return None


def normalize_question_options(options: List[str]) -> List[str]:
    normalized = [str(option).strip() for option in options]
    if len(normalized) != 4 or any(not option for option in normalized):
        raise HTTPException(400, "Een vraag moet exact 4 niet-lege antwoordopties hebben.")
    return normalized


def stable_ai_correct_index(question: dict) -> int:
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


def rebalance_ai_question_answer_positions() -> List[dict]:
    questions = load_core_questions()
    if not questions:
        return []

    changed = False

    for question in questions:
        if question.get("source") != "ai":
            continue
        if question.get("rejected", False):
            continue
        if str(question.get("type") or "multiple_choice") != "multiple_choice":
            continue

        target_index = stable_ai_correct_index(question)
        if move_correct_option_to_index(question, target_index):
            changed = True

    if changed:
        save_core_questions(questions)

    return questions


def require_teacher_password(x_teacher_password: Optional[str]) -> None:
    if not TEACHER_PASSWORD:
        raise HTTPException(500, "Er is geen leerkrachtpaswoord ingesteld.")

    provided_password = (x_teacher_password or "").strip()
    if provided_password != TEACHER_PASSWORD:
        raise HTTPException(401, "Onjuist leerkrachtpaswoord.")


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


class SpawnItem(BaseModel):
    kind: Literal["diamond", "dynamite"]
    coord: Coord
    spawned_at: float


class GameState(BaseModel):
    game_id: str
    phase: Phase = "setup"

    # Timing
    started_at: Optional[float] = None
    deadline_at: Optional[float] = None  # explosion moment
    auto_exit_reveal_at: Optional[float] = None  # time when exit becomes visible automatically (25 min)
    timer_paused: bool = False
    paused_at: Optional[float] = None

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


class ActionResponse(BaseModel):
    ok: bool
    message: str
    state: GameState


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
    theme: Optional[Literal["werking", "leefwereld", "risicos", "verantwoord"]] = None
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


class ConsensusEvaluationRequest(BaseModel):
    decision: Literal["approve", "reject"]


# ----------------------------
# App + In-memory state
# ----------------------------

app = FastAPI(title="Uit de Steengroeve - Game API (MVP)")
from fastapi.responses import FileResponse

@app.get("/")
def serve_index():
    return FileResponse("static/index.html")
app.mount("/static", StaticFiles(directory="static"), name="static")

STATE_LOCK = asyncio.Lock()
STATE: Optional[GameState] = None
LAST_IMAGE_QUESTION = False

# Global config for current game (stored for the loop)
CONFIG: Dict[str, int] = {
    "timer_minutes": 30,
    "auto_exit_reveal_minute": 25,
    "emergency_endgame_minutes": 5,
    "diamond_spawn_min_seconds": 150,
    "diamond_spawn_max_seconds": 270,
    "diamond_max_simultaneous": 2,
    "dynamite_spawn_min_seconds": 210,
    "dynamite_spawn_max_seconds": 360,
    "dynamite_max_simultaneous": 3,
}
DEFAULT_RANDOM_SPAWN_CONFIG = {
    "diamond_spawn_min_seconds": 150,
    "diamond_spawn_max_seconds": 270,
    "diamond_max_simultaneous": 2,
    "dynamite_spawn_min_seconds": 210,
    "dynamite_spawn_max_seconds": 360,
    "dynamite_max_simultaneous": 3,
}
@app.post("/api/tile/auto_place")
async def auto_place_tile():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")

        gs = STATE
        coord = random_empty_coord(gs.occupied_coords(include_start_coords=True))

        _log(gs, f"Fout antwoord. Tegel moet geplaatst worden op {coord}.")

        return {"coord": coord}
# ----------------------------
# Core game functions
# ----------------------------

def _log(gs: GameState, msg: str) -> None:
    stamp = time.strftime("%H:%M:%S")
    gs.event_log.append(f"[{stamp}] {msg}")

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


def _pause_game_clock(gs: GameState, paused_at: Optional[float] = None) -> None:
    if gs.timer_paused:
        return
    gs.timer_paused = True
    gs.paused_at = paused_at or time.time()


def _resume_game_clock(gs: GameState, resumed_at: Optional[float] = None) -> float:
    if not gs.timer_paused or gs.paused_at is None:
        return 0.0

    resume_time = resumed_at or time.time()
    pause_duration = max(0.0, resume_time - gs.paused_at)

    gs.deadline_at = _shift_timer_value(gs.deadline_at, pause_duration)
    gs.auto_exit_reveal_at = _shift_timer_value(gs.auto_exit_reveal_at, pause_duration)
    gs.next_diamond_spawn_at = _shift_timer_value(gs.next_diamond_spawn_at, pause_duration)
    gs.next_dynamite_spawn_at = _shift_timer_value(gs.next_dynamite_spawn_at, pause_duration)
    gs.timer_paused = False
    gs.paused_at = None

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
        return
    escaped.sort(key=lambda p: (-p.info_cards, p.escaped_at or 10**18))
    winner = escaped[0]
    _log(gs, f"Winnaar: {winner.name} (infokaarten: {winner.info_cards}).")
    gs.phase = "finished"


def _schedule_next_spawn(kind: Literal["diamond", "dynamite"], now: Optional[float] = None) -> float:
    base_time = now if now is not None else time.time()
    min_key = f"{kind}_spawn_min_seconds"
    max_key = f"{kind}_spawn_max_seconds"
    return base_time + random.randint(CONFIG[min_key], CONFIG[max_key])


def _spawn_random_item(gs: GameState, kind: Literal["diamond", "dynamite"], max_simultaneous: int, now: float) -> bool:
    existing = [it for it in gs.items if it.kind == kind]
    if len(existing) >= max_simultaneous:
        return False

    coord = random_empty_coord(gs.occupied_coords(include_start_coords=True))
    gs.items.append(SpawnItem(kind=kind, coord=coord, spawned_at=now))

    label = "Diamant" if kind == "diamond" else "Dynamiet"
    _log(gs, f"ALARM: {label} leggen op {coord}.")
    return True


# ----------------------------
# Background loop
# ----------------------------

@app.on_event("startup")
async def startup_loop():
    asyncio.create_task(game_loop())

async def game_loop():
    global STATE
    while True:
        await asyncio.sleep(0.5)
        async with STATE_LOCK:
            if STATE is None:
                continue
            gs = STATE
            if gs.phase not in ("running", "endgame"):
                continue

            if gs.timer_paused:
                continue

            now = time.time()

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
async def new_game(req: NewGameRequest):
    global STATE, CONFIG, LAST_IMAGE_QUESTION
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
    gs = GameState(
        game_id=game_id,
        phase="running",
        started_at=now,
        deadline_at=now + req.timer_minutes * 60,
        auto_exit_reveal_at=now + req.auto_exit_reveal_minute * 60,
        next_diamond_spawn_at=_schedule_next_spawn("diamond", now),
        next_dynamite_spawn_at=_schedule_next_spawn("dynamite", now),
        players=players,
        turn_index=0,
    )
    reset_questions()
    LAST_IMAGE_QUESTION = False

    CONFIG = {
        "timer_minutes": req.timer_minutes,
        "auto_exit_reveal_minute": req.auto_exit_reveal_minute,
        "emergency_endgame_minutes": req.emergency_endgame_minutes,
        **DEFAULT_RANDOM_SPAWN_CONFIG,
    }

    _log(gs, f"Nieuw spel gestart met {len(players)} spelers. Timer: {req.timer_minutes} min.")
    for p in players:
        _log(gs, f"Startcoordinaat {p.name}: {p.start_coord}")

    async with STATE_LOCK:
        STATE = gs

    return ActionResponse(ok=True, message="Spel gestart.", state=gs)

@app.post("/api/question/next")
async def next_question(payload: dict):
    global LAST_IMAGE_QUESTION
    theme_key = payload.get("theme")

    if theme_key not in THEMES:
        raise HTTPException(400, "Ongeldig thema.")

    core_questions = rebalance_ai_question_answer_positions()
    available_questions = [
        q for q in core_questions
        if q.get("theme") == theme_key
        and not q.get("used", False)
        and q.get("approved", True)
    ]
    available_image_questions = [
        q for q in load_image_questions()
        if not q.get("used", False)
        and q.get("approved", True)
    ]

    selected_question = None

    if (
        available_image_questions
        and not LAST_IMAGE_QUESTION
        and random.random() < IMAGE_QUESTION_CHANCE
    ):
        selected_question = random.choice(available_image_questions)
    elif available_questions:
        selected_question = random.choice(available_questions)
    elif available_image_questions:
        selected_question = random.choice(available_image_questions)

    if selected_question:
        LAST_IMAGE_QUESTION = selected_question.get("type") == "image_binary"
        return build_question_payload(selected_question, theme_key)

    return {"message": "Geen beschikbare vragen meer voor dit thema of de beeldrondes."}
@app.post("/api/question/generate")
async def generate_ai_question(theme: str, x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)

    if theme not in THEMES:
        raise HTTPException(400, "Ongeldig thema.")

    if _client is None:
        raise HTTPException(500, "OpenAI client niet beschikbaar.")

    try:
        questions = prune_duplicate_pending_ai_questions()
        rejected_variants: List[str] = []
        duplicate_match: Optional[dict] = None

        for _attempt in range(AI_GENERATION_MAX_ATTEMPTS):
            avoid_list = build_generation_avoid_list(questions, theme, rejected_variants)
            duplicate_instruction = ""
            if avoid_list:
                duplicate_instruction = (
                    "Maak GEEN vraag die inhoudelijk hetzelfde is als of sterk lijkt op een van deze bestaande of afgekeurde vragen:\n"
                    f"{avoid_list}\n\n"
                    "Kies dus bewust een andere invalshoek, situatie of redenering.\n\n"
                )

            resp = _client.chat.completions.create(
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
                            f"Extra richtlijnen voor dit thema:\n{THEME_GENERATION_GUIDANCE[theme]}\n\n"
                            f"{duplicate_instruction}"
                            "Maak 1 inhoudelijke meerkeuzevraag die leerlingen echt laat nadenken. "
                            "Gebruik gewone taal, maar maak de vraag niet flauw of te simplistisch. "
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

            duplicate_match = find_similar_question(ai_question, questions)
            if duplicate_match is not None:
                rejected_variants.append(ai_question["question"])
                continue

            ai_question["id"] = next_ai_question_id(questions)
            move_correct_option_to_index(ai_question, stable_ai_correct_index(ai_question))
            ai_question["explanation"] = learning_explanation_text(ai_question)
            questions.append(ai_question)
            save_core_questions(questions)
            return ai_question

        if duplicate_match is not None:
            raise HTTPException(
                409,
                "AI blijft te gelijkaardige vragen voorstellen. Probeer opnieuw voor meer variatie."
            )

        raise HTTPException(500, "AI vraag kon niet uniek genoeg gegenereerd worden.")

    except HTTPException:
        raise
    except Exception as e:
        print("AI generation error:", e)
        raise HTTPException(500, "AI vraag kon niet gegenereerd worden.")
@app.post("/api/question/answer")
async def answer_question(payload: dict):
    question_id = payload.get("id")
    chosen_index = payload.get("chosen_index")

    question = mark_question_used(question_id)
    if question is not None:
        correct_index = question["correct_index"]
        correct_option = correct_option_text(question)
        return {
            "correct": chosen_index == correct_index,
            "correct_index": correct_index,
            "correct_option": correct_option,
            "correct_label": answer_label_from_index(correct_index),
            "explanation": learning_explanation_text(question),
        }

    raise HTTPException(404, "Vraag niet gevonden.")


@app.post("/api/consensus/start")
async def start_consensus_challenge():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")

        gs = STATE
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
        _pause_game_clock(gs)
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
):
    require_teacher_password(x_teacher_password)

    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")

        gs = STATE
        if not gs.consensus_active or not gs.consensus_question:
            raise HTTPException(400, "Er is momenteel geen actieve ethische groepsvraag.")

        destroyed_tiles: List[Coord] = []
        removed_items: List[SpawnItem] = []
        question_text = gs.consensus_question
        pause_duration = _resume_game_clock(gs)

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
async def get_state():
    async with STATE_LOCK:
        if STATE is None:
            return None
        return STATE


@app.get("/api/teacher/auth-check")
async def teacher_auth_check(x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)
    return {"ok": True}


@app.get("/api/question/pending")
async def pending_questions(x_teacher_password: Optional[str] = Header(None)):
    require_teacher_password(x_teacher_password)

    questions = prune_duplicate_pending_ai_questions()

    pending = [
        q for q in questions
        if q.get("approved") is False and not q.get("rejected", False)
    ]

    return pending


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
        question["approved"] = True
        question["rejected"] = False

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
):
    require_teacher_password(x_teacher_password)

    focus = str(payload.focus or "").strip()
    existing_image_questions = load_image_questions()
    real_candidates = unique_real_image_candidates(existing_image_questions)
    local_ai_candidates = unique_ai_image_candidates(existing_image_questions)

    if not real_candidates:
        raise HTTPException(
            400,
            "Voeg eerst minstens een echte beeldvraag toe, zodat de automatische beeldmix ook een niet-AI-foto kan gebruiken.",
        )

    real_count = 1
    target_ai_count = payload.count - real_count
    if target_ai_count <= 0:
        raise HTTPException(400, "De automatische beeldmix heeft minstens een AI-beeld nodig.")

    selected_real_questions = random.sample(real_candidates, k=real_count)
    selected_scenes = choose_auto_image_scene_seeds(target_ai_count)

    new_questions: List[dict] = []
    preview_questions: List[dict] = [
        build_auto_image_preview_item(selected_real_questions[0], "bestaand")
    ]
    working_questions = list(existing_image_questions)
    generated_ai_count = 0
    fallback_ai_count = 0
    openai_failed = False

    for scene in selected_scenes:
        if openai_failed or _client is None:
            break

        try:
            generated_image = generate_ai_mix_image(scene, focus)
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
                "Kijk bij zulke foto's extra naar kleine details, texturen, schaduwen en onwaarschijnlijke elementen."
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
            copied_ai_question = build_auto_image_question(
                working_questions,
                correct_index=0,
                image_url=str(ai_question.get("image_url") or "").strip(),
                image_alt=str(ai_question.get("image_alt") or "").strip() or "AI-beeld in de automatische beeldmix",
                explanation=learning_explanation_text(ai_question),
                source=str(ai_question.get("source") or "auto"),
            )
            working_questions.append(copied_ai_question)
            new_questions.append(copied_ai_question)
            preview_questions.append(copied_ai_question)
            fallback_ai_count += 1

    existing_image_questions.extend(new_questions)
    save_image_questions(existing_image_questions)

    ai_total = generated_ai_count + fallback_ai_count
    ai_suffix = "AI-beeld" if ai_total == 1 else "AI-beelden"
    generation_note = ""
    if generated_ai_count and fallback_ai_count:
        generation_note = (
            f" {generated_ai_count} {('AI-beeld' if generated_ai_count == 1 else 'AI-beelden')} "
            "zijn nieuw gegenereerd; de rest komt uit de lokale beeldpool."
        )
    elif generated_ai_count:
        generation_note = " Alle AI-beelden zijn nieuw gegenereerd via OpenAI."
    elif fallback_ai_count:
        generation_note = " De AI-beelden voor deze mix komen uit de bestaande lokale beeldpool."

    return {
        "ok": True,
        "message": (
            f"Automatische beeldmix opgeslagen: 1 bestaande echte foto en {len(new_questions)} nieuwe {ai_suffix}."
            f"{generation_note}"
        ),
        "real_count": real_count,
        "ai_count": ai_total,
        "generated_ai_count": generated_ai_count,
        "fallback_ai_count": fallback_ai_count,
        "questions": preview_questions,
        "saved_count": len(new_questions),
        "preview_message": (
            f"De mix hieronder gebruikt 1 bestaande echte foto en {len(new_questions)} nieuwe {ai_suffix.lower()}."
            " Alleen de nieuwe AI-vragen worden extra toegevoegd onder 'Vragen verwijderen'."
        ),
    }


@app.post("/api/question/manual")
async def create_teacher_question(
    payload: TeacherQuestionCreateRequest,
    x_teacher_password: Optional[str] = Header(None),
):
    require_teacher_password(x_teacher_password)

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
            raise HTTPException(400, "Kies bij een beeldvraag of het beeld AI-gegenereerd is of niet.")

        image_questions = load_image_questions()
        teacher_question = {
            "id": next_prefixed_question_id(image_questions, "image_round_"),
            "source": "teacher",
            "type": "image_binary",
            "display_theme": "Beeldronde",
            "question": normalized_question,
            "options": list(IMAGE_BINARY_OPTIONS),
            "correct_index": payload.correct_index,
            "image_url": image_url,
            "image_alt": str(payload.image_alt or "").strip() or "Beeld bij de vraag",
            "explanation": str(payload.explanation or "").strip(),
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
        "theme": payload.theme,
        "source": "teacher",
        "question": normalized_question,
        "options": normalized_options,
        "correct_index": payload.correct_index,
        "approved": True,
        "rejected": False,
        "used": False,
    }

    questions.append(teacher_question)
    save_core_questions(questions)

    return {
        "ok": True,
        "message": "Eigen vraag opgeslagen en meteen toegevoegd aan het spel.",
        "question": teacher_question,
    }
    
@app.post("/api/next_turn", response_model=ActionResponse)
async def next_turn():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, f"Spel is niet actief (phase={gs.phase}).")

        # Advance to next non-escaped player
        for _ in range(len(gs.players)):
            gs.turn_index = (gs.turn_index + 1) % len(gs.players)
            if not gs.players[gs.turn_index].escaped:
                break

        cp = gs.current_player()
        if cp is None:
            _log(gs, "Alle spelers zijn ontsnapt. Spel eindigt.")
            gs.phase = "finished"
            return ActionResponse(ok=True, message="Alle spelers ontsnapt. Einde spel.", state=gs)

        _log(gs, f"Beurt: {cp.name}")
        return ActionResponse(ok=True, message=f"Aan beurt: {cp.name}", state=gs)


@app.post("/api/spawn", response_model=ActionResponse)
async def spawn_item(req: SpawnRequest):
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
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
        return ActionResponse(ok=True, message=f"{req.kind} op {coord}", state=gs)


@app.post("/api/item/remove", response_model=ActionResponse)
async def remove_item(req: RemoveItemRequest):
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE

        try:
            parse_coord(req.coord)
        except ValueError as e:
            raise HTTPException(400, str(e))

        item = next((it for it in gs.items if it.coord == req.coord), None)
        if item is None:
            return ActionResponse(ok=False, message="Geen actief item op dit coordinaat.", state=gs)

        gs.items.remove(item)
        label = "Diamant" if item.kind == "diamond" else "Dynamiet"
        _log(gs, f"{label} op {req.coord} verwijderd uit de app-lijst.")
        return ActionResponse(ok=True, message=f"{label} op {req.coord} verwijderd.", state=gs)


@app.post("/api/reveal_exit", response_model=ActionResponse)
async def reveal_exit_manual():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
        if gs.phase not in ("running", "endgame"):
            raise HTTPException(400, "Spel is niet actief.")
        _reveal_exit(gs, reason="handmatig")
        return ActionResponse(ok=True, message=f"Uitgang: {gs.exit_coord}", state=gs)


@app.post("/api/emergency/{player_id}", response_model=ActionResponse)
async def press_emergency(player_id: str):
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
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
        gs.emergency_pressed = True
        gs.emergency_pressed_by = player_id
        gs.emergency_pressed_at = time.time()
        gs.phase = "endgame"

        _reveal_exit(gs, reason=f"groene exitknop door {current_player.name}")

        gs.deadline_at = time.time() + CONFIG["emergency_endgame_minutes"] * 60
        _log(
            gs,
            f"GROENE EXITKNOP ingedrukt door {current_player.name}. "
            f"Explosie over {CONFIG['emergency_endgame_minutes']} min."
        )
        _log(gs, "Regel: groene exitknop indrukken = beurt en uitgang wordt meteen onthuld.")

        return ActionResponse(ok=True, message="Groene exitknop geactiveerd. Eindfase gestart.", state=gs)


@app.post("/api/collect/{player_id}", response_model=ActionResponse)
async def collect_on_tile(player_id: str, coord: Coord):
    """
    Semi-manual helper:
    Call this when a player ends movement on a coord.
    If there's a diamond/dynamite there, it's collected.
    For diamonds: +1 info card
    For dynamite: +1 dynamite
    """
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
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
            if it.kind == "diamond":
                player.info_cards += 1
                _log(gs, f"{player.name} verzamelt DIAMANT op {coord} -> +1 infofiche (totaal {player.info_cards}).")
            elif it.kind == "dynamite":
                player.dynamite += 1
                _log(gs, f"{player.name} verzamelt DYNAMIET op {coord} -> +1 (totaal {player.dynamite}).")
            gs.items.remove(it)

        return ActionResponse(ok=True, message="Verzameld.", state=gs)


@app.post("/api/escape/{player_id}", response_model=ActionResponse)
async def player_escape(player_id: str, coord: Optional[Coord] = None):
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
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
        return ActionResponse(ok=True, message=f"{player.name} ontsnapt.", state=gs)


# ----------------------------
# BavoBot Full: Chat endpoint
# ----------------------------

def _bot_system_prompt(gs: GameState) -> str:
    """
    BavoBot Full: spelleider + regel-uitleg + korte coaching, zonder AI-verwijzingen.
    """
    remaining = gs.remaining_seconds()
    remaining_str = f"{remaining//60}:{remaining%60:02d}" if remaining is not None else "onbekend"
    phase = gs.phase
    exit_info = gs.exit_coord if gs.exit_known else "nog onbekend"
    cp = gs.current_player()
    cp_name = cp.name if cp else "geen"

    return f"""
Je bent BavoBot, een speelse maar duidelijke spelleider voor 12-jarigen.
Je helpt met spelregels, volgende stappen en korte verduidelijking van infokaarten.
Je blijft thema-neutraal: je verwijst NIET naar AI of technologie, tenzij de speler dat expliciet als thema gekozen heeft.

Harde regels:
- Houd antwoorden kort (meestal 1-4 zinnen).
- Geef geen 'optimale zet' die het spel oplost; je mag wel opties benoemen.
- Als een vraag over de regels gaat: geef een duidelijk JA/NEE + 1 zin uitleg.
- Als iets onduidelijk is omdat het fysieke bord niet in de app zit: zeg wat je nodig hebt (bv. coordinaat) of zeg dat de leerkracht bevestigt.

Huidige spelstatus:
- Fase: {phase}
- Resterende tijd: {remaining_str}
- Huidige speler: {cp_name}
- Uitgang: {exit_info}
- Spelers: {", ".join([p.name + ("(ontsnapt)" if p.escaped else "") for p in gs.players])}
"""

@app.post("/api/chat", response_model=dict)
async def chat(req: ChatRequest):
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE

        # If no OpenAI key/client, return a safe fallback
        if _client is None:
            return {"reply": "BavoBot is nog niet gekoppeld. Vraag de leerkracht om hulp of probeer later opnieuw."}

        # Minimal context: player inventory if player_id is provided
        player_ctx = ""
        if req.player_id:
            p = next((x for x in gs.players if x.id == req.player_id), None)
            if p:
                player_ctx = f"\nSpelercontext: {p.name}, infofiches={p.info_cards}, dynamiet={p.dynamite}, ontsnapt={p.escaped}\n"

    # Call model outside lock to avoid blocking game loop
    user_msg = req.message.strip()
    if not user_msg:
        raise HTTPException(400, "Bericht mag niet leeg zijn.")

    sys_prompt = _bot_system_prompt(gs) + player_ctx

    try:
        resp = _client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.7
        )
        reply = (resp.choices[0].message.content or "").strip()
        if not reply:
            reply = "Ik heb daar nu even geen goed antwoord op."

        # Log bot interaction briefly
        async with STATE_LOCK:
            if STATE is not None:
                _log(STATE, f"BavoBot antwoordt op '{user_msg[:40]}...': {reply[:60]}...")
        return {"reply": reply}
    except Exception:
        return {"reply": "Oeps, er ging iets mis. Probeer je vraag nog eens korter of vraag de leerkracht even."}
