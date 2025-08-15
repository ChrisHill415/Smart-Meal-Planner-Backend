from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import requests
import os
from fastapi.middleware.cors import CORSMiddleware


# Supabase
SUPABASE_URL = os.getenv("SUPABASE_URL", "https://fqqpgfxufljvxgithyvb.supabase.co")
SUPABASE_KEY = os.getenv("SUPABASE_KEY")
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

# AI API key (OpenRouter or OpenAI)
AI_API_KEY = os.getenv("OPENROUTER_API_KEY")  # store in env vars


app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Or replace * with your frontend URL for more security
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


app = FastAPI()

class PantryItem(BaseModel):
    item: str
    quantity: int
    unit: str

def get_current_user_id():
    # Replace with your real auth logic
    return "b2b68226-1d8f-4002-b706-7dfc327346b0"

@app.get("/api/recipes")  # <-- frontend can now call /api/recipes
def suggest_recipes(user_id: str = Depends(get_current_user_id)):
    # Get pantry items for the user
    response = supabase.table("pantry").select("item").eq("user_id", user_id).execute()
    if not response.data:
        return {"error": "No pantry items found"}

    pantry_items = [item["item"] for item in response.data]
    ingredients_list = ", ".join(pantry_items)

    # Build AI prompt
    ai_prompt = f"Suggest 5 creative recipes I can make using only: {ingredients_list}. Include ingredients and instructions."

    # Call AI API
    ai_response = requests.post(
        "https://openrouter.ai/api/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {AI_API_KEY}",
            "Content-Type": "application/json"
        },
        json={
            "model": "gpt-4o-mini",
            "messages": [
                {"role": "system", "content": "You are a helpful recipe assistant."},
                {"role": "user", "content": ai_prompt}
            ]
        }
    )

    if ai_response.status_code != 200:
        raise HTTPException(status_code=500, detail="AI request failed")

    return ai_response.json()

@app.post("/pantry/add", status_code=201)
def add_pantry_item(item: PantryItem, user_id: str = Depends(get_current_user_id)):
    data = item.model_dump()
    data["user_id"] = user_id
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
    if delete_resp.data is None:
        raise HTTPException(status_code=400, detail="Failed to delete pantry item")

    return {"detail": "Item deleted successfully"}

@app.get("/")
def root():
    return {"message": "Welcome to Pantry API!"}

