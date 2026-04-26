import os
import json
from backend.db import create_post, get_settings
from backend.visuals import create_story_image
from backend.sports import get_all_upcoming

GABIN_SYSTEM = """Tu es le community manager de Gabin, une pizzeria napolitaine à Asnières-sur-Seine avec 10 800 abonnés Instagram.

Gabin en quelques mots :
- Pizza napolitaine authentique + burgers F.A.T (Fat As Truck)
- Ambiance conviviale, équipe passionnée, "de l'amore dans chaque assiette"
- Meilleure pizzeria d'Asnières, style casual-chic, clientèle urbaine et branchée
- Ton : casual, chaleureux, fun, direct. Jamais pompeux. Parfois une touche d'italien ("amore", "pizze", "grazie")
- Style éditorial : phrases courtes, percutantes. Emojis utilisés avec parcimonie mais présents.
- L'événement sportif est TOUJOURS un prétexte pour inviter les gens à venir chez Gabin, pas un commentaire sportif.

Tu génères du contenu pour Instagram et Facebook en français."""

THEME_CONTEXT = {
    "sports_event": "Utiliser l'événement sportif comme prétexte pour inviter à venir regarder/célébrer chez Gabin",
    "daily_special": "Mettre en avant le plat du jour ou l'ardoise du moment de manière appétissante",
    "ambiance": "Transmettre l'atmosphère unique de Gabin, la chaleur humaine, l'équipe",
    "promo": "Annoncer une offre ou promotion de manière excitante sans être trop commercial",
    "privatisation": "Inviter à privatiser l'espace pour des événements privés ou professionnels",
    "quiz_jeu": "Créer un jeu ou quiz engageant en lien avec la pizza, le foot, ou Gabin",
}


def _build_prompt(themes: list, event: dict = None, custom_context: str = None) -> str:
    theme_descriptions = "\n".join(
        f"- {THEME_CONTEXT.get(t, t)}" for t in themes if t in THEME_CONTEXT
    )

    event_block = ""
    if event:
        event_block = f"""
Événement sportif du jour :
- Match : {event.get('name', '')}
- Sport : {event.get('sport', '')} {event.get('emoji', '')}
- Compétition : {event.get('league', '')}
- Date : {event.get('date_display', '')} à {event.get('time_display', '')}
- Équipe locale suivie : {event.get('tracked_team', '')}
"""

    custom_block = f"\nContexte additionnel : {custom_context}" if custom_context else ""

    return f"""Génère un post Instagram/Facebook pour Gabin.

Objectifs éditoriaux :
{theme_descriptions}
{event_block}{custom_block}

Génère le contenu au format JSON strict :
{{
  "hook": "Accroche percutante, 1 ligne max, peut contenir 1-2 emojis",
  "body": "Corps du message, 2-4 lignes max, naturel et engageant",
  "cta": "Call-to-action court et direct",
  "hashtags": ["hashtag1", "hashtag2"],
  "visual_title": "Texte principal pour le visuel (court, impactant, MAJUSCULES si sport)",
  "visual_subtitle": "Sous-titre pour le visuel (ex: date du match, nom du plat)"
}}

Règles hashtags : 6-10 hashtags, mix entre génériques (#pizza #restaurant) et spécifiques (#PSG #ChampionsLeague #Asnières #GabinRestaurant). Pas de # dans le champ, juste le mot.

Réponds UNIQUEMENT avec le JSON, sans markdown ni explication."""


def _parse_ai_response(raw: str) -> dict:
    raw = raw.strip()
    if raw.startswith("```"):
        parts = raw.split("```")
        raw = parts[1] if len(parts) > 1 else raw
        if raw.startswith("json"):
            raw = raw[4:]
        raw = raw.strip()
    return json.loads(raw)


def _call_gemini(prompt: str) -> str:
    import google.generativeai as genai
    api_key = os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        raise ValueError("GEMINI_API_KEY non configurée dans .env")
    genai.configure(api_key=api_key)
    model = genai.GenerativeModel(
        "gemini-1.5-flash",
        system_instruction=GABIN_SYSTEM,
    )
    response = model.generate_content(prompt)
    return response.text


def _call_claude(prompt: str) -> str:
    import anthropic
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        raise ValueError("ANTHROPIC_API_KEY non configurée dans .env")
    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        system=GABIN_SYSTEM,
        messages=[{"role": "user", "content": prompt}],
    )
    return message.content[0].text


def _call_ai(prompt: str) -> str:
    """Route to the configured AI provider (DB setting takes precedence over .env)."""
    settings = get_settings()
    provider = str(settings.get("ai_provider", os.getenv("AI_PROVIDER", "gemini"))).lower()
    if provider == "claude":
        return _call_claude(prompt)
    return _call_gemini(prompt)


async def generate_post(
    themes: list,
    event_id: str = None,
    custom_context: str = None,
    platforms: list = None,
):
    if platforms is None:
        platforms = ["instagram", "facebook"]

    event = None
    if event_id and "sports_event" in themes:
        upcoming = get_all_upcoming()
        event = next((e for e in upcoming if str(e.get("id")) == str(event_id)), None)

    prompt = _build_prompt(themes, event, custom_context)
    raw = _call_ai(prompt)
    data = _parse_ai_response(raw)

    hook = data.get("hook", "")
    body = data.get("body", "")
    cta = data.get("cta", "")
    hashtags = data.get("hashtags", [])
    visual_title = data.get("visual_title", hook)
    visual_subtitle = data.get("visual_subtitle", "")

    image_path = create_story_image(
        title=visual_title,
        subtitle=visual_subtitle,
        body=body,
        cta=cta,
        hashtags=hashtags,
        sport_event=event,
        themes=themes,
    )

    post_id = create_post(
        hook=hook,
        body=body,
        cta=cta,
        hashtags=hashtags,
        image_path=image_path,
        platforms=platforms,
        themes=themes,
        sport_event=event,
    )

    settings = get_settings()
    auto_publish = str(settings.get("auto_publish", "false")).lower() == "true"

    return {
        "id": post_id,
        "hook": hook,
        "body": body,
        "cta": cta,
        "hashtags": hashtags,
        "image_path": image_path,
        "platforms": platforms,
        "themes": themes,
        "sport_event": event,
        "status": "draft",
        "auto_publish": auto_publish,
    }


async def regenerate_text(post_id: int, themes: list, event=None, custom_context: str = None):
    prompt = _build_prompt(themes, event, custom_context)
    raw = _call_ai(prompt)
    return _parse_ai_response(raw)
