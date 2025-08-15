from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import requests
import os
import json
from fastapi.middleware.cors import CORSMiddleware

# Create FastAPI app first
app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Change to your frontend URL for security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Supabase config
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Missing SUPABASE_URL or SUPABASE_KEY environment variables.")

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)




# AI API key (OpenRouter or OpenAI)
AI_API_KEY = os.getenv("OPENROUTER_API_KEY")  # store in env vars

response = requests.get(
    "https://openrouter.ai/api/v1/models",
    headers={"Authorization": f"Bearer {AI_API_KEY}"}
)
print(response.status_code, response.text)

# Models
class PantryItem(BaseModel):
    item: str
    quantity: int
    unit: str

# Fake auth for now
def get_current_user_id():
    # Replace with real auth
    return "b2b68226-1d8f-4002-b706-7dfc327346b0"

# Routes
@app.get("/api/recipes")
def suggest_recipes(user_id: str = Depends(get_current_user_id)):
    # Get pantry items for the user
    response = supabase.table("pantry").select("item").eq("user_id", user_id).execute()
    if not response.data:
        return {"error": "No pantry items found"}

    pantry_items = [item["item"] for item in response.data]
    ingredients_list = ", ".join(pantry_items)

    ai_prompt = f"Suggest 5 creative recipes I can make using only: {ingredients_list}. Include ingredients and instructions."

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
            "max_tokens": 800,
            "reasoning_level": "medium"
        }
    )

    if ai_response.status_code != 200:
        raise HTTPException(status_code=500, detail=f"AI request failed: {ai_response.text}")

    # Parse JSON and pretty-print
    parsed = ai_response.json()
    pretty_json = json.dumps(parsed, indent=4)  # 4-space indentation

    return json.loads(pretty_json)  # FastAPI will return it as JSON
    
@app.post("/pantry/add", status_code=201)
def add_pantry_item(item: PantryItem, user_id: str = Depends(get_current_user_id)):
    data = item.model_dump()
    data["user_id"] = user_id
    if not data.get("unit"):
        data["unit"] = ""  # default empty string
    response = supabase.table("pantry").insert(data).execute()
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

    delete_resp = supabase.table("pantry").delete().eq("id", item_id).execute()
    if not delete_resp.data:
        raise HTTPException(status_code=400, detail="Failed to delete pantry item")

    return {"detail": "Item deleted successfully"}

@app.get("/")
def root():
    return {"message": "Welcome to Pantry API!"}





