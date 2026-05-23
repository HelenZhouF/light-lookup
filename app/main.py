from typing import Any, Dict, List
from datetime import datetime
from fastapi import FastAPI, Depends, HTTPException, status, Request, Response
from fastapi.responses import JSONResponse, StreamingResponse
from fastapi.exceptions import RequestValidationError
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import text
from contextlib import asynccontextmanager
from pydantic import ValidationError
import csv
import io

from . import crud, models, schemas
from .database import engine, get_db


MEDIA_TYPE_DOMAIN = "application/vnd.sas.data.reference.domain+json"
MEDIA_TYPE_VALUELIST = "application/vnd.sas.data.reference.valuelist+json"
MEDIA_TYPE_CONTENT = "application/vnd.sas.data.reference.content+json"
MEDIA_TYPE_ENTRY = "application/vnd.sas.data.reference.entry+json"
MEDIA_TYPE_COLLECTION = "application/vnd.sas.collection+json"
API_BASE = "/api/v1/reference-data"


@asynccontextmanager
async def lifespan(app: FastAPI):
    async with engine.begin() as conn:
        await conn.run_sync(models.Base.metadata.create_all)
        result = await conn.execute(text("PRAGMA table_info(entries)"))
        existing = {row[1] for row in result.fetchall()}
        for col_name, col_def in [
            ("disabled", "BOOLEAN NOT NULL DEFAULT 0"),
            ("sequence", "INTEGER NOT NULL DEFAULT 0"),
            ("folderPath", "VARCHAR(1024)"),
        ]:
            if col_name not in existing:
                await conn.execute(text(f"ALTER TABLE entries ADD COLUMN {col_name} {col_def}"))
    yield


app = FastAPI(title="light-lookup", lifespan=lifespan)


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    for error in exc.errors():
        field = error.get("loc", [])
        if len(field) >= 2 and field[0] == "body":
            field_name = field[1]
            if field_name in ["majorNumber", "minorNumber"]:
                return JSONResponse(
                    status_code=400,
                    content={"detail": f"Field '{field_name}' is read-only and cannot be modified"},
                )
    return JSONResponse(
        status_code=422,
        content={"detail": exc.errors()},
    )


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
        "getCurrentContents": schemas.Link(
            href=f"{domain_url}/currentContents",
            method="GET",
            uri=f"{API_BASE}/domains/{domain_id}/currentContents",
            type=MEDIA_TYPE_COLLECTION,
        ).model_dump(),
        "copyCurrentContent": schemas.Link(
            href=f"{domain_url}/currentContents",
            method="PATCH",
            uri=f"{API_BASE}/domains/{domain_id}/currentContents",
            type="application/json-patch+json",
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


def build_content_links(request: Request, content_id: str, domain_id: str) -> Dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    content_url = f"{base_url}{API_BASE}/contents/{content_id}"
    entries_uri = f"{API_BASE}/domains/{domain_id}/contents/{content_id}/entries"
    entries_url = f"{base_url}{entries_uri}"
    return {
        "self": schemas.Link(
            href=content_url,
            method="GET",
            uri=f"{API_BASE}/contents/{content_id}",
            type=MEDIA_TYPE_CONTENT,
        ).model_dump(),
        "update": schemas.Link(
            href=content_url,
            method="PUT",
            uri=f"{API_BASE}/contents/{content_id}",
            type=MEDIA_TYPE_CONTENT,
        ).model_dump(),
        "delete": schemas.Link(
            href=content_url,
            method="DELETE",
            uri=f"{API_BASE}/contents/{content_id}",
            type=MEDIA_TYPE_CONTENT,
        ).model_dump(),
        "getEntries": schemas.Link(
            href=entries_url,
            method="GET",
            uri=entries_uri,
            type=MEDIA_TYPE_COLLECTION,
        ).model_dump(),
        "createEntries": schemas.Link(
            href=entries_url,
            method="POST",
            uri=entries_uri,
            type=MEDIA_TYPE_ENTRY,
        ).model_dump(),
        "patchEntries": schemas.Link(
            href=entries_url,
            method="PATCH",
            uri=entries_uri,
            type="application/json-patch+json",
        ).model_dump(),
        "deleteEntries": schemas.Link(
            href=entries_url,
            method="DELETE",
            uri=entries_uri,
            type="*/*",
        ).model_dump(),
        "up": schemas.Link(
            href=f"{base_url}{API_BASE}/domains/{domain_id}",
            method="GET",
            uri=f"{API_BASE}/domains/{domain_id}",
            type=MEDIA_TYPE_DOMAIN,
        ).model_dump(),
    }


def content_to_response(request: Request, content: models.Content) -> Dict[str, Any]:
    data = schemas.Content.model_validate(content).model_dump(mode="json")
    data["_links"] = build_content_links(request, content.id, content.domainId)
    return data


@app.get(f"{API_BASE}/domains/{{domain_id}}/contents/", response_model=schemas.ContentCollection)
async def read_contents(
    request: Request,
    domain_id: str,
    start: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    db_domain = await crud.get_domain(db, domain_id=domain_id)
    if db_domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    contents, total = await crud.get_contents_by_domain_id(db, domain_id=domain_id, skip=start, limit=limit)
    base_url = str(request.base_url).rstrip("/")
    items = [content_to_response(request, c) for c in contents]
    result = {
        "items": items,
        "start": start,
        "limit": limit,
        "count": total,
        "_links": {
            "self": schemas.Link(
                href=f"{base_url}{API_BASE}/domains/{domain_id}/contents/?start={start}&limit={limit}",
                method="GET",
                uri=f"{API_BASE}/domains/{domain_id}/contents/",
                type=MEDIA_TYPE_CONTENT,
            ).model_dump(),
            "create": schemas.Link(
                href=f"{base_url}{API_BASE}/domains/{domain_id}/contents/",
                method="POST",
                uri=f"{API_BASE}/domains/{domain_id}/contents/",
                type=MEDIA_TYPE_CONTENT,
            ).model_dump(),
            "up": schemas.Link(
                href=f"{base_url}{API_BASE}/domains/{domain_id}",
                method="GET",
                uri=f"{API_BASE}/domains/{domain_id}",
                type=MEDIA_TYPE_DOMAIN,
            ).model_dump(),
        },
    }
    return JSONResponse(content=result, media_type=MEDIA_TYPE_CONTENT)


@app.post(
    f"{API_BASE}/domains/{{domain_id}}/contents/",
    response_model=schemas.Content,
    status_code=status.HTTP_201_CREATED,
)
async def create_content(
    request: Request,
    domain_id: str,
    content: schemas.ContentCreate,
    db: AsyncSession = Depends(get_db),
):
    try:
        created = await crud.create_content(db=db, domain_id=domain_id, content=content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    result = content_to_response(request, created)
    return JSONResponse(content=result, media_type=MEDIA_TYPE_CONTENT, status_code=201)


@app.get(f"{API_BASE}/contents/{{content_id}}", response_model=schemas.Content)
async def read_content(
    request: Request,
    content_id: str,
    db: AsyncSession = Depends(get_db),
):
    db_content = await crud.get_content(db, content_id=content_id)
    if db_content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    result = content_to_response(request, db_content)
    return JSONResponse(content=result, media_type=MEDIA_TYPE_CONTENT)


@app.put(f"{API_BASE}/contents/{{content_id}}", response_model=schemas.Content)
async def update_content(
    request: Request,
    content_id: str,
    content: schemas.ContentUpdate,
    db: AsyncSession = Depends(get_db),
):
    try:
        db_content = await crud.update_content(db=db, content_id=content_id, content=content)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))
    if db_content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    result = content_to_response(request, db_content)
    return JSONResponse(content=result, media_type=MEDIA_TYPE_CONTENT)


@app.delete(f"{API_BASE}/contents/{{content_id}}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_content(
    content_id: str,
    db: AsyncSession = Depends(get_db),
):
    success = await crud.delete_content(db=db, content_id=content_id)
    if not success:
        raise HTTPException(status_code=404, detail="Content not found")
    return Response(status_code=204)


def current_content_to_response(request: Request, content: models.Content) -> Dict[str, Any]:
    return schemas.CurrentContent.model_validate(content).model_dump(mode="json")


@app.get(f"{API_BASE}/domains/{{domain_id}}/currentContents", response_model=schemas.CurrentContentCollection)
async def read_current_contents(
    request: Request,
    domain_id: str,
    start: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    db_domain = await crud.get_domain(db, domain_id=domain_id)
    if db_domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    contents, total = await crud.get_production_contents_by_domain_id(
        db, domain_id=domain_id, skip=start, limit=limit
    )
    base_url = str(request.base_url).rstrip("/")
    cc_uri = f"{API_BASE}/domains/{domain_id}/currentContents"
    items = [current_content_to_response(request, c) for c in contents]
    result = {
        "items": items,
        "start": start,
        "limit": limit,
        "count": total,
        "_links": {
            "self": schemas.Link(
                href=f"{base_url}{cc_uri}?start={start}&limit={limit}",
                method="GET",
                uri=cc_uri,
                type=MEDIA_TYPE_COLLECTION,
            ).model_dump(),
            "copyToExecution": schemas.Link(
                href=f"{base_url}{cc_uri}",
                method="PATCH",
                uri=cc_uri,
                type="application/json-patch+json",
            ).model_dump(),
            "up": schemas.Link(
                href=f"{base_url}{API_BASE}/domains/{domain_id}",
                method="GET",
                uri=f"{API_BASE}/domains/{domain_id}",
                type=MEDIA_TYPE_DOMAIN,
            ).model_dump(),
        },
    }
    return JSONResponse(content=result, media_type=MEDIA_TYPE_COLLECTION)


@app.patch(f"{API_BASE}/domains/{{domain_id}}/currentContents")
async def patch_current_contents(
    request: Request,
    domain_id: str,
    operations: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
):
    db_domain = await crud.get_domain(db, domain_id=domain_id)
    if db_domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")

    if not operations:
        raise HTTPException(status_code=400, detail="At least one JSON Patch operation is required")

    current_prod = await crud.get_current_production_content(db, domain_id=domain_id)
    if current_prod is None:
        raise HTTPException(
            status_code=400,
            detail="No content in production. A production content is required to copy to the execution environment.",
        )

    for op_data in operations:
        op = op_data.get("op")
        path = op_data.get("path", "")
        value = op_data.get("value")

        if op not in ["add", "replace", "copy"]:
            raise HTTPException(
                status_code=400,
                detail=f"Unsupported operation: {op}. Supported operations: add, replace, copy",
            )

        path_parts = path.strip("/").split("/") if path.strip("/") else []
        top = path_parts[0] if path_parts else ""

        if op == "copy":
            if top and top != "execution":
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported copy path: {path}. Only '/execution' is supported.",
                )
            label = None
            if isinstance(value, dict):
                label = value.get("label")
            elif isinstance(value, str):
                label = value
            new_content = await crud.copy_content_to_execution(db, current_prod, label=label)
            result = content_to_response(request, new_content)
            return JSONResponse(content=result, media_type=MEDIA_TYPE_CONTENT, status_code=201)

        if op in ["add", "replace"]:
            if top != "execution":
                raise HTTPException(
                    status_code=400,
                    detail=f"Unsupported path: {path}. Only '/execution' is supported.",
                )
            label = None
            if isinstance(value, dict):
                label = value.get("label")
            elif isinstance(value, str):
                label = value
            new_content = await crud.copy_content_to_execution(db, current_prod, label=label)
            result = content_to_response(request, new_content)
            return JSONResponse(content=result, media_type=MEDIA_TYPE_CONTENT, status_code=201)

    raise HTTPException(status_code=400, detail="No copy/add/replace operation matched")


ENTRIES_PATH = f"{API_BASE}/domains/{{domain_id}}/contents/{{content_id}}/entries"


def build_entry_links(request: Request, domain_id: str, content_id: str, entry_id: str) -> Dict[str, Any]:
    base_url = str(request.base_url).rstrip("/")
    entries_uri = f"{API_BASE}/domains/{domain_id}/contents/{content_id}/entries"
    entry_uri = f"{entries_uri}/{entry_id}"
    return {
        "self": schemas.Link(
            href=f"{base_url}{entry_uri}",
            method="GET",
            uri=entry_uri,
            type=MEDIA_TYPE_ENTRY,
        ).model_dump(),
        "update": schemas.Link(
            href=f"{base_url}{entry_uri}",
            method="PATCH",
            uri=entry_uri,
            type="application/json-patch+json",
        ).model_dump(),
        "delete": schemas.Link(
            href=f"{base_url}{entry_uri}",
            method="DELETE",
            uri=entry_uri,
            type="*/*",
        ).model_dump(),
        "up": schemas.Link(
            href=f"{base_url}{API_BASE}/contents/{content_id}",
            method="GET",
            uri=f"{API_BASE}/contents/{content_id}",
            type=MEDIA_TYPE_CONTENT,
        ).model_dump(),
    }


def entry_to_response(request: Request, domain_id: str, content_id: str, entry: models.Entry) -> Dict[str, Any]:
    data = schemas.Entry.model_validate(entry).model_dump(mode="json")
    data["_links"] = build_entry_links(request, domain_id, content_id, entry.id)
    return data


async def validate_content_and_domain(
    db: AsyncSession, domain_id: str, content_id: str
) -> tuple[models.Domain, models.Content]:
    db_domain = await crud.get_domain(db, domain_id=domain_id)
    if db_domain is None:
        raise HTTPException(status_code=404, detail="Domain not found")
    db_content = await crud.get_content(db, content_id=content_id)
    if db_content is None:
        raise HTTPException(status_code=404, detail="Content not found")
    if db_content.domainId != domain_id:
        raise HTTPException(status_code=404, detail="Content not found in this domain")
    return db_domain, db_content


def validate_entry_for_domain_type(db_domain: models.Domain, entry_data: dict, for_create: bool = True):
    domain_type = db_domain.domainType
    if domain_type == "lookup":
        if not entry_data.get("key"):
            raise HTTPException(status_code=400, detail="Entry 'key' is required for lookup domain type")
        if not entry_data.get("value"):
            raise HTTPException(status_code=400, detail="Entry 'value' is required")
    elif domain_type == "valueList":
        if not entry_data.get("value"):
            raise HTTPException(status_code=400, detail="Entry 'value' is required")


def check_production_protection(content: models.Content):
    if content.status == "production":
        raise HTTPException(
            status_code=400,
            detail="Cannot modify entries of content in production status",
        )


def entries_to_csv(entries: List[models.Entry], domain_type: str) -> str:
    output = io.StringIO()
    if domain_type == "lookup":
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["key", "value"])
        for entry in entries:
            writer.writerow([entry.key or "", entry.value])
    else:
        writer = csv.writer(output, lineterminator="\n")
        writer.writerow(["value"])
        for entry in entries:
            writer.writerow([entry.value])
    return output.getvalue()


@app.get(ENTRIES_PATH, response_model=schemas.EntryCollection)
async def read_entries(
    request: Request,
    domain_id: str,
    content_id: str,
    start: int = 0,
    limit: int = 10,
    db: AsyncSession = Depends(get_db),
):
    accept = request.headers.get("accept", "*/*")

    db_domain, db_content = await validate_content_and_domain(db, domain_id, content_id)

    if "text/csv" in accept and "application/json" not in accept and MEDIA_TYPE_COLLECTION not in accept:
        all_entries = await crud.get_all_entries_by_content_id(db, content_id=content_id)
        csv_data = entries_to_csv(all_entries, db_domain.domainType)
        return Response(content=csv_data, media_type="text/csv")

    entries, total = await crud.get_entries_by_content_id(db, content_id=content_id, skip=start, limit=limit)
    base_url = str(request.base_url).rstrip("/")
    entries_uri = f"{API_BASE}/domains/{domain_id}/contents/{content_id}/entries"
    items = [entry_to_response(request, domain_id, content_id, e) for e in entries]
    result = {
        "items": items,
        "start": start,
        "limit": limit,
        "count": total,
        "_links": {
            "self": schemas.Link(
                href=f"{base_url}{entries_uri}?start={start}&limit={limit}",
                method="GET",
                uri=entries_uri,
                type=MEDIA_TYPE_COLLECTION,
            ).model_dump(),
            "create": schemas.Link(
                href=f"{base_url}{entries_uri}",
                method="POST",
                uri=entries_uri,
                type=MEDIA_TYPE_ENTRY,
            ).model_dump(),
            "up": schemas.Link(
                href=f"{base_url}{API_BASE}/contents/{content_id}",
                method="GET",
                uri=f"{API_BASE}/contents/{content_id}",
                type=MEDIA_TYPE_CONTENT,
            ).model_dump(),
        },
    }
    return JSONResponse(content=result, media_type=MEDIA_TYPE_COLLECTION)


@app.post(ENTRIES_PATH, response_model=List[Dict[str, Any]], status_code=status.HTTP_201_CREATED)
async def create_entries(
    request: Request,
    domain_id: str,
    content_id: str,
    entries: List[schemas.EntryCreate],
    db: AsyncSession = Depends(get_db),
):
    db_domain, db_content = await validate_content_and_domain(db, domain_id, content_id)
    check_production_protection(db_content)

    if not entries:
        raise HTTPException(status_code=400, detail="At least one entry is required")

    for entry in entries:
        entry_data = entry.model_dump()
        validate_entry_for_domain_type(db_domain, entry_data)

    if db_domain.domainType == "lookup":
        keys = [e.key for e in entries if e.key]
        if len(keys) != len(set(keys)):
            raise HTTPException(status_code=400, detail="Duplicate keys found in entries. Keys must be unique for lookup domain type")

    if db_domain.domainType == "valueList":
        values = [e.value for e in entries]
        if len(values) != len(set(values)):
            raise HTTPException(status_code=400, detail="Duplicate values found in entries. Values must be unique for valueList domain type")

    created = await crud.bulk_replace_entries(db, content_id=content_id, entries=entries)
    items = [entry_to_response(request, domain_id, content_id, e) for e in created]
    return JSONResponse(content=items, media_type=MEDIA_TYPE_ENTRY, status_code=201)


@app.patch(ENTRIES_PATH)
async def patch_entries(
    request: Request,
    domain_id: str,
    content_id: str,
    operations: List[Dict[str, Any]],
    db: AsyncSession = Depends(get_db),
):
    db_domain, db_content = await validate_content_and_domain(db, domain_id, content_id)
    check_production_protection(db_content)

    if not operations:
        raise HTTPException(status_code=400, detail="At least one JSON Patch operation is required")

    for op_data in operations:
        op = op_data.get("op")
        path = op_data.get("path", "")
        value = op_data.get("value")

        if op not in ["add", "replace", "delete"]:
            raise HTTPException(status_code=400, detail=f"Unsupported operation: {op}. Supported operations: add, replace, delete")

        path_parts = path.strip("/").split("/") if path.strip("/") else []

        if op == "add":
            if value is None:
                raise HTTPException(status_code=400, detail="Value is required for 'add' operation")
            validate_entry_for_domain_type(db_domain, value)
            if db_domain.domainType == "lookup" and value.get("key"):
                existing = await crud.get_all_entries_by_content_id(db, content_id=content_id)
                existing_keys = [e.key for e in existing if e.key]
                if value["key"] in existing_keys:
                    raise HTTPException(status_code=400, detail=f"Key '{value['key']}' already exists")
            if db_domain.domainType == "valueList" and value.get("value"):
                existing = await crud.get_all_entries_by_content_id(db, content_id=content_id)
                existing_values = [e.value for e in existing]
                if value["value"] in existing_values:
                    raise HTTPException(status_code=400, detail=f"Value '{value['value']}' already exists")
            try:
                new_entry = schemas.EntryCreate(**value)
            except ValidationError as e:
                raise HTTPException(status_code=400, detail=str(e))
            await crud.create_entry(db, content_id=content_id, entry=new_entry)

        elif op == "replace":
            if len(path_parts) < 1:
                raise HTTPException(status_code=400, detail="Path must reference an entry ID for 'replace' operation")
            entry_id = path_parts[0]
            db_entry = await crud.get_entry(db, entry_id=entry_id)
            if db_entry is None:
                raise HTTPException(status_code=404, detail=f"Entry not found: {entry_id}")

            if len(path_parts) >= 2:
                field_name = path_parts[1]
                if field_name not in ["key", "value", "disabled", "sequence", "folderPath"]:
                    raise HTTPException(status_code=400, detail=f"Cannot modify field: {field_name}")
                if field_name == "key":
                    if db_domain.domainType != "lookup":
                        raise HTTPException(status_code=400, detail="Key field is not applicable for valueList domain type")
                    if value is None or not isinstance(value, str) or not value.strip():
                        raise HTTPException(status_code=400, detail="Key must be a non-empty string")
                    existing_all = await crud.get_all_entries_by_content_id(db, content_id=content_id)
                    existing_keys = [e.key for e in existing_all if e.key and e.id != entry_id]
                    if value in existing_keys:
                        raise HTTPException(status_code=400, detail=f"Key '{value}' already exists")
                    db_entry.key = value
                elif field_name == "value":
                    if value is None or not isinstance(value, str) or not value.strip():
                        raise HTTPException(status_code=400, detail="Value must be a non-empty string")
                    db_entry.value = value
                elif field_name == "disabled":
                    if isinstance(value, bool):
                        db_entry.disabled = value
                    elif isinstance(value, str):
                        db_entry.disabled = value.strip().lower() in ("true", "1", "yes", "y", "t")
                    elif isinstance(value, (int, float)):
                        db_entry.disabled = bool(value)
                    else:
                        raise HTTPException(status_code=400, detail="disabled must be a boolean or boolean string")
                elif field_name == "sequence":
                    if isinstance(value, bool):
                        db_entry.sequence = int(value)
                    elif isinstance(value, int):
                        db_entry.sequence = value
                    elif isinstance(value, str):
                        try:
                            db_entry.sequence = int(value.strip())
                        except ValueError:
                            raise HTTPException(status_code=400, detail=f"Invalid sequence value: {value}")
                    else:
                        raise HTTPException(status_code=400, detail="sequence must be an integer")
                elif field_name == "folderPath":
                    if value is None:
                        db_entry.folderPath = None
                    elif isinstance(value, str):
                        db_entry.folderPath = value.strip() or None
                    else:
                        raise HTTPException(status_code=400, detail="folderPath must be a string")
                db_entry.modifiedTimeStamp = datetime.utcnow()
                db_entry.version += 1
                await db.commit()
                await db.refresh(db_entry)
            else:
                if value is None:
                    raise HTTPException(status_code=400, detail="Value is required for 'replace' operation")
                if "key" in value and value["key"] is not None:
                    if db_domain.domainType != "lookup":
                        raise HTTPException(status_code=400, detail="Key field is not applicable for valueList domain type")
                    existing_all = await crud.get_all_entries_by_content_id(db, content_id=content_id)
                    existing_keys = [e.key for e in existing_all if e.key and e.id != entry_id]
                    if value["key"] in existing_keys:
                        raise HTTPException(status_code=400, detail=f"Key '{value['key']}' already exists")
                if not value.get("value"):
                    raise HTTPException(status_code=400, detail="Entry 'value' is required")
                try:
                    update_data = schemas.EntryUpdate(**value)
                except ValidationError as e:
                    raise HTTPException(status_code=400, detail=str(e))
                updated = await crud.update_entry(db, entry_id=entry_id, entry=update_data)
                if updated is None:
                    raise HTTPException(status_code=404, detail=f"Entry not found: {entry_id}")

        elif op == "delete":
            if len(path_parts) < 1:
                raise HTTPException(status_code=400, detail="Path must reference an entry ID for 'delete' operation")
            entry_id = path_parts[0]
            success = await crud.delete_entry(db, entry_id=entry_id)
            if not success:
                raise HTTPException(status_code=404, detail=f"Entry not found: {entry_id}")

    all_entries = await crud.get_all_entries_by_content_id(db, content_id=content_id)
    items = [entry_to_response(request, domain_id, content_id, e) for e in all_entries]
    return JSONResponse(content=items, media_type=MEDIA_TYPE_ENTRY)


@app.delete(ENTRIES_PATH, status_code=status.HTTP_204_NO_CONTENT)
async def delete_entries(
    domain_id: str,
    content_id: str,
    db: AsyncSession = Depends(get_db),
):
    _, db_content = await validate_content_and_domain(db, domain_id, content_id)
    check_production_protection(db_content)
    await crud.delete_all_entries_by_content_id(db, content_id=content_id)
    return Response(status_code=204)


DOMAIN_ENTRIES_HEADERS = [
    "domainName",
    "domainDescription",
    "folderPath",
    "key",
    "value",
    "disabled",
    "sequence",
    "domainType",
]


def domain_entries_to_csv(rows: List[Dict[str, Any]], header: bool) -> str:
    output = io.StringIO()
    writer = csv.writer(output, lineterminator="\n")
    if header:
        writer.writerow(DOMAIN_ENTRIES_HEADERS)
    for row in rows:
        writer.writerow([row.get(h, "") if row.get(h) is not None else "" for h in DOMAIN_ENTRIES_HEADERS])
    return output.getvalue()


def parse_csv_body(body: str) -> List[Dict[str, str]]:
    if not body:
        raise HTTPException(status_code=400, detail="CSV body is empty")
    stream = io.StringIO(body)
    reader = csv.reader(stream)
    try:
        header_row = next(reader)
    except StopIteration:
        return []
    if len(header_row) != 8:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid CSV format: expected 8 columns, got {len(header_row)}",
        )
    header_row = [h.strip() for h in header_row]
    missing = [h for h in DOMAIN_ENTRIES_HEADERS if h not in header_row]
    if missing:
        raise HTTPException(
            status_code=400,
            detail=f"CSV header is missing required columns: {', '.join(missing)}",
        )
    idx = {h: header_row.index(h) for h in DOMAIN_ENTRIES_HEADERS}
    rows = []
    for lineno, raw in enumerate(reader, start=2):
        if not raw or all(not (c or "").strip() for c in raw):
            continue
        if len(raw) != 8:
            raise HTTPException(
                status_code=400,
                detail=f"Invalid CSV format: expected 8 columns, got {len(raw)} at line {lineno}",
            )
        row = {h: raw[idx[h]] for h in DOMAIN_ENTRIES_HEADERS}
        rows.append(row)
    return rows


@app.get(f"{API_BASE}/domainEntries/")
async def export_domain_entries_csv(
    request: Request,
    header: str = "",
    db: AsyncSession = Depends(get_db),
):
    include_header = str(header).strip().lower() == "present"
    results = await crud.get_all_entries_all_domains(db)
    rows = []
    for entry, content, domain in results:
        rows.append(
            {
                "domainName": domain.name or "",
                "domainDescription": domain.description or "",
                "folderPath": entry.folderPath or "",
                "key": entry.key or "",
                "value": entry.value or "",
                "disabled": "true" if entry.disabled else "false",
                "sequence": str(entry.sequence or 0),
                "domainType": domain.domainType or "",
            }
        )
    csv_data = domain_entries_to_csv(rows, include_header)
    return Response(content=csv_data, media_type="text/csv")


@app.post(f"{API_BASE}/domainEntries/", status_code=status.HTTP_201_CREATED)
async def import_domain_entries_csv(
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    content_type = request.headers.get("content-type", "")
    if "text/csv" not in content_type and "application/json" not in content_type:
        raise HTTPException(
            status_code=400,
            detail="Content-Type must be text/csv or application/json",
        )

    if "application/json" in content_type:
        payload = await request.json()
        if isinstance(payload, dict):
            rows = payload.get("rows") or payload.get("entries") or []
        else:
            rows = payload
        if not isinstance(rows, list):
            raise HTTPException(status_code=400, detail="JSON payload must be a list of row objects")
    else:
        body = (await request.body()).decode("utf-8-sig")
        rows = parse_csv_body(body)

    if not rows:
        raise HTTPException(status_code=400, detail="No data rows provided")

    try:
        created = await crud.bulk_import_domain_entries(db, rows=rows)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    return JSONResponse(
        content={"count": len(created), "message": "Import completed successfully"},
        media_type="application/json",
        status_code=201,
    )
