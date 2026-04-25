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
DISABLED_CONSENSUS_FILE = DATA_DIR / "disabled_consensus_dilemmas.json"
ALL_TIME_RANKING_FILE = DATA_DIR / "all_time_ranking.json"
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
# Optional: load .env if present
try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

TEACHER_PASSWORD = os.getenv("TEACHER_PASSWORD", "double diamond").strip()
OPENAI_API_KEY = (os.getenv("OPENAI_API_KEY") or "").strip()

# OpenAI client (BavoBot Full)
# Works with the "openai" python package (new style client).
try:
    from openai import OpenAI, APIConnectionError, APIStatusError, BadRequestError
    _client = OpenAI(api_key=OPENAI_API_KEY) if OPENAI_API_KEY else None
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
    questions = load_questions_from_file(CORE_FILE)
    if rebalance_core_question_answer_positions_in_memory(questions):
        save_core_questions(questions)
    return questions


def load_image_questions():
    return load_questions_from_file(IMAGE_FILE)


def load_consensus_dilemmas():
    return load_questions_from_file(CONSENSUS_FILE)


def load_questions_from_file(path: Path):
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def load_string_list_from_file(path: Path) -> List[str]:
    if not path.exists():
        return []
    with open(path, "r", encoding="utf-8") as f:
        payload = json.load(f)

    if not isinstance(payload, list):
        return []

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


def save_string_list_to_file(path: Path, values: List[str]) -> None:
    with open(path, "w", encoding="utf-8") as f:
        json.dump(values, f, indent=2, ensure_ascii=False)


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
            or "Kies het beste antwoord. Bij een juist antwoord mag je 3 tegels leggen, bij een fout krijg je een plaatsingscoordinaat."
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
            save_questions(questions)
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
STATE: Optional[GameState] = None
LAST_IMAGE_QUESTION = False

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
DEFAULT_RANDOM_SPAWN_CONFIG = {
    "diamond_spawn_min_seconds": 120,
    "diamond_spawn_max_seconds": 210,
    "diamond_max_simultaneous": 3,
    "dynamite_spawn_min_seconds": 180,
    "dynamite_spawn_max_seconds": 300,
    "dynamite_max_simultaneous": 4,
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


def _ranking_summary_text(names: List[str], diamond_total: int) -> str:
    if not names:
        return "Niemand raakte op tijd uit de groeve. Er werd geen rankingresultaat toegevoegd."

    names_text = ", ".join(names)
    diamonds_text = f"{diamond_total} diamant{'en' if diamond_total != 1 else ''}"
    if len(names) == 1:
        return f"{names_text} bereikte de uitgang met {diamonds_text}. (1 ontsnapte speler)"

    player_text = f"{len(names)} ontsnapte spelers"
    return f"{names_text} bereikten samen de uitgang met {diamonds_text}. ({player_text})"


def _sync_ranking_snapshot(gs: GameState) -> None:
    gs.all_time_ranking = load_all_time_ranking()


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
        _sync_ranking_snapshot(gs)
        return

    player_names = [player.name for player in escaped_players]
    diamond_total = _escaped_diamond_total(gs)
    ranking_entries = load_all_time_ranking()
    entry = AllTimeRankingEntry(
        id=gs.game_id,
        game_id=gs.game_id,
        created_at=time.time(),
        player_names=player_names,
        escaped_player_count=len(player_names),
        diamond_total=diamond_total,
    )

    ranking_entries = [existing for existing in ranking_entries if existing.id != entry.id]
    ranking_entries.append(entry)
    save_all_time_ranking(ranking_entries)

    gs.latest_all_time_ranking_entry_id = entry.id
    gs.final_result_note = _ranking_summary_text(player_names, diamond_total)
    gs.ranking_recorded = True
    _sync_ranking_snapshot(gs)
    _log(gs, "All time ranking bijgewerkt: " + gs.final_result_note)


EVALUATION_THEME_ORDER = ["werking", "leefwereld", "risicos", "verantwoord", "beeldronde", "algemeen"]
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
    "risicos": {
        "background": "AI kan fouten maken, iets verzinnen, oude informatie gebruiken of vooroordelen uit data overnemen. Een antwoord kan juist lijken omdat het mooi geschreven is.",
        "strength": "Dit loopt al goed: jullie zien dat AI niet altijd juist is. Dat is belangrijk bij schoolwerk, nieuws, beelden en advies.",
        "growth": "Let nog extra op broncontrole. Controleer zeker wanneer een antwoord verrassend, heel stellig, vaag of te mooi om waar te zijn klinkt.",
        "risk": "Een verkeerd AI-antwoord kan leiden tot foutieve leerstof, verkeerde conclusies, nepnieuws of oneerlijke ideeen over mensen en groepen.",
    },
    "verantwoord": {
        "background": "Verantwoord AI-gebruik betekent dat AI mag helpen, maar dat jullie zelf blijven nadenken, controleren en eerlijk zijn over hulp van AI.",
        "strength": "Dit loopt al goed: jullie kiezen vaker voor controleren, afspraken volgen en eigen denkwerk bewaren.",
        "growth": "Let nog extra op privacy, eerlijk vermelden wanneer AI hielp en AI gebruiken als hulp, niet als vervanger van jullie eigen antwoord.",
        "risk": "Onverantwoord gebruik kan ervoor zorgen dat je persoonlijke gegevens deelt, werk indient dat je niet begrijpt of minder oefent met zelf redeneren.",
    },
    "beeldronde": {
        "background": "AI-beelden en bewerkte beelden kunnen echt lijken. Details zoals handen, tekst, licht, schaduwen en context kunnen helpen, maar geven niet altijd zekerheid.",
        "strength": "Dit loopt al goed: jullie kijken kritischer naar beelden en zoeken naar aanwijzingen voordat jullie beslissen.",
        "growth": "Let nog extra op traag kijken, de bron controleren en de context bekijken voordat jullie een beeld geloven of delen.",
        "risk": "Als je een AI-beeld verkeerd inschat, kan je een nepbeeld delen, iemand onterecht beschuldigen of een gemanipuleerd verhaal geloven.",
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
        return "beeldronde"

    theme = str(question.get("theme") or "").strip()
    if theme in THEMES:
        return theme

    return "algemeen"


def evaluation_theme_label(theme_key: str) -> str:
    if theme_key == "beeldronde":
        return "Beeldronde: AI-beelden herkennen"
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


def group_evaluation_report_rows(gs: GameState) -> List[Tuple[str, int, int]]:
    evaluation = gs.group_evaluation
    rows: List[Tuple[str, int, int]] = [
        ("Groepsevaluatie AI-geletterdheid", 18, 10),
        (
            "Deze evaluatie vat samen wat tijdens het spel zichtbaar werd rond kritisch, veilig en eerlijk omgaan met AI.",
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
        (0.70, 0.62, 0.48),
    ]

    operations.append(pdf_rect_operation(0, 0, page_width, page_height, (0.83, 0.77, 0.64)))
    operations.append(pdf_rect_operation(0, 0, page_width, page_height, (0.50, 0.41, 0.31)))

    border_zones = [
        (0, 0, 62, page_height),
        (page_width - 62, 0, 62, page_height),
        (0, page_height - 86, page_width, 86),
        (0, 0, page_width, 70),
    ]

    for _ in range(170):
        zone_x, zone_y, zone_w, zone_h = rng.choice(border_zones)
        stone_x = zone_x + rng.random() * zone_w
        stone_y = zone_y + rng.random() * zone_h
        stone_w = rng.uniform(12, 30)
        stone_h = rng.uniform(9, 24)
        color = rng.choice(rock_palette)
        operations.append(pdf_stone_operation(stone_x, stone_y, stone_w, stone_h, color, rng.uniform(0, math.pi)))

    # Wooden beams, crates, cones and gold-like stones echo the board edge without copying the grid.
    wood = (0.55, 0.32, 0.13)
    dark_wood = (0.30, 0.19, 0.10)
    red_crate = (0.72, 0.16, 0.09)
    gold = (0.92, 0.68, 0.12)
    cone = (0.88, 0.34, 0.08)

    operations.append(pdf_rect_operation(30, page_height - 55, 72, 7, wood))
    operations.append(pdf_rect_operation(36, page_height - 72, 6, 32, dark_wood))
    operations.append(pdf_rect_operation(92, page_height - 72, 6, 32, dark_wood))
    operations.append(pdf_rect_operation(page_width - 130, 36, 82, 7, wood))
    operations.append(pdf_rect_operation(page_width - 122, 20, 6, 32, dark_wood))
    operations.append(pdf_rect_operation(page_width - 58, 20, 6, 32, dark_wood))

    operations.append(pdf_rect_operation(page_width - 112, page_height - 58, 26, 22, red_crate))
    operations.append(pdf_rect_operation(page_width - 108, page_height - 53, 18, 4, dark_wood))
    operations.append(pdf_rect_operation(page_width - 106, page_height - 47, 14, 4, dark_wood))

    operations.append(pdf_rect_operation(28, 34, 25, 22, red_crate))
    operations.append(pdf_rect_operation(33, 39, 15, 4, dark_wood))

    for gold_x, gold_y in ((page_width - 84, 82), (page_width - 65, 84), (page_width - 74, 100), (118, 52), (137, 55)):
        operations.append(pdf_stone_operation(gold_x, gold_y, 12, 9, gold, rng.uniform(0, math.pi)))

    for cone_x in (92, page_width - 96):
        operations.append(pdf_polygon_operation([(cone_x - 12, 52), (cone_x, 91), (cone_x + 12, 52)], cone))
        operations.append(pdf_rect_operation(cone_x - 15, 48, 30, 6, (0.94, 0.86, 0.70)))

    inner_x = 70
    inner_y = 78
    inner_width = page_width - inner_x * 2
    inner_height = page_height - 174
    operations.append(pdf_rect_operation(inner_x, inner_y, inner_width, inner_height, (0.88, 0.84, 0.73)))
    operations.append(pdf_rect_operation(inner_x + 7, inner_y + 7, inner_width - 14, inner_height - 14, (0.95, 0.91, 0.80)))
    operations.append(pdf_rect_operation(inner_x, inner_y, inner_width, inner_height, (0.38, 0.31, 0.23), b"S"))

    return b"".join(operations)


def build_text_pdf(rows: List[Tuple[str, int, int]]) -> bytes:
    page_width = 595
    page_height = 842
    margin_x = 84
    top_y = 718
    bottom_y = 100
    pages: List[bytes] = []
    operations: List[bytes] = []
    y = top_y

    def flush_page() -> None:
        nonlocal operations, y
        if operations:
            pages.append(b"".join(operations))
            operations = []
        y = top_y

    for text, font_size, gap_after in rows:
        wrap_width = 54 if font_size >= 14 else 72
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

    objects: List[Optional[bytes]] = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        None,
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica /Encoding /WinAnsiEncoding >>",
    ]
    page_ids: List[int] = []

    for page_index, stream in enumerate(pages):
        page_id = len(objects) + 1
        content_id = page_id + 1
        page_ids.append(page_id)
        stream = pdf_board_edge_background(page_width, page_height, page_index) + stream
        objects.append(
            (
                f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 {page_width} {page_height}] "
                f"/Resources << /Font << /F1 3 0 R >> >> /Contents {content_id} 0 R >>"
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


def build_group_evaluation_pdf(gs: GameState) -> bytes:
    return build_text_pdf(student_group_evaluation_report_rows(gs))

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
    _log(gs, "Alle spelers zijn buiten. De teller springt naar 0 en de groeve ontploft meteen.")
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
        all_time_ranking=load_all_time_ranking(),
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
    _seed_initial_board_items(gs, diamond_count=6, dynamite_count=4, now=now)
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
                            "Maak 1 korte, concrete meerkeuzevraag die leerlingen echt laat nadenken over AI-geletterdheid. "
                            "Laat de vraag aansluiten bij een herkenbare leerlingensituatie. "
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
            move_correct_option_to_index(ai_question, stable_question_correct_index(ai_question))
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
        is_correct = chosen_index == correct_index
        async with STATE_LOCK:
            if STATE is not None:
                record_group_question_result(STATE, question, is_correct, chosen_index)
        correct_option = correct_option_text(question)
        return {
            "correct": is_correct,
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
async def get_state():
    async with STATE_LOCK:
        if STATE is None:
            return None
        return STATE


@app.get("/api/ranking", response_model=List[AllTimeRankingEntry])
async def get_all_time_ranking():
    return load_all_time_ranking()


@app.get("/api/evaluation/pdf")
async def download_group_evaluation_pdf():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")

        pdf_bytes = build_group_evaluation_pdf(STATE)

    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": 'attachment; filename="groepsevaluatie-ai-geletterdheid.pdf"',
        },
    )


@app.post("/api/timer/pause", response_model=ActionResponse)
async def pause_timer():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")

        gs = STATE
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
async def resume_timer():
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")

        gs = STATE
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
            _finish_immediately_if_all_players_escaped(gs)
            return ActionResponse(
                ok=True,
                message="Alle spelers zijn buiten. De teller staat op 0 en de groeve ontploft meteen.",
                state=gs,
            )

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
        chain_blast_triggered = False
        if req.kind == "dynamite":
            chain_blast_triggered = _register_distributed_dynamite(gs)

        message = f"{req.kind} op {coord}"
        if chain_blast_triggered:
            message += " en meteen gevolgd door een dynamietketting."
        return ActionResponse(ok=True, message=message, state=gs)


@app.post("/api/item/remove", response_model=ActionResponse)
async def remove_item(req: RemoveItemRequest):
    async with STATE_LOCK:
        if STATE is None:
            raise HTTPException(404, "Geen actief spel.")
        gs = STATE
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
            _collect_item_for_player(gs, player, it)
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

        if all(current_player.escaped for current_player in gs.players):
            _finish_immediately_if_all_players_escaped(gs)
            return ActionResponse(
                ok=True,
                message=f"{player.name} ontsnapt. Iedereen is buiten: de groeve ontploft meteen.",
                state=gs,
            )

        return ActionResponse(ok=True, message=f"{player.name} ontsnapt.", state=gs)


# ----------------------------
# BavoBot Full: Chat endpoint
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
Officiële spelregels van Uit de Steengroeve. Volg deze regels letterlijk en verzin niets erbij.

Algemeen:
- Doel: verzamel diamanten en raak voor de explosie uit de steengroeve.
- De app beheert timer, startcoördinaten, vragen, itemalarmen, uitgang en eindresultaat.
- Pionbeweging en het echte leggen of wegnemen van fysieke tegels gebeuren op het fysieke bord.

Start van het spel:
- Bij een nieuw spel krijgt elke speler een willekeurig startcoördinaat.
- Bij de start liggen er al 6 diamanten en 4 dynamietstaven op willekeurige vrije vakken.
- Daarna kunnen extra diamanten en dynamietstaven later opnieuw verschijnen.

Beurten en vragen:
- Spelers kiezen meestal een themaknop om een vraag te openen.
- Bij een gewone meerkeuzevraag geldt: juist antwoord = zelf 3 tegels leggen; fout antwoord = de app geeft 1 verplicht plaatsingscoördinaat.
- Bij een beeldvraag kies je of een beeld waarschijnlijk AI-gegenereerd is of niet.
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
- Als iedereen al buiten is, springt de teller naar 0 en ontploft de groeve meteen voor het eindresultaat.
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
- Soms komt er tussendoor een beeldvraag; dat gebeurt met ongeveer {int(IMAGE_QUESTION_CHANCE * 100)}% kans zolang dat past.

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

    if ("ranking" in text or "diamant" in text or "einde" in text) and ("meetel" in text or "tellen" in text or "buiten" in text or "ontsnapt" in text):
        return "Voor de all time ranking tellen alleen diamanten mee van spelers die op tijd ontsnappen. De ranking verschijnt pas na de explosie."

    if ("start" in text or "begin" in text) and ("diamant" in text or "dynamiet" in text):
        return "Bij de start van een spel liggen er 6 diamanten en 4 dynamietstaven op willekeurige vrije vakken."

    if "pauze" in text and ("klok" in text or "timer" in text):
        return "De pauzeknop zet de spelklok stil zonder het spel te resetten. Met dezelfde knop kan je de klok weer hervatten."

    if ("iedereen" in text and ("buiten" in text or "ontsnapt" in text)) or ("wanneer" in text and "ranking" in text):
        return "Als iedereen buiten is, springt de teller naar 0 en ontploft de groeve meteen. Daarna komt het eindresultaat en de all time ranking."

    return None

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
async def chat(req: ChatRequest):
    async with STATE_LOCK:
        gs = STATE

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

    fallback_reply = _bot_rule_fallback(gs, user_msg)
    if fallback_reply:
        async with STATE_LOCK:
            if STATE is not None:
                _log(STATE, f"BavoBot regelantwoord op '{user_msg[:40]}...': {fallback_reply[:60]}...")
        return {"reply": fallback_reply}

    if gs is None:
        return {
            "reply": (
                "BavoBot helpt ook al voor de start met basisregels. "
                "Vraag bijvoorbeeld wie op de groene exitknop mag drukken, wat dynamiet doet, "
                "hoe de pauzeknop werkt of wanneer de ranking verschijnt."
            )
        }

    if _client is None:
        return {
            "reply": (
                "BavoBot kan nu de basisregels uitleggen, maar de uitgebreide chat staat hier niet aan. "
                "Stel je vraag zo concreet mogelijk over een spelregel."
            )
        }

    sys_prompt = _bot_system_prompt(gs) + player_ctx

    try:
        resp = _client.chat.completions.create(
            model="gpt-4.1-mini",
            messages=[
                {"role": "system", "content": sys_prompt},
                {"role": "user", "content": user_msg}
            ],
            temperature=0.2
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
