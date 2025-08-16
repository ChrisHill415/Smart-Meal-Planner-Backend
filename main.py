from fastapi import FastAPI, Depends, HTTPException, Header, Request
from pydantic import BaseModel
from supabase import create_client, Client
import requests
import os
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

# 🔹 FastAPI app
app = FastAPI()

# 🔹 CORS Middleware
origins = [
    "http://localhost:5173",   # Vite frontend (dev)
    "http://127.0.0.1:5173",   # alternate localhost
    "https://your-frontend-domain.com",  # your production frontend
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,       # better to whitelist instead of "*"
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Handle OPTIONS requests explicitly (for safety)
@app.options("/{rest_of_path:path}")
async def preflight_handler(request: Request, rest_of_path: str):
    response = JSONResponse(content={"message": "CORS preflight OK"})
    response.headers["Access-Control-Allow-Origin"] = request.headers.get("origin", "*")
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, PUT, PATCH, DELETE, OPTIONS"
    response.headers["Access-Control-Allow-Headers"] = request.headers.get(
        "Access-Control-Request-Headers", "*"
    )
    response.headers["Access-Control-Allow-Credentials"] = "true"
    return response

# 🔹 Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# 🔹 AI API key
AI_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not AI_API_KEY:
    raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

# 🔹 Test AI API key
try:
    response = requests.get(
        "https://openrouter.ai/api/v1/models",
        headers={"Authorization": f"Bearer {AI_API_KEY}"}
    )
    print("OpenRouter test:", response.status_code, response.text)
except Exception as e:
    print("⚠️ Could not verify OpenRouter key:", str(e))

# 🔹 Models
class PantryItem(BaseModel):
    item: str
    quantity: int
    unit: str = ""

class PantryUpdate(BaseModel):
    quantity: int

# 🔹 Auth helper
def get_current_user_id(authorization: str = Header(...)):
    if not authorization.startswith("Bearer "):
        raise HTTPException(status_code=401, detail="Invalid auth header")
    token = authorization.split(" ")[1]
    user_resp = supabase.auth.get_user(token)
    if user_resp.error or not user_resp.data or not user_resp.data.get("user"):
        raise HTTPException(status_code=401, detail="Invalid token or user not found")
    return user_resp.data["user"]["id"]
# 🔹 Routes

# Add pantry item
@app.post("/pantry/add", status_code=201)
def add_pantry_item(item: PantryItem, user_id: str = Depends(get_current_user_id)):
    data = item.model_dump()
    data["user_id"] = user_id
    response = supabase.table("pantry").insert(data).execute()
    if not response.data:
        raise HTTPException(status_code=400, detail="Failed to insert pantry item")
    return response.data

# List pantry items
@app.get("/pantry/list")
def list_pantry_items(user_id: str = Depends(get_current_user_id)):
    response = supabase.table("pantry").select("*").eq("user_id", user_id).execute()
    if response.data is None:
        raise HTTPException(status_code=400, detail="Failed to fetch pantry items")
    return response.data

# Update pantry item
@app.patch("/pantry/update/{item_id}")
def update_pantry_item(item_id: int, update: PantryUpdate, user_id: str = Depends(get_current_user_id)):
    item_resp = supabase.table("pantry").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise HTTPException(status_code=404, detail="Item not found")

    updated_resp = supabase.table("pantry").update({"quantity": update.quantity}).eq("id", item_id).execute()
    if not updated_resp.data:
        raise HTTPException(status_code=400, detail="Failed to update pantry item")
    return {"detail": "Item updated successfully", "item": updated_resp.data[0]}

# Delete pantry item
@app.delete("/pantry/remove/{item_id}")
def remove_pantry_item(item_id: int, user_id: str = Depends(get_current_user_id)):
    item_resp = supabase.table("pantry").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise HTTPException(status_code=404, detail="Item not found")

    delete_resp = supabase.table("pantry").delete().eq("id", item_id).execute()
    if not delete_resp.data:
        raise HTTPException(status_code=400, detail="Failed to delete pantry item")
    return {"detail": "Item deleted successfully"}

# Suggest recipes
@app.get("/api/recipes")
def suggest_recipes(user_id: str = Depends(get_current_user_id)):
    response = supabase.table("pantry").select("*").eq("user_id", user_id).execute()
    if response.data is None:
        raise HTTPException(status_code=400, detail="Failed to fetch pantry items")
    if len(response.data) == 0:
        return {"recipes": "No pantry items found."}

    ingredients_list = ", ".join(
        f"{item['quantity']} {item['unit']} {item['item']}".strip()
        for item in response.data
    )

    ai_prompt = (
        f"Suggest 2 creative recipes I can make using only: {ingredients_list}. "
        "Assume I have basic tools, equipment and basic ingredients. "
        "Include ingredients and step-by-step instructions. "
        "Begin your response by jumping into the recipes, don't include an intro. "
        "Format each recipe starting with '### Recipe:' "
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

# Root
@app.get("/")
def root():
    return {"message": "Welcome to Pantry API!"}

