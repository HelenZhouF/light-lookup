import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1/reference-data"


async def test_create_domain():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/",
            follow_redirects=True,
            json={"name": "TestDomainForContent", "domainType": "lookup", "description": "Test domain for content"},
        )
        print(f"Create domain status: {response.status_code}")
        return response.json()["id"]


async def test_create_content(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "Content v1", "status": "developing"},
        )
        print(f"\nCreate content status: {response.status_code}")
        data = response.json()
        print(f"Create content response: {data}")
        print(f"Content _links keys: {list(data.get('_links', {}).keys())}")
        return data["id"]


async def test_create_production_content(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "Production v1", "status": "production"},
        )
        print(f"\nCreate production content status: {response.status_code}")
        data = response.json()
        print(f"Production content standing: {data.get('standing')}")
        return data["id"]


async def test_get_contents(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/domains/{domain_id}/contents/")
        print(f"\nGet contents status: {response.status_code}")
        data = response.json()
        print(f"Contents count: {data.get('count')}, items: {len(data.get('items', []))}")
        for item in data.get("items", []):
            print(f"  - {item['label']}: status={item['status']}, standing={item['standing']}")


async def test_get_content(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.get(f"{BASE_URL}/contents/{content_id}")
        print(f"\nGet content status: {response.status_code}")
        data = response.json()
        print(f"Content label: {data.get('label')}")
        print(f"Content fields: {list(data.keys())}")


async def test_update_content(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/contents/{content_id}",
            json={"label": "Updated Content v1"},
        )
        print(f"\nUpdate content status: {response.status_code}")
        data = response.json()
        print(f"Updated label: {data.get('label')}, version: {data.get('version')}")


async def test_update_content_to_production(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/contents/{content_id}",
            json={"status": "production"},
        )
        print(f"\nUpdate content to production status: {response.status_code}")
        if response.status_code != 200:
            print(f"Error: {response.json()}")


async def test_delete_content(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/contents/{content_id}")
        print(f"\nDelete content status: {response.status_code}")


async def test_delete_domain(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/domains/{domain_id}")
        print(f"\nDelete domain status: {response.status_code}")


async def main():
    domain_id = await test_create_domain()
    content_id1 = await test_create_content(domain_id)
    content_id2 = await test_create_production_content(domain_id)
    await test_get_contents(domain_id)
    await test_get_content(content_id1)
    await test_update_content(content_id1)
    await test_update_content_to_production(content_id1)
    await test_delete_content(content_id1)
    await test_get_contents(domain_id)
    await test_delete_domain(domain_id)


if __name__ == "__main__":
    asyncio.run(main())
