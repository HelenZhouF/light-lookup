import asyncio
import httpx

BASE_URL = "http://localhost:8000/api/v1/reference-data"


async def test_create_domain():
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/",
            follow_redirects=True,
            json={"name": "TestDomainProdCheck", "domainType": "lookup", "description": "Test"},
        )
        print(f"Create domain status: {response.status_code}")
        return response.json()["id"]


async def test_create_production_content_directly(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "Should Fail", "status": "production"},
        )
        print(f"\nCreate production content directly: {response.status_code}")
        if response.status_code == 400:
            print(f"Error: {response.json()}")
        return response.status_code


async def test_create_developing_content(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "Developing Content", "status": "developing"},
        )
        print(f"\nCreate developing content: {response.status_code}")
        return response.json()["id"]


async def test_promote_to_production(content_id):
    async with httpx.AsyncClient() as client:
        response = await client.put(
            f"{BASE_URL}/contents/{content_id}",
            json={"status": "production"},
        )
        print(f"\nPromote to production: {response.status_code}")
        if response.status_code == 400:
            print(f"Error: {response.json()}")
        return response.status_code


async def test_delete_domain(domain_id):
    async with httpx.AsyncClient() as client:
        response = await client.delete(f"{BASE_URL}/domains/{domain_id}")
        print(f"\nDelete domain: {response.status_code}")


async def main():
    domain_id = await test_create_domain()
    
    status1 = await test_create_production_content_directly(domain_id)
    print(f"Expected 400, got: {status1} {'✓' if status1 == 400 else '✗'}")
    
    content_id = await test_create_developing_content(domain_id)
    
    status2 = await test_promote_to_production(content_id)
    print(f"Expected 400, got: {status2} {'✓' if status2 == 400 else '✗'}")
    
    await test_delete_domain(domain_id)
    
    print(f"\nAll checks passed: {status1 == 400 and status2 == 400}")


if __name__ == "__main__":
    asyncio.run(main())
