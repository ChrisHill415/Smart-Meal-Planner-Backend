from fastapi import FastAPI, Depends, HTTPException, Path
from pydantic import BaseModel
from supabase import create_client, Client
import os
from fastapi.middleware.cors import CORSMiddleware

# FastAPI app
app = FastAPI()

# CORS Middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Replace with frontend URL in production
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

# Fake auth for demo
def get_current_user_id():
    return "b2b68226-1d8f-4002-b706-7dfc327346b0"

# Models
class PantryItem(BaseModel):
    item: str
    quantity: int
    unit: str = ""

class UpdateQuantity(BaseModel):
    quantity: int

# -----------------------------
# Pantry CRUD endpoints
# -----------------------------
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
    return response.data or []

@app.delete("/pantry/remove/{item_id}")
def remove_pantry_item(item_id: int, user_id: str = Depends(get_current_user_id)):
    item_resp = supabase.table("pantry").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise HTTPException(status_code=404, detail="Item not found")

    delete_resp = supabase.table("pantry").delete().eq("id", item_id).execute()
    if not delete_resp.data:
        raise HTTPException(status_code=400, detail="Failed to delete pantry item")

    return {"detail": "Item deleted successfully"}

# 🔹 PATCH endpoint for partial quantity updates
@app.patch("/pantry/update/{item_id}")
def update_pantry_quantity(
    item_id: int = Path(..., description="ID of the pantry item"),
    payload: UpdateQuantity = None,
    user_id: str = Depends(get_current_user_id)
):
    if payload.quantity < 0:
        raise HTTPException(status_code=400, detail="Quantity must be non-negative")

    # Check if the item exists
    item_resp = supabase.table("pantry").select("*").eq("id", item_id).eq("user_id", user_id).execute()
    if not item_resp.data:
        raise HTTPException(status_code=404, detail="Item not found")

    if payload.quantity == 0:
        # Delete if quantity is 0
        delete_resp = supabase.table("pantry").delete().eq("id", item_id).execute()
        if not delete_resp.data:
            raise HTTPException(status_code=400, detail="Failed to delete pantry item")
        return {"detail": "Item deleted successfully"}

    # Otherwise, update quantity
    update_resp = supabase.table("pantry").update({"quantity": payload.quantity}).eq("id", item_id).execute()
    if not update_resp.data:
        raise HTTPException(status_code=400, detail="Failed to update pantry item")
    return update_resp.data
