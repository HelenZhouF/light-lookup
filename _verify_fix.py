import asyncio
import httpx

BASE_URL = "http://localhost:8001/api/v1/reference-data"


async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/domains/",
            json={"name": "TestFix", "domainType": "lookup"},
        )
        print("create domain:", r.status_code)
        domain_id = r.json()["id"]

        r = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "v1", "status": "developing"},
        )
        print("create content:", r.status_code)

        r = await client.get(f"{BASE_URL}/domains/{domain_id}/contents/")
        print("get contents:", r.status_code)
        if r.status_code == 200:
            data = r.json()
            print("  count:", data.get("count"))
            for it in data.get("items", []):
                print("   -", it["label"], "status:", it["status"])
        else:
            print("  error:", r.text)


if __name__ == "__main__":
    asyncio.run(main())
