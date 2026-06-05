import pytest
from httpx import AsyncClient, ASGITransport
from app.main import app  # Assuming the FastAPI app is defined in app/main.py

@pytest.fixture
def client():
    transport = ASGITransport(app=app)
    return AsyncClient(transport=transport, base_url="http://test")

@pytest.mark.asyncio
async def test_read_root(client):
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "message" in data

@pytest.mark.asyncio
async def test_create_item(client):
    payload = {"name": "test_item", "price": 10.5}
    response = await client.post("/items/", json=payload)
    assert response.status_code == 201
    data = response.json()
    assert data["name"] == "test_item"
    assert data["price"] == 10.5
    assert "id" in data

@pytest.mark.asyncio
async def test_get_item(client):
    # First create an item
    create_response = await client.post("/items/", json={"name": "item1", "price": 20.0})
    item_id = create_response.json()["id"]

    response = await client.get(f"/items/{item_id}")
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "item1"
    assert data["price"] == 20.0

@pytest.mark.asyncio
async def test_get_item_not_found(client):
    response = await client.get("/items/99999")
    assert response.status_code == 404
    data = response.json()
    assert "detail" in data

@pytest.mark.asyncio
async def test_update_item(client):
    create_response = await client.post("/items/", json={"name": "old_name", "price": 15.0})
    item_id = create_response.json()["id"]

    update_payload = {"name": "new_name", "price": 25.0}
    response = await client.put(f"/items/{item_id}", json=update_payload)
    assert response.status_code == 200
    data = response.json()
    assert data["name"] == "new_name"
    assert data["price"] == 25.0

@pytest.mark.asyncio
async def test_update_item_not_found(client):
    response = await client.put("/items/99999", json={"name": "nonexistent", "price": 0})
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_delete_item(client):
    create_response = await client.post("/items/", json={"name": "delete_me", "price": 5.0})
    item_id = create_response.json()["id"]

    response = await client.delete(f"/items/{item_id}")
    assert response.status_code == 204

    # Verify it's gone
    get_response = await client.get(f"/items/{item_id}")
    assert get_response.status_code == 404

@pytest.mark.asyncio
async def test_delete_item_not_found(client):
    response = await client.delete("/items/99999")
    assert response.status_code == 404

@pytest.mark.asyncio
async def test_list_items(client):
    # Create a couple of items
    await client.post("/items/", json={"name": "item_a", "price": 1.0})
    await client.post("/items/", json={"name": "item_b", "price": 2.0})

    response = await client.get("/items/")
    assert response.status_code == 200
    data = response.json()
    assert isinstance(data, list)
    assert len(data) >= 2

@pytest.mark.asyncio
async def test_invalid_payload(client):
    # Missing required field 'name'
    response = await client.post("/items/", json={"price": 10.0})
    assert response.status_code == 422

    # Invalid price type
    response = await client.post("/items/", json={"name": "test", "price": "free"})
    assert response.status_code == 422

@pytest.mark.asyncio
async def test_method_not_allowed(client):
    response = await client.put("/", json={})
    assert response.status_code == 405