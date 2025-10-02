from typing import Optional, List, Dict, Any
from pydantic import BaseModel, validator
from datetime import datetime
from ..models.item import ItemType, TaxType


class ItemBase(BaseModel):
    """Base item schema"""
    name: str
    description: Optional[str] = None
    sku: Optional[str] = None
    item_type: ItemType = ItemType.SERVICE
    category: Optional[str] = None
    unit_price: int = 0  # In cents
    cost: int = 0  # In cents
    unit: str = "each"
    tax_type: TaxType = TaxType.TAXABLE
    default_tax_rate: int = 0  # Tax rate percentage * 100
    track_inventory: bool = False
    current_stock: int = 0
    minimum_stock: int = 0
    is_active: bool = True
    is_billable: bool = True
    tags: List[str] = []
    custom_fields: Dict[str, Any] = {}
    notes: Optional[str] = None

    @validator('unit_price', 'cost', 'default_tax_rate')
    def validate_positive_integers(cls, v):
        if v < 0:
            raise ValueError('Value must be non-negative')
        return v

    @validator('current_stock', 'minimum_stock')
    def validate_stock(cls, v):
        if v < 0:
            raise ValueError('Stock values must be non-negative')
        return v


class ItemCreate(ItemBase):
    """Schema for creating an item"""
    pass


class ItemUpdate(BaseModel):
    """Schema for updating an item"""
    name: Optional[str] = None
    description: Optional[str] = None
    sku: Optional[str] = None
    item_type: Optional[ItemType] = None
    category: Optional[str] = None
    unit_price: Optional[int] = None
    cost: Optional[int] = None
    unit: Optional[str] = None
    tax_type: Optional[TaxType] = None
    default_tax_rate: Optional[int] = None
    track_inventory: Optional[bool] = None
    current_stock: Optional[int] = None
    minimum_stock: Optional[int] = None
    is_active: Optional[bool] = None
    is_billable: Optional[bool] = None
    tags: Optional[List[str]] = None
    custom_fields: Optional[Dict[str, Any]] = None
    notes: Optional[str] = None

    @validator('unit_price', 'cost', 'default_tax_rate')
    def validate_positive_integers(cls, v):
        if v is not None and v < 0:
            raise ValueError('Value must be non-negative')
        return v

    @validator('current_stock', 'minimum_stock')
    def validate_stock(cls, v):
        if v is not None and v < 0:
            raise ValueError('Stock values must be non-negative')
        return v


class Item(ItemBase):
    """Item schema for responses"""
    id: str
    organization_id: str
    created_at: datetime
    updated_at: datetime
    
    # Computed fields
    display_name: str
    unit_price_display: float
    cost_display: float
    margin_percentage: float
    
    class Config:
        from_attributes = True


class ItemList(BaseModel):
    """Schema for item list responses"""
    items: List[Item]
    total: int
    page: int
    size: int
    pages: int


class ItemStats(BaseModel):
    """Item statistics"""
    total_items: int
    active_items: int
    services: int
    products: int
    low_stock_items: int
    total_value: int  # Total inventory value in cents
