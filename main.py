from fastapi import FastAPI, Depends, HTTPException
from pydantic import BaseModel
from supabase import create_client, Client
import requests
from fastapi import Depends

SUPABASE_URL = "https://fqqpgfxufljvxgithyvb.supabase.co"     # from Supabase settings
SUPABASE_KEY = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6ImZxcXBnZnh1ZmxqdnhnaXRoeXZiIiwicm9sZSI6ImFub24iLCJpYXQiOjE3NTQ4NzI2OTMsImV4cCI6MjA3MDQ0ODY5M30.ccY6m60xtFSTHgD4iov7y21S3Kbh42TOZgPkSghtBF0"     # anon key from Supabase
SPOON_KEY = "d51ae9caba694a00ae6a52fe15d5f4ae"


app = FastAPI()
supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

class PantryItem(BaseModel):
    item: str
    quantity: int
    unit: str

def get_current_user_id():
    # Replace this with your actual auth logic; use valid UUID string for now
    return "b2b68226-1d8f-4002-b706-7dfc327346b0"




@app.get("/recipes/suggest")
def suggest_recipes(user_id: str = Depends(get_current_user_id)):
    # Step 1: Query pantry items for this user from Supabase
    response = supabase.table("pantry").select("item").eq("user_id", user_id).execute()
    
    if response.data is None or len(response.data) == 0:
        return {"error": "No pantry items found for this user."}
    
    # Step 2: Extract item names as a list of strings
    pantry_items = [item['item'] for item in response.data]
    
    # Step 3: Join items with commas for Spoonacular API
    ingredients = ",".join(pantry_items)
    
    # Step 4: Build Spoonacular API URL
    url = f"https://api.spoonacular.com/recipes/findByIngredients?ingredients={ingredients}&apiKey={SPOON_KEY}"
    
    # Step 5: Make the request to Spoonacular
    spoon_response = requests.get(url)
    
    if spoon_response.status_code != 200:
        return {"error": "Failed to fetch recipes from Spoonacular."}
    
    recipes = spoon_response.json()
    return recipes



@app.post("/pantry/add", status_code=201)
def add_pantry_item(item: PantryItem, user_id: str = Depends(get_current_user_id)):
    data = item.model_dump()
    data["user_id"] = user_id

    response = supabase.table("pantry").insert(data).execute()
    if response.data is None:
        # No data means failure
        raise HTTPException(status_code=400, detail="Failed to insert pantry item")
    return response.data

@app.get("/")
def root():
    return {"message": "Welcome to Pantry API!"}


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

    delete_resp = supabase.table("pantry_items").delete().eq("id", item_id).execute()
    if delete_resp.data is None:
        raise HTTPException(status_code=400, detail="Failed to delete pantry item")

    return {"detail": "Item deleted successfully"}


