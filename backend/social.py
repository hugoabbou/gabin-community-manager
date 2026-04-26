import os
import base64
import requests

FACEBOOK_ACCESS_TOKEN = os.getenv("FACEBOOK_ACCESS_TOKEN", "")
INSTAGRAM_ACCOUNT_ID = os.getenv("INSTAGRAM_BUSINESS_ACCOUNT_ID", "")
FACEBOOK_PAGE_ID = os.getenv("FACEBOOK_PAGE_ID", "")
IMGBB_API_KEY = os.getenv("IMGBB_API_KEY", "")
SERVER_URL = os.getenv("SERVER_URL", "http://localhost:8000")

GRAPH_BASE = "https://graph.facebook.com/v19.0"


def _upload_to_imgbb(image_path: str) -> str:
    """Upload image to imgbb and return public URL."""
    with open(image_path, "rb") as f:
        encoded = base64.b64encode(f.read()).decode("utf-8")

    resp = requests.post(
        "https://api.imgbb.com/1/upload",
        data={"key": IMGBB_API_KEY, "image": encoded},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["data"]["url"]


def _get_public_image_url(image_path: str) -> str:
    """Get a public URL for the image (imgbb if configured, else local server)."""
    abs_path = image_path if os.path.isabs(image_path) else os.path.join(
        os.path.dirname(os.path.dirname(__file__)), image_path
    )
    if IMGBB_API_KEY:
        return _upload_to_imgbb(abs_path)
    # Fallback: serve from local server (only works if server is publicly accessible)
    return f"{SERVER_URL}/{image_path}"


def publish_to_instagram_story(image_path: str, caption: str) -> dict:
    if not INSTAGRAM_ACCOUNT_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Instagram credentials not configured"}

    image_url = _get_public_image_url(image_path)

    # Step 1: Create story container
    container_resp = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_ACCOUNT_ID}/media",
        data={
            "image_url": image_url,
            "media_type": "STORIES",
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    container_resp.raise_for_status()
    creation_id = container_resp.json().get("id")

    # Step 2: Publish
    publish_resp = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_ACCOUNT_ID}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    return {"platform": "instagram_story", "id": publish_resp.json().get("id")}


def publish_to_instagram_feed(image_path: str, caption: str) -> dict:
    if not INSTAGRAM_ACCOUNT_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Instagram credentials not configured"}

    image_url = _get_public_image_url(image_path)

    container_resp = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_ACCOUNT_ID}/media",
        data={
            "image_url": image_url,
            "caption": caption,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    container_resp.raise_for_status()
    creation_id = container_resp.json().get("id")

    publish_resp = requests.post(
        f"{GRAPH_BASE}/{INSTAGRAM_ACCOUNT_ID}/media_publish",
        data={
            "creation_id": creation_id,
            "access_token": FACEBOOK_ACCESS_TOKEN,
        },
        timeout=30,
    )
    publish_resp.raise_for_status()
    return {"platform": "instagram_feed", "id": publish_resp.json().get("id")}


def publish_to_facebook(image_path: str, caption: str) -> dict:
    if not FACEBOOK_PAGE_ID or not FACEBOOK_ACCESS_TOKEN:
        return {"error": "Facebook credentials not configured"}

    abs_path = image_path if os.path.isabs(image_path) else os.path.join(
        os.path.dirname(os.path.dirname(__file__)), image_path
    )

    with open(abs_path, "rb") as f:
        resp = requests.post(
            f"{GRAPH_BASE}/{FACEBOOK_PAGE_ID}/photos",
            data={
                "message": caption,
                "access_token": FACEBOOK_ACCESS_TOKEN,
            },
            files={"source": f},
            timeout=30,
        )
    resp.raise_for_status()
    return {"platform": "facebook", "id": resp.json().get("id")}


def build_caption(post: dict) -> str:
    parts = []
    if post.get("hook"):
        parts.append(post["hook"])
    if post.get("body"):
        parts.append(post["body"])
    if post.get("cta"):
        parts.append(post["cta"])
    if post.get("hashtags"):
        tags = post["hashtags"] if isinstance(post["hashtags"], list) else []
        parts.append(" ".join(f"#{h}" for h in tags))
    return "\n\n".join(parts)


async def publish_post(post: dict) -> dict:
    image_path = post.get("image_path", "")
    caption = build_caption(post)
    platforms = post.get("platforms", [])
    if isinstance(platforms, str):
        import json
        platforms = json.loads(platforms)

    results = []

    if "instagram" in platforms:
        try:
            results.append(publish_to_instagram_story(image_path, caption))
        except Exception as e:
            results.append({"platform": "instagram", "error": str(e)})

    if "facebook" in platforms:
        try:
            results.append(publish_to_facebook(image_path, caption))
        except Exception as e:
            results.append({"platform": "facebook", "error": str(e)})

    return {"results": results, "caption": caption}
