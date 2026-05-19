from datetime import datetime
from typing import List, Optional
from sqlalchemy import select, func
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
