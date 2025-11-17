"""
Database Schemas for East Link Connect

Each Pydantic model represents a MongoDB collection.
Collection name is the lowercase of the class name.
"""
from pydantic import BaseModel, Field, EmailStr
from typing import Optional, List

class Business(BaseModel):
    name: str = Field(..., description="Business name")
    owner: Optional[str] = Field(None, description="Owner name")
    category: str = Field(..., description="e.g., Food, Crafts, Tourism, Services")
    description: Optional[str] = Field(None, description="Short description")
    phone: Optional[str] = Field(None, description="Contact number")
    email: Optional[str] = Field(None, description="Contact email")
    website: Optional[str] = Field(None, description="Website or social link")
    address: Optional[str] = Field(None, description="Address or landmark")
    town: Optional[str] = Field(None, description="Town within the Eastern Region")
    region: str = Field("Eastern Region", description="Region")
    latitude: Optional[float] = Field(None, description="GPS latitude")
    longitude: Optional[float] = Field(None, description="GPS longitude")
    images: Optional[List[str]] = Field(default_factory=list, description="Image URLs")
    rating: Optional[float] = Field(None, ge=0, le=5, description="Average rating")

class Product(BaseModel):
    business_id: Optional[str] = Field(None, description="Related business id as string")
    title: str = Field(..., description="Product title")
    description: Optional[str] = Field(None, description="Product description")
    price: Optional[float] = Field(None, ge=0, description="Price in GHS")
    currency: str = Field("GHS", description="Currency code")
    category: Optional[str] = Field(None, description="Category, e.g., crafts, food")
    images: Optional[List[str]] = Field(default_factory=list, description="Image URLs")
    available: bool = Field(True, description="Available for sale")

class Attraction(BaseModel):
    name: str = Field(..., description="Attraction name")
    town: Optional[str] = Field(None, description="Town/Area")
    description: Optional[str] = Field(None, description="What to expect")
    latitude: Optional[float] = Field(None, description="GPS latitude")
    longitude: Optional[float] = Field(None, description="GPS longitude")
    images: Optional[List[str]] = Field(default_factory=list, description="Image URLs")
    tags: Optional[List[str]] = Field(default_factory=list, description="e.g., hiking, culture")

class Review(BaseModel):
    target_type: str = Field(..., description="'business' | 'product' | 'attraction'")
    target_id: str = Field(..., description="ID of the target document as string")
    author_name: Optional[str] = Field(None, description="Reviewer name")
    rating: int = Field(..., ge=1, le=5, description="Rating 1-5")
    comment: Optional[str] = Field(None, description="Review text")

class Update(BaseModel):
    title: str = Field(..., description="Update title")
    content: str = Field(..., description="Body of the update/news")
    category: Optional[str] = Field(None, description="e.g., event, announcement, market")
    town: Optional[str] = Field(None, description="Town/Area")
    images: Optional[List[str]] = Field(default_factory=list, description="Image URLs")

class User(BaseModel):
    name: str = Field(..., description="Full name")
    email: EmailStr = Field(..., description="Unique email")
    hashed_password: str = Field(..., description="BCrypt hashed password")
    avatar: Optional[str] = Field(None, description="Avatar URL")
    follows: List[str] = Field(default_factory=list, description="Followed community towns/tags")
    role: str = Field("user", description="user | admin")
