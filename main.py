import os
import json
import shutil
from contextlib import asynccontextmanager
from fastapi import FastAPI, HTTPException, Body, UploadFile, File, Depends, APIRouter
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from dotenv import load_dotenv

load_dotenv()

from backend.auth import authenticate, create_token, get_current_user
from backend.db import (
    init_db, get_settings, update_setting, get_posts, get_post,
    delete_post, update_post_status, update_post_content, add_team,
    get_teams, remove_team,
)
from backend.sports import get_all_upcoming, get_all_recent, search_team
from backend.content import generate_post, regenerate_text
from backend.visuals import get_library_images, LIBRARY_DIR
from backend.social import publish_post

BASE_DIR = os.path.dirname(__file__)
GENERATED_DIR = os.path.join(BASE_DIR, "generated")
ASSETS_DIR = os.path.join(BASE_DIR, "assets")

# Create required directories before mounting
os.makedirs(GENERATED_DIR, exist_ok=True)
os.makedirs(ASSETS_DIR, exist_ok=True)
os.makedirs(os.path.join(ASSETS_DIR, "library"), exist_ok=True)

AVAILABLE_THEMES = [
    {"id": "sports_event",   "label": "Événement sportif",       "icon": "🏆"},
    {"id": "daily_special",  "label": "Plat du jour / Ardoise",  "icon": "🍕"},
    {"id": "ambiance",       "label": "Ambiance / Vie du resto",  "icon": "✨"},
    {"id": "promo",          "label": "Promotion / Offre",        "icon": "🎁"},
    {"id": "privatisation",  "label": "Privatisation / Événement","icon": "🎉"},
    {"id": "quiz_jeu",       "label": "Quiz / Jeu concours",      "icon": "🎯"},
]


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    os.makedirs(GENERATED_DIR, exist_ok=True)
    os.makedirs(LIBRARY_DIR, exist_ok=True)
    yield


app = FastAPI(title="Gabin Community Manager", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/generated", StaticFiles(directory=GENERATED_DIR), name="generated")
app.mount("/assets", StaticFiles(directory=ASSETS_DIR), name="assets")
app.mount("/static", StaticFiles(directory=os.path.join(BASE_DIR, "frontend")), name="static")


# ── Public routes ─────────────────────────────────────────────────────────────

@app.get("/")
async def root():
    return FileResponse(os.path.join(BASE_DIR, "frontend", "login.html"))


@app.get("/app")
async def dashboard():
    return FileResponse(os.path.join(BASE_DIR, "frontend", "index.html"))


class LoginRequest(BaseModel):
    username: str
    password: str


@app.post("/auth/login")
async def login(req: LoginRequest):
    username = authenticate(req.username, req.password)
    if not username:
        raise HTTPException(status_code=401, detail="Identifiant ou mot de passe incorrect")
    return {"access_token": create_token(username), "username": username}


@app.get("/auth/me")
async def me(user: str = Depends(get_current_user)):
    return {"username": user}


# ── Protected API router (all /api/* require valid JWT) ───────────────────────

api = APIRouter(prefix="/api", dependencies=[Depends(get_current_user)])


@api.get("/sports/upcoming")
async def api_upcoming():
    return get_all_upcoming()


@api.get("/sports/recent")
async def api_recent():
    return get_all_recent()


@api.get("/sports/teams")
async def api_list_teams():
    return get_teams()


@api.get("/sports/search")
async def api_search_teams(q: str):
    return search_team(q)


@api.post("/sports/teams")
async def api_add_team(
    name: str = Body(...),
    sport: str = Body(...),
    external_id: str = Body(...),
    badge_url: str = Body(""),
):
    team_id = add_team(name, sport, external_id, badge_url)
    return {"id": team_id, "name": name, "sport": sport}


@api.delete("/sports/teams/{team_id}")
async def api_remove_team(team_id: int):
    remove_team(team_id)
    return {"ok": True}


class GenerateRequest(BaseModel):
    themes: List[str]
    event_id: Optional[str] = None
    custom_context: Optional[str] = None
    platforms: List[str] = ["instagram", "facebook"]


@api.post("/generate")
async def api_generate(req: GenerateRequest):
    try:
        return await generate_post(
            themes=req.themes,
            event_id=req.event_id,
            custom_context=req.custom_context,
            platforms=req.platforms,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class RegenerateRequest(BaseModel):
    themes: List[str]
    custom_context: Optional[str] = None


@api.post("/posts/{post_id}/regenerate-text")
async def api_regenerate_text(post_id: int, req: RegenerateRequest):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    try:
        return await regenerate_text(
            post_id=post_id,
            themes=req.themes,
            event=post.get("sport_event"),
            custom_context=req.custom_context,
        )
    except Exception as e:
        raise HTTPException(500, str(e))


@api.get("/posts")
async def api_list_posts(status: Optional[str] = None):
    return get_posts(status)


@api.get("/posts/{post_id}")
async def api_get_post(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    return post


@api.put("/posts/{post_id}/approve")
async def api_approve_post(post_id: int):
    update_post_status(post_id, "approved")
    return {"ok": True}


@api.put("/posts/{post_id}")
async def api_update_post(post_id: int, data: dict = Body(...)):
    update_post_content(post_id, data)
    return {"ok": True}


@api.delete("/posts/{post_id}")
async def api_delete_post(post_id: int):
    delete_post(post_id)
    return {"ok": True}


@api.post("/publish/{post_id}")
async def api_publish(post_id: int):
    post = get_post(post_id)
    if not post:
        raise HTTPException(404, "Post not found")
    try:
        result = await publish_post(post)
        update_post_status(post_id, "published")
        return result
    except Exception as e:
        raise HTTPException(500, str(e))


@api.get("/library")
async def api_get_library():
    return get_library_images()


@api.post("/library/upload")
async def api_upload_library(files: List[UploadFile] = File(...)):
    uploaded = []
    for file in files:
        ext = os.path.splitext(file.filename)[1].lower()
        if ext not in {".jpg", ".jpeg", ".png", ".webp"}:
            continue
        dest = os.path.join(LIBRARY_DIR, file.filename)
        with open(dest, "wb") as f:
            shutil.copyfileobj(file.file, f)
        uploaded.append(file.filename)
    return {"uploaded": uploaded}


@api.delete("/library/{filename}")
async def api_delete_library(filename: str):
    path = os.path.join(LIBRARY_DIR, filename)
    if os.path.exists(path):
        os.remove(path)
    return {"ok": True}


@api.get("/themes")
async def api_themes():
    return AVAILABLE_THEMES


@api.get("/settings")
async def api_get_settings():
    return get_settings()


@api.put("/settings")
async def api_update_settings(data: dict = Body(...)):
    for key, value in data.items():
        update_setting(key, json.dumps(value) if not isinstance(value, str) else value)
    return {"ok": True}


app.include_router(api)

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run("main:app", host="0.0.0.0", port=port, reload=True)
