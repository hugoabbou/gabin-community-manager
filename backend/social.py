import os
import requests

GRAPH_BASE = "https://graph.facebook.com/v19.0"
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")


def _get_credentials() -> tuple[str, str]:
    token = os.getenv("INSTAGRAM_ACCESS_TOKEN") or os.getenv("FACEBOOK_ACCESS_TOKEN", "")
    account_id = os.getenv("INSTAGRAM_ACCOUNT_ID") or os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
    return str(token), str(account_id)


def _get_public_image_url(image_path: str) -> str:
    if image_path.startswith("https://"):
        return image_path
    import base64
    abs_path = image_path if os.path.isabs(image_path) else os.path.join(
        os.path.dirname(os.path.dirname(__file__)), image_path
    )
    if IMGBB_API_KEY:
        with open(abs_path, "rb") as f:
            encoded = base64.b64encode(f.read()).decode("utf-8")
        resp = requests.post(
            "https://api.imgbb.com/1/upload",
            data={"key": IMGBB_API_KEY, "image": encoded},
            timeout=30,
        )
        resp.raise_for_status()
        return resp.json()["data"]["url"]
    return f"{SERVER_URL}/{image_path}"


def publish_to_instagram_story(image_path: str, caption: str) -> dict:
    token, account_id = _get_credentials()
    if not token or not account_id:
        raise ValueError("Credentials Instagram non configurés — configure-les dans Réglages")

    image_url = _get_public_image_url(image_path)

    container = requests.post(
        f"{GRAPH_BASE}/{account_id}/media",
        data={"image_url": image_url, "media_type": "STORIES", "access_token": token},
        timeout=30,
    )
    container.raise_for_status()
    creation_id = container.json().get("id")

    pub = requests.post(
        f"{GRAPH_BASE}/{account_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    pub.raise_for_status()
    return {"platform": "instagram_story", "id": pub.json().get("id")}


def publish_to_instagram_feed(image_path: str, caption: str) -> dict:
    token, account_id = _get_credentials()
    if not token or not account_id:
        raise ValueError("Credentials Instagram non configurés — configure-les dans Réglages")

    image_url = _get_public_image_url(image_path)

    container = requests.post(
        f"{GRAPH_BASE}/{account_id}/media",
        data={"image_url": image_url, "caption": caption, "access_token": token},
        timeout=30,
    )
    container.raise_for_status()
    creation_id = container.json().get("id")

    pub = requests.post(
        f"{GRAPH_BASE}/{account_id}/media_publish",
        data={"creation_id": creation_id, "access_token": token},
        timeout=30,
    )
    pub.raise_for_status()
    return {"platform": "instagram_feed", "id": pub.json().get("id")}


def build_caption(post: dict) -> str:
    parts = []
    if post.get("hook"):
        parts.append(post["hook"])
    if post.get("body"):
        parts.append(post["body"])
    if post.get("cta"):
        parts.append(post["cta"])
    tags = post.get("hashtags", [])
    if isinstance(tags, list) and tags:
        parts.append(" ".join(f"#{h}" for h in tags))
    return "\n\n".join(parts)


async def publish_post(post: dict) -> dict:
    image_path = post.get("image_path", "")
    caption = build_caption(post)
    result = publish_to_instagram_story(image_path, caption)
    return {"results": [result], "caption": caption}
