"""AgroVet V2 API - serves the web app and the future mobile app.

Endpoints:
  GET  /api/status         -> which models are loaded, device
  GET  /api/classes        -> disease class list
  POST /api/predict        -> multipart image upload -> two-stage result JSON
The static web UI is served from / (the ../web folder).
"""
from __future__ import annotations

from pathlib import Path

from fastapi import Depends, FastAPI, File, Header, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from agrovet.auth_store import (
    create_local_user,
    create_session,
    delete_session,
    get_user_by_token,
    init_db,
    login_local,
    upsert_google_user,
)
from agrovet.image_io import load_rgb_image
from agrovet.infer import InferenceEngine
from agrovet.knowledge import (
    EMERGENCY_CONTACTS,
    GOV_LINKS,
    advice_for,
    chatbot_reply,
)

ROOT = Path(__file__).resolve().parent.parent
WEB_DIR = ROOT / "web"

app = FastAPI(title="AgroVet V2", version="2.0.0")

# Allow the mobile app (and any web origin) to call the API.
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

engine: InferenceEngine | None = None


@app.on_event("startup")
def _load():
    global engine
    init_db()
    engine = InferenceEngine()
    print("Engine status:", engine.status())


@app.get("/api/status")
def status():
    if engine is None:
        return {"ready": False, "message": "Server is still loading models..."}
    s = engine.status()
    s["ready"] = engine.ready
    return s


@app.get("/api/classes")
def classes():
    return {"disease_classes": engine.disease_classes}


@app.post("/api/predict")
async def predict(file: UploadFile = File(...)):
    if engine is None or not engine.ready:
        raise HTTPException(503, "Models are not trained/loaded yet.")
    data = await file.read()
    try:
        img = load_rgb_image(data, fallback_size=None)
    except Exception:
        raise HTTPException(400, "Could not read the uploaded image.")
    return engine.predict(img)


# --------------------------------------------------------------------------- #
# Chatbot, resources and advice (also consumable by the mobile app)
# --------------------------------------------------------------------------- #
class ChatIn(BaseModel):
    message: str
    context_disease: str | None = None
    lang: str | None = "bn"


@app.post("/api/chat")
def chat(body: ChatIn):
    return chatbot_reply(body.message, body.context_disease, body.lang or "en")


@app.get("/api/resources")
def resources():
    return {"emergency_contacts": EMERGENCY_CONTACTS, "gov_links": GOV_LINKS}


@app.get("/api/advice/{class_name}")
def advice(class_name: str, lang: str = "bn"):
    info = advice_for(class_name, lang)
    if info is None:
        raise HTTPException(404, "No advice found for that class.")
    return info


@app.get("/api/diseases")
def diseases(lang: str = "bn"):
    from agrovet.knowledge import all_diseases

    return {"diseases": all_diseases(lang)}


# --------------------------------------------------------------------------- #
# Auth: signup, login, logout, Google, session
# --------------------------------------------------------------------------- #
class SignupIn(BaseModel):
    name: str
    email: str
    password: str


class LoginIn(BaseModel):
    email: str
    password: str


class GoogleAuthIn(BaseModel):
    id_token: str
    client_id: str


def _auth_response(user: dict) -> dict:
    token = create_session(user["id"])
    return {"ok": True, "token": token, "user": user}


def _optional_user(authorization: str | None = Header(default=None)):
    if not authorization or not authorization.startswith("Bearer "):
        return None
    return get_user_by_token(authorization[7:])


@app.post("/api/auth/signup")
def auth_signup(body: SignupIn):
    if len(body.password) < 6:
        raise HTTPException(400, "Password must be at least 6 characters.")
    try:
        user = create_local_user(body.name, body.email, body.password)
    except ValueError as e:
        raise HTTPException(400, str(e))
    return _auth_response(user)


@app.post("/api/auth/login")
def auth_login(body: LoginIn):
    try:
        user = login_local(body.email, body.password)
    except ValueError:
        raise HTTPException(401, "Invalid email or password.")
    return _auth_response(user)


@app.post("/api/auth/logout")
def auth_logout(authorization: str | None = Header(default=None)):
    if authorization and authorization.startswith("Bearer "):
        delete_session(authorization[7:])
    return {"ok": True}


@app.get("/api/auth/me")
def auth_me(user=Depends(_optional_user)):
    if not user:
        raise HTTPException(401, "Not signed in.")
    return {"user": user}


@app.post("/api/auth/google")
def auth_google(body: GoogleAuthIn):
    try:
        from google.oauth2 import id_token as gid_token
        from google.auth.transport import requests as g_requests
    except Exception:
        raise HTTPException(
            501,
            "Server-side Google verification needs `pip install google-auth`.",
        )
    try:
        info = gid_token.verify_oauth2_token(
            body.id_token, g_requests.Request(), body.client_id
        )
    except Exception:
        raise HTTPException(401, "Invalid Google token.")
    user = upsert_google_user(
        info.get("name") or "Google User",
        info.get("email") or "",
        info.get("picture") or "",
        info.get("sub") or "",
    )
    return _auth_response(user)


# --------------------------------------------------------------------------- #
# Static web UI
# --------------------------------------------------------------------------- #
if WEB_DIR.exists():
    app.mount("/static", StaticFiles(directory=str(WEB_DIR)), name="static")

    @app.get("/")
    def index():
        return FileResponse(str(WEB_DIR / "index.html"))

    @app.get("/login")
    def login_page():
        return FileResponse(str(WEB_DIR / "login.html"))

    @app.get("/signup")
    def signup_page():
        return FileResponse(str(WEB_DIR / "signup.html"))

    @app.get("/logout")
    def logout_page():
        return FileResponse(str(WEB_DIR / "logout.html"))
