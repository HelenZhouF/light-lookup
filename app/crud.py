from datetime import datetime
from typing import List, Optional, Tuple
from sqlalchemy import select, func, case
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
    return 0


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
                current_prod.modifiedTimeStamp = datetime.utcnow()
                current_prod.version += 1
            db_content.standing = "current"

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
