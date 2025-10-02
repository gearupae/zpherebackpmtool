from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, update, delete
from typing import List, Optional, Any
from ...deps import get_current_active_user as get_current_user
from ....models.user import User
from ....models.vendor import Vendor
from ...deps_tenant import get_tenant_db
from ....schemas.vendor import (
    VendorCreate, VendorUpdate, VendorResponse, VendorListResponse, VendorStats
)
import uuid

router = APIRouter()


@router.get("/", response_model=VendorListResponse)
async def get_vendors(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user),
    page: int = Query(1, ge=1),
    size: int = Query(10, ge=1, le=100),
    search: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    is_active: Optional[bool] = Query(None)
):
    """Get list of vendors for the current organization"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Build base query
    query = select(Vendor).where(Vendor.organization_id == current_user.organization_id)
    
    # Apply filters
    if search:
        search_filter = or_(
            Vendor.name.ilike(f"%{search}%"),
            Vendor.email.ilike(f"%{search}%"),
            Vendor.contact_person.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if category:
        query = query.where(Vendor.category == category)
    
    if is_active is not None:
        query = query.where(Vendor.is_active == is_active)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination and get results
    query = query.offset((page - 1) * size).limit(size).order_by(Vendor.created_at.desc())
    result = await db.execute(query)
    vendors = result.scalars().all()
    
    return VendorListResponse(
        vendors=[VendorResponse.model_validate(vendor) for vendor in vendors],
        total=total,
        page=page,
        size=size,
        pages=(total + size - 1) // size
    )


@router.post("/", response_model=VendorResponse)
async def create_vendor(
    vendor_data: VendorCreate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Create a new vendor"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Create vendor instance
    vendor = Vendor(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        **vendor_data.dict()
    )
    
    db.add(vendor)
    await db.commit()
    await db.refresh(vendor)
    
    return VendorResponse.model_validate(vendor)


@router.get("/{vendor_id}", response_model=VendorResponse)
async def get_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Get a specific vendor by ID"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    query = select(Vendor).where(
        and_(
            Vendor.id == vendor_id,
            Vendor.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    return VendorResponse.model_validate(vendor)


@router.put("/{vendor_id}", response_model=VendorResponse)
async def update_vendor(
    vendor_id: str,
    vendor_data: VendorUpdate,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Update a vendor"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Get existing vendor
    query = select(Vendor).where(
        and_(
            Vendor.id == vendor_id,
            Vendor.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Update vendor with provided data
    update_data = vendor_data.dict(exclude_unset=True)
    for field, value in update_data.items():
        setattr(vendor, field, value)
    
    await db.flush()
    await db.refresh(vendor)
    
    return VendorResponse.model_validate(vendor)


@router.delete("/{vendor_id}")
async def delete_vendor(
    vendor_id: str,
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Delete a vendor"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Check if vendor exists and belongs to organization
    query = select(Vendor).where(
        and_(
            Vendor.id == vendor_id,
            Vendor.organization_id == current_user.organization_id
        )
    )
    result = await db.execute(query)
    vendor = result.scalar_one_or_none()
    
    if not vendor:
        raise HTTPException(status_code=404, detail="Vendor not found")
    
    # Delete vendor
    await db.delete(vendor)
    await db.commit()
    
    return {"message": "Vendor deleted successfully"}


@router.get("/stats/overview", response_model=VendorStats)
async def get_vendor_stats(
    db: AsyncSession = Depends(get_tenant_db),
    current_user: User = Depends(get_current_user)
):
    """Get vendor statistics for the current organization"""
    if not current_user.organization_id:
        raise HTTPException(status_code=400, detail="User must belong to an organization")
    
    # Get total and active vendor counts
    total_query = select(func.count(Vendor.id)).where(Vendor.organization_id == current_user.organization_id)
    active_query = select(func.count(Vendor.id)).where(
        and_(Vendor.organization_id == current_user.organization_id, Vendor.is_active == True)
    )
    
    total_result = await db.execute(total_query)
    active_result = await db.execute(active_query)
    
    total_vendors = total_result.scalar()
    active_vendors = active_result.scalar()
    
    # Get category distribution
    category_query = select(Vendor.category, func.count(Vendor.id)).where(
        Vendor.organization_id == current_user.organization_id
    ).group_by(Vendor.category)
    category_result = await db.execute(category_query)
    by_category = {row[0]: row[1] for row in category_result.fetchall()}
    
    # Get payment terms distribution
    terms_query = select(Vendor.payment_terms, func.count(Vendor.id)).where(
        Vendor.organization_id == current_user.organization_id
    ).group_by(Vendor.payment_terms)
    terms_result = await db.execute(terms_query)
    by_payment_terms = {row[0]: row[1] for row in terms_result.fetchall()}
    
    # Get average rating
    rating_query = select(func.avg(Vendor.rating)).where(Vendor.organization_id == current_user.organization_id)
    rating_result = await db.execute(rating_query)
    average_rating = rating_result.scalar() or 0.0
    
    return VendorStats(
        total_vendors=total_vendors,
        active_vendors=active_vendors,
        inactive_vendors=total_vendors - active_vendors,
        by_category=by_category,
        by_payment_terms=by_payment_terms,
        average_rating=round(average_rating, 1)
    )
