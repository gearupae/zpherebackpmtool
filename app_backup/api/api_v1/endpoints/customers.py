from typing import Any, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select, and_, or_, func, case
from sqlalchemy.orm import selectinload
import uuid

from ....db.database import get_db
from ....models.customer import Customer as CustomerModel
from ....models.user import User
from ....models.project import Project
from ....schemas.customer import (
    Customer, CustomerCreate, CustomerUpdate, CustomerList, CustomerStats
)
from ...deps import get_current_active_user, require_manager

router = APIRouter()


@router.get("/", response_model=CustomerList)
async def get_customers(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    search: Optional[str] = None,
    customer_type: Optional[str] = None,
    is_active: Optional[bool] = None,
) -> Any:
    """Get customers with pagination and filtering"""
    
    # Build base query
    query = select(CustomerModel).where(
        CustomerModel.organization_id == current_user.organization_id
    )
    
    # Apply filters
    if search:
        search_filter = or_(
            CustomerModel.first_name.ilike(f"%{search}%"),
            CustomerModel.last_name.ilike(f"%{search}%"),
            CustomerModel.company_name.ilike(f"%{search}%"),
            CustomerModel.email.ilike(f"%{search}%")
        )
        query = query.where(search_filter)
    
    if customer_type:
        query = query.where(CustomerModel.customer_type == customer_type)
    
    if is_active is not None:
        query = query.where(CustomerModel.is_active == is_active)
    
    # Get total count
    count_query = select(func.count()).select_from(query.subquery())
    total_result = await db.execute(count_query)
    total = total_result.scalar()
    
    # Apply pagination
    query = query.offset((page - 1) * size).limit(size)
    query = query.order_by(CustomerModel.created_at.desc())
    
    # Execute query
    result = await db.execute(query)
    customers = result.scalars().all()
    
    # Calculate pagination info
    pages = (total + size - 1) // size
    
    return CustomerList(
        customers=customers,
        total=total,
        page=page,
        size=size,
        pages=pages
    )


@router.get("/stats", response_model=CustomerStats)
async def get_customer_stats(
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get customer statistics"""
    
    # Get customer counts by type
    stats_query = select(
        func.count().label("total"),
        func.coalesce(func.sum(case((CustomerModel.is_active == True, 1), else_=0)), 0).label("active"),
        func.coalesce(func.sum(case((CustomerModel.customer_type == "prospect", 1), else_=0)), 0).label("prospects"),
        func.coalesce(func.sum(case((CustomerModel.customer_type == "client", 1), else_=0)), 0).label("clients"),
        func.coalesce(func.sum(case((CustomerModel.customer_type == "lead", 1), else_=0)), 0).label("leads"),
        func.coalesce(func.sum(case((CustomerModel.is_active == False, 1), else_=0)), 0).label("inactive")
    ).where(CustomerModel.organization_id == current_user.organization_id)
    
    stats_result = await db.execute(stats_query)
    stats = stats_result.first()
    
    # Get project count and revenue
    project_query = select(
        func.count().label("total_projects"),
        func.coalesce(func.sum(Project.budget), 0).label("total_revenue")
    ).join(CustomerModel).where(
        and_(
            Project.organization_id == current_user.organization_id,
            Project.customer_id == CustomerModel.id
        )
    )
    
    project_result = await db.execute(project_query)
    project_stats = project_result.first()
    
    return CustomerStats(
        total_customers=stats.total or 0,
        active_customers=stats.active or 0,
        prospects=stats.prospects or 0,
        clients=stats.clients or 0,
        leads=stats.leads or 0,
        inactive_customers=stats.inactive or 0,
        total_projects=project_stats.total_projects or 0,
        total_revenue=project_stats.total_revenue or 0
    )


@router.get("/{customer_id}", response_model=Customer)
async def get_customer(
    customer_id: str,
    current_user: User = Depends(get_current_active_user),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Get a specific customer by ID"""
    
    result = await db.execute(
        select(CustomerModel).where(
            and_(
                CustomerModel.id == customer_id,
                CustomerModel.organization_id == current_user.organization_id
            )
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    return customer


@router.post("/", response_model=Customer, status_code=status.HTTP_201_CREATED)
async def create_customer(
    customer_data: CustomerCreate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Create a new customer"""
    
    # Check if email already exists in organization
    existing_customer = await db.execute(
        select(CustomerModel).where(
            and_(
                CustomerModel.email == customer_data.email,
                CustomerModel.organization_id == current_user.organization_id
            )
        )
    )
    if existing_customer.scalar_one_or_none():
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Customer with this email already exists"
        )
    
    # Create customer
    customer = CustomerModel(
        id=str(uuid.uuid4()),
        organization_id=current_user.organization_id,
        **customer_data.model_dump()
    )
    
    db.add(customer)
    await db.commit()
    await db.refresh(customer)
    
    return customer


@router.put("/{customer_id}", response_model=Customer)
async def update_customer(
    customer_id: str,
    customer_data: CustomerUpdate,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
) -> Any:
    """Update a customer"""
    
    # Get customer
    result = await db.execute(
        select(CustomerModel).where(
            and_(
                CustomerModel.id == customer_id,
                CustomerModel.organization_id == current_user.organization_id
            )
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Check email uniqueness if changing
    if customer_data.email and customer_data.email != customer.email:
        existing_customer = await db.execute(
            select(CustomerModel).where(
                and_(
                    CustomerModel.email == customer_data.email,
                    CustomerModel.organization_id == current_user.organization_id,
                    CustomerModel.id != customer_id
                )
            )
        )
        if existing_customer.scalar_one_or_none():
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Customer with this email already exists"
            )
    
    # Update customer
    update_data = customer_data.model_dump(exclude_unset=True)
    for field, value in update_data.items():
        setattr(customer, field, value)
    
    await db.commit()
    await db.refresh(customer)
    
    return customer


@router.delete("/{customer_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_customer(
    customer_id: str,
    current_user: User = Depends(require_manager),
    db: AsyncSession = Depends(get_db),
):
    """Delete a customer (soft delete by setting is_active to False)"""
    
    # Get customer
    result = await db.execute(
        select(CustomerModel).where(
            and_(
                CustomerModel.id == customer_id,
                CustomerModel.organization_id == current_user.organization_id
            )
        )
    )
    customer = result.scalar_one_or_none()
    
    if not customer:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Customer not found"
        )
    
    # Check if customer has active projects
    project_query = select(func.count()).where(
        and_(
            Project.customer_id == customer_id,
            Project.status.in_(["planning", "active", "on_hold"])
        )
    )
    project_result = await db.execute(project_query)
    active_projects = project_result.scalar()
    
    if active_projects > 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot delete customer with active projects"
        )
    
    # Soft delete
    customer.is_active = False
    await db.commit()
