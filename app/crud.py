from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import select, func, case, and_, or_
from sqlalchemy.ext.asyncio import AsyncSession

from . import models, schemas


async def get_domain(db: AsyncSession, domain_id: str) -> Optional[models.Domain]:
    result = await db.execute(select(models.Domain).where(models.Domain.id == domain_id))
    return result.scalar_one_or_none()


async def get_domain_by_name(db: AsyncSession, name: str) -> Optional[models.Domain]:
    result = await db.execute(select(models.Domain).where(models.Domain.name == name))
    return result.scalar_one_or_none()


async def get_domains(db: AsyncSession, skip: int = 0, limit: int = 100) -> tuple[List[models.Domain], int]:
    count_result = await db.execute(select(func.count()).select_from(models.Domain))
    total = count_result.scalar_one()
    result = await db.execute(
        select(models.Domain)
        .order_by(models.Domain.name)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all(), total


async def create_domain(db: AsyncSession, domain: schemas.DomainCreate) -> models.Domain:
    db_domain = models.Domain(
        name=domain.name,
        description=domain.description,
        domainType=domain.domainType.value,
        createdBy=domain.createdBy,
        modifiedBy=domain.modifiedBy,
        properties=domain.properties,
    )
    db.add(db_domain)
    await db.commit()
    await db.refresh(db_domain)
    return db_domain


async def update_domain(db: AsyncSession, domain_id: str, domain: schemas.DomainUpdate) -> Optional[models.Domain]:
    db_domain = await get_domain(db, domain_id)
    if db_domain is None:
        return None
    update_data = domain.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_domain, key, value)
    db_domain.modifiedTimeStamp = datetime.utcnow()
    db_domain.version += 1
    await db.commit()
    await db.refresh(db_domain)
    return db_domain


async def delete_domain(db: AsyncSession, domain_id: str) -> bool:
    db_domain = await get_domain(db, domain_id)
    if db_domain is None:
        return False
    await db.delete(db_domain)
    await db.commit()
    return True


async def get_content(db: AsyncSession, content_id: str) -> Optional[models.Content]:
    result = await db.execute(select(models.Content).where(models.Content.id == content_id))
    return result.scalar_one_or_none()


async def get_contents_by_domain_id(
    db: AsyncSession, domain_id: str, skip: int = 0, limit: int = 100
) -> Tuple[List[models.Content], int]:
    count_result = await db.execute(
        select(func.count()).select_from(models.Content).where(models.Content.domainId == domain_id)
    )
    total = count_result.scalar_one()

    status_order = case(
        (models.Content.status == "production", 1),
        (models.Content.status == "candidate", 2),
        (models.Content.status == "developing", 3),
        else_=4
    )

    result = await db.execute(
        select(models.Content)
        .where(models.Content.domainId == domain_id)
        .order_by(status_order, models.Content.creationTimeStamp.desc())
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all(), total


async def get_current_production_content(db: AsyncSession, domain_id: str) -> Optional[models.Content]:
    result = await db.execute(
        select(models.Content)
        .where(
            models.Content.domainId == domain_id,
            models.Content.status == "production"
        )
        .order_by(models.Content.creationTimeStamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def get_production_contents_by_domain_id(
    db: AsyncSession, domain_id: str, skip: int = 0, limit: int = 100
) -> Tuple[List[models.Content], int]:
    base_stmt = select(models.Content).where(
        models.Content.domainId == domain_id,
        models.Content.productionStartTime.isnot(None),
    )
    count_result = await db.execute(
        select(func.count()).select_from(base_stmt)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        base_stmt
        .order_by(
            models.Content.productionStartTime.desc(),
            models.Content.creationTimeStamp.desc(),
        )
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all(), total


async def get_current_execution_content(db: AsyncSession, domain_id: str) -> Optional[models.Content]:
    result = await db.execute(
        select(models.Content)
        .where(
            models.Content.domainId == domain_id,
            models.Content.standing == "current",
        )
        .order_by(models.Content.creationTimeStamp.desc())
        .limit(1)
    )
    return result.scalar_one_or_none()


async def copy_content_to_execution(
    db: AsyncSession, source: models.Content, label: Optional[str] = None
) -> models.Content:
    major, minor = await get_next_version_numbers(db, source.domainId)
    new_label = label or f"{source.label} (execution copy)"
    new_content = models.Content(
        label=new_label,
        status="developing",
        standing="future",
        majorNumber=major,
        minorNumber=minor,
        activationStatus="active",
        createdBy=source.createdBy,
        modifiedBy=source.modifiedBy,
        domainId=source.domainId,
    )
    db.add(new_content)
    await db.flush()

    source_entries = await get_all_entries_by_content_id(db, source.id)
    for entry in source_entries:
        db_entry = models.Entry(
            key=entry.key,
            value=entry.value,
            disabled=entry.disabled,
            sequence=entry.sequence,
            folderPath=entry.folderPath,
            createdBy=entry.createdBy,
            modifiedBy=entry.modifiedBy,
            contentId=new_content.id,
        )
        db.add(db_entry)

    await db.commit()
    await db.refresh(new_content)
    return new_content


async def get_next_version_numbers(db: AsyncSession, domain_id: str) -> Tuple[int, int]:
    result = await db.execute(
        select(models.Content)
        .where(models.Content.domainId == domain_id)
        .order_by(models.Content.majorNumber.desc(), models.Content.minorNumber.desc())
        .limit(1)
    )
    latest = result.scalar_one_or_none()
    if latest is None:
        return 1, 0
    return latest.majorNumber, latest.minorNumber + 1


async def get_content_entry_count(db: AsyncSession, content_id: str) -> int:
    result = await db.execute(
        select(func.count()).select_from(models.Entry).where(models.Entry.contentId == content_id)
    )
    return result.scalar_one()


async def create_content(
    db: AsyncSession, domain_id: str, content: schemas.ContentCreate
) -> models.Content:
    db_domain = await get_domain(db, domain_id)
    if db_domain is None:
        raise ValueError("Domain not found")

    major, minor = await get_next_version_numbers(db, domain_id)
    standing = "future"
    activation_status = "active"

    if content.status == schemas.ContentStatus.production:
        raise ValueError("Content must have at least 1 entry before promoting to production")

    db_content = models.Content(
        label=content.label,
        status=content.status.value,
        standing=standing,
        majorNumber=major,
        minorNumber=minor,
        activationStatus=activation_status,
        createdBy=content.createdBy,
        modifiedBy=content.modifiedBy,
        domainId=domain_id,
    )
    db.add(db_content)
    await db.commit()
    await db.refresh(db_content)
    return db_content


async def update_content(
    db: AsyncSession, content_id: str, content: schemas.ContentUpdate
) -> Optional[models.Content]:
    db_content = await get_content(db, content_id)
    if db_content is None:
        return None

    update_data = content.model_dump(exclude_unset=True)

    if "status" in update_data:
        new_status = update_data["status"]
        if db_content.status == "production" and new_status in ["candidate", "developing"]:
            raise ValueError("Cannot change production status back to candidate or developing")

        if new_status == "production" and db_content.status != "production":
            entry_count = await get_content_entry_count(db, content_id)
            if entry_count < 1:
                raise ValueError("Content must have at least 1 entry before promoting to production")

            current_prod = await get_current_production_content(db, db_content.domainId)
            if current_prod is not None and current_prod.id != content_id:
                current_prod.standing = "legacy"
                current_prod.productionEndTime = datetime.utcnow()
                current_prod.modifiedTimeStamp = datetime.utcnow()
                current_prod.version += 1
            db_content.standing = "current"
            db_content.productionStartTime = datetime.utcnow()
            db_content.productionEndTime = None

    for key, value in update_data.items():
        if key == "status":
            setattr(db_content, key, value.value)
        elif key not in ["majorNumber", "minorNumber"]:
            setattr(db_content, key, value)

    db_content.modifiedTimeStamp = datetime.utcnow()
    db_content.version += 1
    await db.commit()
    await db.refresh(db_content)
    return db_content


async def delete_content(db: AsyncSession, content_id: str) -> bool:
    db_content = await get_content(db, content_id)
    if db_content is None:
        return False
    await db.delete(db_content)
    await db.commit()
    return True


async def get_entry(db: AsyncSession, entry_id: str) -> Optional[models.Entry]:
    result = await db.execute(select(models.Entry).where(models.Entry.id == entry_id))
    return result.scalar_one_or_none()


async def get_entries_by_content_id(
    db: AsyncSession, content_id: str, skip: int = 0, limit: int = 100
) -> Tuple[List[models.Entry], int]:
    count_result = await db.execute(
        select(func.count()).select_from(models.Entry).where(models.Entry.contentId == content_id)
    )
    total = count_result.scalar_one()

    result = await db.execute(
        select(models.Entry)
        .where(models.Entry.contentId == content_id)
        .order_by(models.Entry.creationTimeStamp)
        .offset(skip)
        .limit(limit)
    )
    return result.scalars().all(), total


async def get_all_entries_by_content_id(
    db: AsyncSession, content_id: str
) -> List[models.Entry]:
    result = await db.execute(
        select(models.Entry)
        .where(models.Entry.contentId == content_id)
        .order_by(models.Entry.creationTimeStamp)
    )
    return result.scalars().all()


async def get_all_entry_keys_by_domain_id(
    db: AsyncSession, domain_id: str
) -> List[str]:
    result = await db.execute(
        select(models.Entry.key)
        .join(models.Content, models.Entry.contentId == models.Content.id)
        .where(models.Content.domainId == domain_id, models.Entry.key.isnot(None))
    )
    return [row[0] for row in result.all()]


async def get_all_entry_values_by_domain_id(
    db: AsyncSession, domain_id: str
) -> List[str]:
    result = await db.execute(
        select(models.Entry.value)
        .join(models.Content, models.Entry.contentId == models.Content.id)
        .where(models.Content.domainId == domain_id)
    )
    return [row[0] for row in result.all()]


async def create_entry(
    db: AsyncSession, content_id: str, entry: schemas.EntryCreate
) -> models.Entry:
    db_entry = models.Entry(
        key=entry.key,
        value=entry.value,
        disabled=entry.disabled if entry.disabled is not None else False,
        sequence=entry.sequence if entry.sequence is not None else 0,
        folderPath=entry.folderPath,
        createdBy=entry.createdBy,
        modifiedBy=entry.modifiedBy,
        contentId=content_id,
    )
    db.add(db_entry)
    await db.commit()
    await db.refresh(db_entry)
    return db_entry


async def bulk_replace_entries(
    db: AsyncSession, content_id: str, entries: List[schemas.EntryCreate]
) -> List[models.Entry]:
    await delete_all_entries_by_content_id(db, content_id)
    created_entries = []
    for entry in entries:
        db_entry = models.Entry(
            key=entry.key,
            value=entry.value,
            disabled=entry.disabled if entry.disabled is not None else False,
            sequence=entry.sequence if entry.sequence is not None else 0,
            folderPath=entry.folderPath,
            createdBy=entry.createdBy,
            modifiedBy=entry.modifiedBy,
            contentId=content_id,
        )
        db.add(db_entry)
        created_entries.append(db_entry)
    await db.commit()
    for e in created_entries:
        await db.refresh(e)
    return created_entries


async def update_entry(
    db: AsyncSession, entry_id: str, entry: schemas.EntryUpdate
) -> Optional[models.Entry]:
    db_entry = await get_entry(db, entry_id)
    if db_entry is None:
        return None
    update_data = entry.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_entry, key, value)
    db_entry.modifiedTimeStamp = datetime.utcnow()
    db_entry.version += 1
    await db.commit()
    await db.refresh(db_entry)
    return db_entry


async def delete_entry(db: AsyncSession, entry_id: str) -> bool:
    db_entry = await get_entry(db, entry_id)
    if db_entry is None:
        return False
    await db.delete(db_entry)
    await db.commit()
    return True


async def delete_all_entries_by_content_id(db: AsyncSession, content_id: str) -> None:
    result = await db.execute(
        select(models.Entry).where(models.Entry.contentId == content_id)
    )
    entries = result.scalars().all()
    for entry in entries:
        await db.delete(entry)
    await db.commit()


async def get_all_entries_all_domains(db: AsyncSession):
    result = await db.execute(
        select(models.Entry, models.Content, models.Domain)
        .join(models.Content, models.Entry.contentId == models.Content.id)
        .join(models.Domain, models.Content.domainId == models.Domain.id)
        .order_by(models.Domain.name, models.Content.creationTimeStamp, models.Entry.creationTimeStamp)
    )
    return result.all()


async def bulk_import_domain_entries(
    db: AsyncSession,
    rows: list,
) -> list:
    by_domain = {}
    for r in rows:
        name = r.get("domainName")
        if not name:
            raise ValueError("domainName is required for every row")
        if name not in by_domain:
            by_domain[name] = []
        by_domain[name].append(r)
    created_entries = []
    for domain_name, domain_rows in by_domain.items():
        first = domain_rows[0]
        description = first.get("domainDescription") or None
        domain_type_raw = (first.get("domainType") or "lookup").strip().lower()
        if domain_type_raw not in ("lookup", "valuelist", "value_list"):
            raise ValueError(f"Invalid domainType '{domain_type_raw}' for domain '{domain_name}'")
        domain_type = "valueList" if domain_type_raw in ("valuelist", "value_list") else "lookup"
        created_by = first.get("createdBy") or None
        modified_by = first.get("modifiedBy") or None

        db_domain = await get_domain_by_name(db, name=domain_name)
        if db_domain is None:
            db_domain = models.Domain(
                name=domain_name,
                description=description,
                domainType=domain_type,
                createdBy=created_by,
                modifiedBy=modified_by,
            )
            db.add(db_domain)
            await db.flush()
        else:
            domain_type = db_domain.domainType

        existing_keys: set = set()
        if domain_type == "lookup":
            existing_keys = set(await get_all_entry_keys_by_domain_id(db, db_domain.id))

        existing_values: set = set()
        if domain_type == "valueList":
            existing_values = set(await get_all_entry_values_by_domain_id(db, db_domain.id))

        major, minor = await get_next_version_numbers(db, db_domain.id)
        db_content = models.Content(
            label=f"{domain_name} - imported",
            status="developing",
            standing="future",
            majorNumber=major,
            minorNumber=minor,
            activationStatus="active",
            createdBy=created_by,
            modifiedBy=modified_by,
            domainId=db_domain.id,
        )
        db.add(db_content)
        await db.flush()

        seen_keys: set = set()
        seen_values: set = set()
        for r in domain_rows:
            key = (r.get("key") or "").strip() or None
            value = (r.get("value") or "").strip()
            if not value:
                raise ValueError(f"Entry 'value' is required for domain '{domain_name}'")

            disabled_raw = r.get("disabled")
            if isinstance(disabled_raw, bool):
                disabled = disabled_raw
            else:
                disabled = str(disabled_raw or "").strip().lower() in ("true", "1", "yes", "y", "t")

            sequence_raw = r.get("sequence")
            if isinstance(sequence_raw, bool):
                sequence = int(sequence_raw)
            elif isinstance(sequence_raw, int):
                sequence = sequence_raw
            else:
                s = str(sequence_raw or "").strip()
                try:
                    sequence = int(s) if s else 0
                except ValueError:
                    raise ValueError(f"Invalid sequence value '{sequence_raw}' for domain '{domain_name}'")

            folder_path_raw = r.get("folderPath")
            folder_path = str(folder_path_raw).strip() if folder_path_raw is not None and str(folder_path_raw).strip() else None

            if domain_type == "lookup":
                if not key:
                    raise ValueError(f"Entry 'key' is required for lookup domain '{domain_name}'")
                if key in seen_keys:
                    raise ValueError(f"Duplicate key '{key}' in import batch for domain '{domain_name}'")
                if key in existing_keys:
                    raise ValueError(f"Key '{key}' already exists in domain '{domain_name}'")
                seen_keys.add(key)

            if domain_type == "valueList":
                if value in seen_values:
                    raise ValueError(f"Duplicate value '{value}' in import batch for domain '{domain_name}'")
                if value in existing_values:
                    raise ValueError(f"Value '{value}' already exists in domain '{domain_name}'")
                seen_values.add(value)

            db_entry = models.Entry(
                key=key,
                value=value,
                disabled=disabled,
                sequence=sequence,
                folderPath=folder_path,
                createdBy=created_by,
                modifiedBy=modified_by,
                contentId=db_content.id,
            )
            db.add(db_entry)
            created_entries.append(db_entry)

    await db.commit()
    for e in created_entries:
        await db.refresh(e)
    return created_entries


async def get_global_variable(db: AsyncSession, variable_id: str) -> Optional[models.GlobalVariable]:
    result = await db.execute(
        select(models.GlobalVariable).where(models.GlobalVariable.id == variable_id)
    )
    return result.scalar_one_or_none()


async def get_global_variable_by_name(db: AsyncSession, name: str) -> Optional[models.GlobalVariable]:
    result = await db.execute(
        select(models.GlobalVariable).where(models.GlobalVariable.name == name)
    )
    return result.scalar_one_or_none()


async def get_global_variables(
    db: AsyncSession,
    skip: int = 0,
    limit: int = 100,
    name: Optional[str] = None,
    data_type: Optional[str] = None,
    default_value: Optional[str] = None,
    sort_by: Optional[str] = None,
    sort_order: Optional[str] = "asc",
) -> Tuple[List[models.GlobalVariable], int]:
    stmt = select(models.GlobalVariable)
    count_stmt = select(func.count()).select_from(models.GlobalVariable)

    conditions = []
    if name:
        conditions.append(models.GlobalVariable.name.ilike(f"{name}%"))
    if data_type:
        conditions.append(models.GlobalVariable.dataType == data_type)
    if default_value:
        conditions.append(models.GlobalVariable.defaultValue.ilike(f"%{default_value}%"))

    if conditions:
        combined = and_(*conditions)
        stmt = stmt.where(combined)
        count_stmt = count_stmt.where(combined)

    count_result = await db.execute(count_stmt)
    total = count_result.scalar_one()

    valid_sort_fields = {
        "name": models.GlobalVariable.name,
        "dataType": models.GlobalVariable.dataType,
        "data_type": models.GlobalVariable.dataType,
        "defaultValue": models.GlobalVariable.defaultValue,
        "default_value": models.GlobalVariable.defaultValue,
        "creationTimeStamp": models.GlobalVariable.creationTimeStamp,
        "creation_timestamp": models.GlobalVariable.creationTimeStamp,
        "modifiedTimeStamp": models.GlobalVariable.modifiedTimeStamp,
        "modified_timestamp": models.GlobalVariable.modifiedTimeStamp,
    }

    order_column = valid_sort_fields.get(sort_by, models.GlobalVariable.name)
    if sort_order and sort_order.lower() == "desc":
        stmt = stmt.order_by(order_column.desc())
    else:
        stmt = stmt.order_by(order_column.asc())

    stmt = stmt.offset(skip).limit(limit)
    result = await db.execute(stmt)
    return result.scalars().all(), total


async def create_global_variable(
    db: AsyncSession, variable: schemas.GlobalVariableCreate
) -> models.GlobalVariable:
    db_variable = models.GlobalVariable(
        name=variable.name,
        dataType=variable.dataType.value,
        defaultValue=variable.defaultValue,
        createdBy=variable.createdBy,
        modifiedBy=variable.modifiedBy,
    )
    db.add(db_variable)
    await db.commit()
    await db.refresh(db_variable)
    return db_variable


async def update_global_variable(
    db: AsyncSession, variable_id: str, variable: schemas.GlobalVariableUpdate
) -> Optional[models.GlobalVariable]:
    db_variable = await get_global_variable(db, variable_id)
    if db_variable is None:
        return None
    update_data = variable.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(db_variable, key, value)
    db_variable.modifiedTimeStamp = datetime.utcnow()
    db_variable.version += 1
    await db.commit()
    await db.refresh(db_variable)
    return db_variable


async def delete_global_variable(db: AsyncSession, variable_id: str) -> bool:
    db_variable = await get_global_variable(db, variable_id)
    if db_variable is None:
        return False
    await db.delete(db_variable)
    await db.commit()
    return True
