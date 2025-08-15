from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import requests
import os
from fastapi.middleware.cors import CORSMiddleware

# FastAPI app
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

# AI API key
AI_API_KEY = os.getenv("OPENROUTER_API_KEY")
if not AI_API_KEY:
    raise RuntimeError("Missing OPENROUTER_API_KEY environment variable.")

# Test API key (optional)
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

# Fake auth
def get_current_user_id():
    return "b2b68226-1d8f-4002-b706-7dfc327346b0"

# Routes
@app.get("/api/recipes")
def suggest_recipes(user_id: str = Depends(get_current_user_id)):
    # Fetch pantry items
    response = supabase.table("pantry").select("item").eq("user_id", user_id).execute()
    if not response.data:
        return {"recipes": "No pantry items found."}

    pantry_items = [item["item"] for item in response.data]
    # Example: include quantity and unit in the prompt
        ingredients_list = ", ".join(
            f"{item['quantity']} {item['unit']} {item['item']}".strip()
            for item in response.data
        )


    ai_prompt = (
        f"Suggest 2 creative recipes I can make using only: {ingredients_list}. "
        "Assume I have basic tools, equipment and basic ingredients"
        "Include ingredients and step-by-step instructions."
        "Begin your response by jumping into the recipes, don't include an intro"
        "Format them so each recipe starts with '### Recipe:' "
    )

    # OpenRouter API call
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
            "max_tokens": 2000,  # Increase to get full recipes
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

    # Return clean JSON
    return {"recipes": recipe_text}


@app.post("/pantry/add", status_code=201)
def add_pantry_item(item: PantryItem, user_id: str = Depends(get_current_user_id)):
    data = item.model_dump()
    data["user_id"] = user_id
    if not data.get("unit"):
        data["unit"] = ""
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




