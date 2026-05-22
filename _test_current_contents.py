import asyncio
import httpx

BASE_URL = "http://localhost:8001/api/v1/reference-data"


async def main():
    async with httpx.AsyncClient() as client:
        r = await client.post(
            f"{BASE_URL}/domains/",
            json={"name": "CurrentContentsDemo", "domainType": "lookup"},
        )
        print("create domain:", r.status_code)
        domain_id = r.json()["id"]

        r = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/",
            json={"label": "v1", "status": "developing"},
        )
        c1 = r.json()["id"]
        print("create content v1:", r.status_code, c1)

        r = await client.post(
            f"{BASE_URL}/domains/{domain_id}/contents/{c1}/entries",
            json=[{"key": "a", "value": "1"}],
        )
        print("add entry:", r.status_code)

        r = await client.put(
            f"{BASE_URL}/contents/{c1}", json={"status": "production"}
        )
        print("promote v1 to production:", r.status_code, r.json().get("standing"), r.json().get("productionStartTime"))

        r = await client.get(f"{BASE_URL}/domains/{domain_id}/currentContents")
        print("get currentContents:", r.status_code)
        data = r.json()
        print("  count:", data.get("count"))
        for it in data.get("items", []):
            print("   -", it["label"], "start:", it.get("productionStartTime"), "end:", it.get("productionEndTime"))

        r = await client.patch(
            f"{BASE_URL}/domains/{domain_id}/currentContents",
            json=[{"op": "copy", "path": "/execution", "value": {"label": "exec copy"}}],
        )
        print("copy to execution:", r.status_code)
        if r.status_code == 201:
            j = r.json()
            print("   new id:", j["id"], "label:", j["label"], "status:", j["status"])

        r = await client.get(f"{BASE_URL}/domains/{domain_id}/contents/")
        print("all contents:", r.status_code, "count:", r.json().get("count"))


if __name__ == "__main__":
    asyncio.run(main())
