from fastapi import FastAPI, Depends, HTTPException, Header
from pydantic import BaseModel
from supabase import create_client, Client
import requests
import os
import jwt
from fastapi.middleware.cors import CORSMiddleware

# FastAPI app
app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For production, replace with frontend URL
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")  # Needed to verify JWT

if not SUPABASE_URL or not SUPABASE_KEY or not SUPABASE_JWT_SECRET:
    raise RuntimeError("Missing SUPABASE_URL, SUPABASE_KEY, or SUPABASE_JWT_SECRET environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# AI API key
AI_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not AI_API_KEY:
    raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

# Models
class PantryItem(BaseModel):
    item: str
    quantity: int
    unit: str | None = ""

# Auth helper
def get_current_user_id(authorization: str = Header(None)) -> str:
    if not authorization:
        raise HTTPException(status_code=401, detail="Missing Authorization header")
    try:
        token_type, token = authorization.split()
        if token_type.lower() != "bearer":
            raise HTTPException(status_code=401, detail="Invalid token type")
        payload = jwt.decode(token, SUPABASE_JWT_SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            raise HTTPException(status_code=401, detail="Invalid token payload")
        return user_id
    except Exception as e:
        raise HTTPException(status_code=401, detail=f"JWT decode error: {str(e)}")

# Routes
@app.get("/api/recipes")
def suggest_recipes(user_id: str = Depends(get_current_user_id)):
    # Fetch pantry items for this user
    response = supabase.table("pantry").select("*").eq("user_id", user_id).execute()
    if not response.data:
        return {"recipes": "No pantry items found."}

    ingredients_list = ", ".join(
        f"{item['quantity']} {item.get('unit', '')} {item['item']}".strip()
        for item in response.data
    )

    ai_prompt = (
        f"Suggest 2 creative recipes I can make using only: {ingredients_list}. "
        "Assume I have basic tools, equipment, and basic ingredients. "
        "Include ingredients and step-by-step instructions. "
        "Begin your response by jumping into the recipes, don't include an intro. "
        "Format them so each recipe starts with '### Recipe:' "
    )

    ai_response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "openai/gpt-oss-20b",
            "messages": [
                {"role": "system", "content": "You are a helpful recipe assistant."},
                {"role": "user", "content": ai_prompt}
            ],
            "temperature": 0.7,
            "max_tokens": 2000,
            "reasoning_level": "medium"
        }
    )

    if ai_response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"AI request failed: {ai_response.text}")

    data = ai_response.json()
    try:
        recipe_text = data["choices"][0]["message"]["content"]
    except (KeyError, IndexError):
        recipe_text = "No recipes generated."

    return {"recipes": recipe_text}


@app.post("/pantry/add", status_code=201)
def add_pantry_item(item: PantryItem, user_id: str = Depends(get_current_user_id)):
    payload = item.model_dump()
    payload["user_id"] = user_id
    response = supabase.table("pantry").insert(payload).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to insert pantry item")
    return response.data

@app.get("/pantry/list")
def list_pantry_items(user_id: str = Depends(get_current_user_id)):
    response = supabase.table("pantry").select("*").eq("user_id", user_id).execute()
    if response.data is None:
        raise HTTPException(status_code=400, detail="Failed to fetch pantry items")
    return response.data

@app.delete("/pantry/remove/{item_id}")
def remove_pantry_item(item_id: int, user_id: str = Depends(get_current_user_id)):
    item_resp = supabase.table("pantry").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise HTTPException(status_code=404, detail="Item not found")

    delete_resp = supabase.table("pantry").delete().eq("id", item_id).eq("user_id", user_id).execute()
    if not delete_resp.data:
        raise HTTPException(status_code=400, detail="Failed to delete pantry item")

    return {"detail": "Item deleted successfully"}

@app.get("/")
def root():
    return {"message": "Welcome to Pantry API!"}
