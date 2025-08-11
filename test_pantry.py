from fastapi.testclient import TestClient
from main import app  # adjust if your FastAPI app is in another file

client = TestClient(app)

def test_add_pantry_item():
    response = client.post(
        "/pantry/add",
        json={"item_name": "tomato", "quantity": 2, "unit": "pcs"}
    )
    assert response.status_code == 201
    data = response.json()
    assert isinstance(data, list)
    assert "id" in data[0]
    assert data[0]["item_name"] == "tomato"

def test_list_pantry_items():
    response = client.get("/pantry/list")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)

def test_remove_pantry_item():
    # Add an item first
    add_response = client.post(
        "/pantry/add",
        json={"item_name": "lettuce", "quantity": 1, "unit": "head"}
    )
    assert add_response.status_code in (200, 201)
    data = add_response.json()
    assert isinstance(data, list)
    assert "id" in data[0]

    item_id = data[0]["id"]
    remove_response = client.delete(f"/pantry/remove/{item_id}")
    assert remove_response.status_code == 200
    detail = remove_response.json().get("detail")
    assert detail == "Item deleted successfully"
