from typing import Any, Dict
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse
from sqlalchemy.ext.asyncio import AsyncSession
from contextlib import asynccontextmanager

from . import crud, models, schemas
from .database import engine, get_db


MEDIA_TYPE_DOMAIN = "application/vnd.sas.data.reference.domain+json"
MEDIA_TYPE_VALUELIST = "application/vnd.sas.data.reference.valuelist+json"
MEDIA_TYPE_CONTENT = "application/vnd.sas.data.reference.content+json"
API_BASE = "/api/v1/reference-data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
    yield


app = FastAPI(title="light-lookup", lifespan=lifespan)


def build_domain_links(request: Request, domain_id: str, domain_type: str) -> Dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    domain_url = f"{base_url}{API_BASE}/domains/{domain_id}"
    media_type = MEDIA_TYPE_VALUELIST if domain_type == "valueList" else MEDIA_TYPE_DOMAIN
    return {
        "self": schemas.Link(
            href=domain_url,
            method="GET",
            uri=f"{API_BASE}/domains/{domain_id}",
            type=media_type,
        ).model_dump(),
        "update": schemas.Link(
            href=domain_url,
            method="PUT",
            uri=f"{API_BASE}/domains/{domain_id}",
            type=media_type,
        ).model_dump(),
        "delete": schemas.Link(
            href=domain_url,
            method="DELETE",
            uri=f"{API_BASE}/domains/{domain_id}",
            type=media_type,
        ).model_dump(),
        "getContents": schemas.Link(
            href=f"{domain_url}/contents",
            method="GET",
            uri=f"{API_BASE}/domains/{domain_id}/contents",
            type=MEDIA_TYPE_CONTENT,
        ).model_dump(),
        "createContent": schemas.Link(
            href=f"{domain_url}/contents",
            method="POST",
            uri=f"{API_BASE}/domains/{domain_id}/contents",
            type=MEDIA_TYPE_CONTENT,
        ).model_dump(),
        "up": schemas.Link(
            href=f"{base_url}{API_BASE}/domains/",
            method="GET",
            uri=f"{API_BASE}/domains/",
            type=media_type,
        ).model_dump(),
    }


def domain_to_response(request: Request, domain: models.Domain) -> Dict[str, Any]:
    data = schemas.Domain.model_validate(domain).model_dump(mode="json")
    data["_links"] = build_domain_links(request, domain.id, domain.domainType)
    return data


@app.get(f"{API_BASE}/domains/", response_model=schemas.DomainCollection)
async def read_domains(
    request: Request,
    start: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    domains, total = await crud.get_domains(db, skip=start, limit=limit)
    base_url = str(request.base_url).rstrip("/")
    items = [domain_to_response(request, d) for d in domains]
    result = {
        "items": items,
        "start": start,
        "limit": limit,
        "count": total,
        "_links": {
            "self": schemas.Link(
                href=f"{base_url}{API_BASE}/domains/?start={start}&limit={limit}",
                method="GET",
                uri=f"{API_BASE}/domains/",
                type=MEDIA_TYPE_DOMAIN,
            ).model_dump(),
            "create": schemas.Link(
                href=f"{base_url}{API_BASE}/domains/",
                method="POST",
                uri=f"{API_BASE}/domains/",
                type=MEDIA_TYPE_DOMAIN,
            ).model_dump(),
        },
    }
    return JSONResponse(content=result, media_type=MEDIA_TYPE_DOMAIN)


@app.post(f"{API_BASE}/domains/", response_model=schemas.Domain, status_code=status.HTTP_201_CREATED)
async def create_domain(
    request: Request,
    domain: schemas.DomainCreate,
    db: AsyncSession = Depends(get_db),
):
    db_domain = await crud.get_domain_by_name(db, name=domain.name)
    if db_domain:
        raise HTTPException(status_code=400, detail="Domain name already exists")
    created = await crud.create_domain(db=db, domain=domain)
    result = domain_to_response(request, created)
    media_type = MEDIA_TYPE_VALUELIST if created.domainType == "valueList" else MEDIA_TYPE_DOMAIN
    return JSONResponse(content=result, media_type=media_type, status_code=201)


@app.get(f"{API_BASE}/domains/{{domain_id}}", response_model=schemas.Domain)
async def read_domain(
    request: Request,
    domain_id: str,
    db: AsyncSession = Depends(get_db),
):
    db_domain = await crud.get_domain(db, domain_id=domain_id)
    if db_domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    result = domain_to_response(request, db_domain)
    media_type = MEDIA_TYPE_VALUELIST if db_domain.domainType == "valueList" else MEDIA_TYPE_DOMAIN
    return JSONResponse(content=result, media_type=media_type)


@app.put(f"{API_BASE}/domains/{{domain_id}}", response_model=schemas.Domain)
async def update_domain(
    request: Request,
    domain_id: str,
    domain: schemas.DomainUpdate,
    db: AsyncSession = Depends(get_db),
):
    db_domain = await crud.update_domain(db=db, domain_id=domain_id, domain=domain)
    if db_domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    result = domain_to_response(request, db_domain)
    media_type = MEDIA_TYPE_VALUELIST if db_domain.domainType == "valueList" else MEDIA_TYPE_DOMAIN
    return JSONResponse(content=result, media_type=media_type)


@app.delete(f"{API_BASE}/domains/{{domain_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_domain(
    domain_id: str,
    db: AsyncSession = Depends(get_db),
):
    success = await crud.delete_domain(db=db, domain_id=domain_id)
    if not success:
        raise HTTPException(status_code=404, detail="Domain not found")
    return Response(status_code=204)
