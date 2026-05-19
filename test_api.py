import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1/reference-data/domains"


async def test_create_domain():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            BASE_URL + "/",
            follow_redirects=True,
            json={"name": "TestDomain", "domainType": "lookup", "description": "Test domain"},
        )
        print(f"POST status: {response.status_code}")
        print(f"POST content-type: {response.headers.get('content-type')}")
        print(f"POST response: {response.json()}")
        return response.json()["id"]


async def test_get_domain(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/{domain_id}")
        print(f"\nGET status: {response.status_code}")
        print(f"GET content-type: {response.headers.get('content-type')}")
        data = response.json()
        print(f"GET response _links keys: {list(data.get('_links', {}).keys())}")


async def test_get_domains():
    async with httpx.AsyncClient() as client:
        response = await client.get(BASE_URL + "/")
        print(f"\nGET list status: {response.status_code}")
        data = response.json()
        print(f"GET list count: {data.get('count')}, items: {len(data.get('items', []))}")


async def test_update_domain(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/{domain_id}",
            json={"description": "Updated description"},
        )
        print(f"\nPUT status: {response.status_code}")
        data = response.json()
        print(f"PUT description: {data.get('description')}, version: {data.get('version')}")


async def test_delete_domain(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/{domain_id}")
        print(f"\nDELETE status: {response.status_code}")


async def main():
    domain_id = await test_create_domain()
    await test_get_domain(domain_id)
    await test_get_domains()
    await test_update_domain(domain_id)
    await test_delete_domain(domain_id)
    await test_get_domains()


if __name__ == "__main__":
    asyncio.run(main())
