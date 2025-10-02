from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload
import uuid

from ...deps_tenant import get_tenant_db
from ....models.item import Item as ItemModel, ItemType
from ....models.user import User
from ....schemas.item import (
    Item, ItemCreate, ItemUpdate, ItemList, ItemStats
)
from ...deps import get_current_active_user, require_manager

router = APIRouter()


@router.get("/", response_model=ItemList)
async def get_items(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    item_type: Optional[ItemType] = None,
    category: Optional[str] = None,
    is_active: Optional[bool] = None,
    is_billable: Optional[bool] = None,
) -> Any:
    """Get items with pagination and filtering"""
    
    # Build base query
    query = select(ItemModel).where(
        ItemModel.organization_id == current_user.organization_id
    )
    
    # Apply filters
    if search:
        search_filter = or_(
            ItemModel.name.ilike(f"%{search}%"),
            ItemModel.description.ilike(f"%{search}%"),
            ItemModel.sku.ilike(f"%{search}%"),
            ItemModel.category.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if item_type:
        query = query.where(ItemModel.item_type == item_type)
    
    if category:
        query = query.where(ItemModel.category == category)
    
    if is_active is not None:
        query = query.where(ItemModel.is_active == is_active)
        
    if is_billable is not None:
        query = query.where(ItemModel.is_billable == is_billable)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(ItemModel.name.asc())
    
    # Execute query
    result = await db.execute(query)
    items = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + size - 1) // size
    
    return ItemList(
        items=items,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/stats", response_model=ItemStats)
async def get_item_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get item statistics"""
    
    # Get item counts by type
    stats_query = select(
        func.count().label("total"),
        func.sum(case((ItemModel.is_active == True, 1), else_=0)).label("active"),
        func.sum(case((ItemModel.item_type == "service", 1), else_=0)).label("services"),
        func.sum(case((ItemModel.item_type == "product", 1), else_=0)).label("products"),
        func.sum(case(
            (and_(ItemModel.track_inventory == True, ItemModel.current_stock <= ItemModel.minimum_stock), 1), 
            else_=0
        )).label("low_stock"),
        func.coalesce(func.sum(ItemModel.current_stock * ItemModel.cost), 0).label("total_value")
    ).where(ItemModel.organization_id == current_user.organization_id)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.first()
    
    return ItemStats(
        total_items=stats.total or 0,
        active_items=stats.active or 0,
        services=stats.services or 0,
        products=stats.products or 0,
        low_stock_items=stats.low_stock or 0,
        total_value=stats.total_value or 0
    )


@router.get("/categories")
async def get_categories(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get all unique categories for the organization"""
    
    query = select(ItemModel.category).where(
        and_(
            ItemModel.organization_id == current_user.organization_id,
            ItemModel.category.isnot(None),
            ItemModel.category != ""
        )
    ).distinct()
    
    result = await db.execute(query)
    categories = [row[0] for row in result.fetchall()]
    
    return {"categories": sorted(categories)}


@router.get("/{item_id}", response_model=Item)
async def get_item(
    item_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Get a specific item by ID"""
    
    result = await db.execute(
        select(ItemModel).where(
            and_(
                ItemModel.id == item_id,
                ItemModel.organization_id == current_user.organization_id
            )
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    return item


@router.post("/", response_model=Item, status_code=status.HTTP_201_CREATED)
async def create_item(
    item_data: ItemCreate,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Create a new item (any active user)"""
    
    # Check if SKU already exists in organization (if provided)
    if item_data.sku:
        existing_item = await db.execute(
            select(ItemModel).where(
                and_(
                    ItemModel.sku == item_data.sku,
                    ItemModel.organization_id == current_user.organization_id
                )
            )
        )
        if existing_item.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item with this SKU already exists"
            )
    
    # Create item
    item = ItemModel(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        **item_data.model_dump()
    )
    
    db.add(item)
    await db.commit()
    await db.refresh(item)
    
    return item


@router.put("/{item_id}", response_model=Item)
async def update_item(
    item_id: str,
    item_data: ItemUpdate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update an item"""
    
    # Get item
    result = await db.execute(
        select(ItemModel).where(
            and_(
                ItemModel.id == item_id,
                ItemModel.organization_id == current_user.organization_id
            )
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # Check SKU uniqueness if changing
    if item_data.sku and item_data.sku != item.sku:
        existing_item = await db.execute(
            select(ItemModel).where(
                and_(
                    ItemModel.sku == item_data.sku,
                    ItemModel.organization_id == current_user.organization_id,
                    ItemModel.id != item_id
                )
            )
        )
        if existing_item.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Item with this SKU already exists"
            )
    
    # Update item
    update_data = item_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(item, field, value)
    
    await db.commit()
    await db.refresh(item)
    
    return item


@router.delete("/{item_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_item(
    item_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
):
    """Delete an item (soft delete by setting is_active to False)"""
    
    # Get item
    result = await db.execute(
        select(ItemModel).where(
            and_(
                ItemModel.id == item_id,
                ItemModel.organization_id == current_user.organization_id
            )
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    # Soft delete
    item.is_active = False
    await db.commit()


@router.post("/{item_id}/stock", response_model=Item)
async def update_stock(
    item_id: str,
    stock_change: int,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_tenant_db),
) -> Any:
    """Update item stock (add or subtract)"""
    
    # Get item
    result = await db.execute(
        select(ItemModel).where(
            and_(
                ItemModel.id == item_id,
                ItemModel.organization_id == current_user.organization_id
            )
        )
    )
    item = result.scalar_one_or_none()
    
    if not item:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Item not found"
        )
    
    if not item.track_inventory:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Item does not track inventory"
        )
    
    # Update stock
    new_stock = item.current_stock + stock_change
    if new_stock < 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Stock cannot be negative"
        )
    
    item.current_stock = new_stock
    await db.commit()
    await db.refresh(item)
    
    return item
