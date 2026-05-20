import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1/reference-data"


async def test_create_domain():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/",
            follow_redirects=True,
            json={"name": "TestVersionFields", "domainType": "lookup", "description": "Test"},
        )
        print(f"Create domain status: {response.status_code}")
        return response.json()["id"]


async def test_create_content(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "Test Content", "status": "developing"},
        )
        print(f"Create content status: {response.status_code}")
        data = response.json()
        print(f"Content version: {data['majorNumber']}.{data['minorNumber']}")
        return data["id"]


async def test_update_with_major_number(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/contents/{content_id}",
            json={"label": "Updated", "majorNumber": 2},
        )
        print(f"\nUpdate with majorNumber: {response.status_code}")
        if response.status_code == 422:
            print(f"Error: {response.json()}")
        elif response.status_code == 400:
            print(f"Error: {response.json()}")
        return response.status_code


async def test_update_with_minor_number(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/contents/{content_id}",
            json={"label": "Updated", "minorNumber": 5},
        )
        print(f"\nUpdate with minorNumber: {response.status_code}")
        if response.status_code == 422:
            print(f"Error: {response.json()}")
        elif response.status_code == 400:
            print(f"Error: {response.json()}")
        return response.status_code


async def test_update_with_both(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/contents/{content_id}",
            json={"majorNumber": 3, "minorNumber": 3},
        )
        print(f"\nUpdate with both: {response.status_code}")
        if response.status_code == 422:
            print(f"Error: {response.json()}")
        elif response.status_code == 400:
            print(f"Error: {response.json()}")
        return response.status_code


async def test_delete_domain(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/domains/{domain_id}")
        print(f"\nDelete domain: {response.status_code}")


async def main():
    domain_id = await test_create_domain()
    content_id = await test_create_content(domain_id)
    
    status1 = await test_update_with_major_number(content_id)
    print(f"Expected 422/400, got: {status1} {'✓' if status1 in [400, 422] else '✗'}")
    
    status2 = await test_update_with_minor_number(content_id)
    print(f"Expected 422/400, got: {status2} {'✓' if status2 in [400, 422] else '✗'}")
    
    status3 = await test_update_with_both(content_id)
    print(f"Expected 422/400, got: {status3} {'✓' if status3 in [400, 422] else '✗'}")
    
    await test_delete_domain(domain_id)
    
    all_passed = all(s in [400, 422] for s in [status1, status2, status3])
    print(f"\nAll checks passed: {all_passed}")


if __name__ == "__main__":
    asyncio.run(main())
