import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional, List
from bson import ObjectId

from database import db, create_document, get_documents

app = FastAPI(title="Akuapem Connect API", description="Connect businesses, products, attractions, and community updates across the Eastern Region of Ghana.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def root():
    return {"name": "Akuapem Connect API", "status": "ok"}

# Schemas endpoint for admin tooling
@app.get("/schema")
def get_schema():
    try:
        from schemas import Business, Product, Attraction, Review, Update  # noqa: F401
        return {"status": "ok", "collections": ["business", "product", "attraction", "review", "update"]}
    except Exception as e:
        return {"status": "error", "detail": str(e)}

# Helper to convert ObjectId to string

def serialize_doc(doc):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    return doc

# Business Endpoints
class BusinessIn(BaseModel):
    name: str
    category: str
    description: Optional[str] = None
    phone: Optional[str] = None
    email: Optional[str] = None
    website: Optional[str] = None
    address: Optional[str] = None
    town: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    images: Optional[List[str]] = None

@app.post("/api/businesses")
def create_business(payload: BusinessIn):
    from schemas import Business
    try:
        biz = Business(**payload.model_dump())
        inserted_id = create_document("business", biz)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/businesses")
def list_businesses(q: Optional[str] = None, town: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
    filter_dict = {}
    if town:
        filter_dict["town"] = {"$regex": town, "$options": "i"}
    if category:
        filter_dict["category"] = {"$regex": category, "$options": "i"}
    if q:
        filter_dict["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"town": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("business", filter_dict, limit)
    return [serialize_doc(d) for d in docs]

# Product Endpoints
class ProductIn(BaseModel):
    business_id: Optional[str] = None
    title: str
    description: Optional[str] = None
    price: Optional[float] = None
    currency: Optional[str] = "GHS"
    category: Optional[str] = None
    images: Optional[List[str]] = None
    available: Optional[bool] = True

@app.post("/api/products")
def create_product(payload: ProductIn):
    from schemas import Product
    data = payload.model_dump()
    try:
        if data.get("business_id"):
            try:
                data["business_id"] = str(ObjectId(data["business_id"]))
            except Exception:
                pass
        prod = Product(**data)
        inserted_id = create_document("product", prod)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/products")
def list_products(business_id: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
    filter_dict = {}
    if business_id:
        filter_dict["business_id"] = business_id
    if q:
        filter_dict["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("product", filter_dict, limit)
    return [serialize_doc(d) for d in docs]

# Attractions
class AttractionIn(BaseModel):
    name: str
    town: Optional[str] = None
    description: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    images: Optional[List[str]] = None
    tags: Optional[List[str]] = None

@app.post("/api/attractions")
def create_attraction(payload: AttractionIn):
    from schemas import Attraction
    try:
        doc = Attraction(**payload.model_dump())
        inserted_id = create_document("attraction", doc)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/attractions")
def list_attractions(q: Optional[str] = None, town: Optional[str] = None, limit: int = 50):
    filter_dict = {}
    if town:
        filter_dict["town"] = {"$regex": town, "$options": "i"}
    if q:
        filter_dict["$or"] = [
            {"name": {"$regex": q, "$options": "i"}},
            {"description": {"$regex": q, "$options": "i"}},
            {"tags": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("attraction", filter_dict, limit)
    return [serialize_doc(d) for d in docs]

# Reviews
class ReviewIn(BaseModel):
    target_type: str
    target_id: str
    author_name: Optional[str] = None
    rating: int
    comment: Optional[str] = None

@app.post("/api/reviews")
def create_review(payload: ReviewIn):
    from schemas import Review
    try:
        if payload.target_type not in {"business", "product", "attraction"}:
            raise HTTPException(status_code=400, detail="Invalid target_type")
        doc = Review(**payload.model_dump())
        inserted_id = create_document("review", doc)
        return {"id": inserted_id}
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/reviews")
def list_reviews(target_type: Optional[str] = None, target_id: Optional[str] = None, limit: int = 50):
    filter_dict = {}
    if target_type:
        filter_dict["target_type"] = target_type
    if target_id:
        filter_dict["target_id"] = target_id
    docs = get_documents("review", filter_dict, limit)
    return [serialize_doc(d) for d in docs]

# Community Updates
class UpdateIn(BaseModel):
    title: str
    content: str
    category: Optional[str] = None
    town: Optional[str] = None
    images: Optional[List[str]] = None

@app.post("/api/updates")
def create_update(payload: UpdateIn):
    from schemas import Update
    try:
        doc = Update(**payload.model_dump())
        inserted_id = create_document("update", doc)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@app.get("/api/updates")
def list_updates(town: Optional[str] = None, category: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
    filter_dict = {}
    if town:
        filter_dict["town"] = {"$regex": town, "$options": "i"}
    if category:
        filter_dict["category"] = {"$regex": category, "$options": "i"}
    if q:
        filter_dict["$or"] = [
            {"title": {"$regex": q, "$options": "i"}},
            {"content": {"$regex": q, "$options": "i"}},
        ]
    docs = get_documents("update", filter_dict, limit)
    return [serialize_doc(d) for d in docs]

@app.get("/test")
def test_database():
    response = {
        "backend": "✅ Running",
        "database": "❌ Not Available",
        "database_url": None,
        "database_name": None,
        "connection_status": "Not Connected",
        "collections": []
    }
    try:
        if db is not None:
            response["database"] = "✅ Available"
            response["database_url"] = "✅ Configured"
            response["database_name"] = db.name if hasattr(db, 'name') else "✅ Connected"
            response["connection_status"] = "Connected"
            try:
                collections = db.list_collection_names()
                response["collections"] = collections[:10]
                response["database"] = "✅ Connected & Working"
            except Exception as e:
                response["database"] = f"⚠️  Connected but Error: {str(e)[:50]}"
        else:
            response["database"] = "⚠️  Available but not initialized"
    except Exception as e:
        response["database"] = f"❌ Error: {str(e)[:50]}"

    response["database_url"] = "✅ Set" if os.getenv("DATABASE_URL") else "❌ Not Set"
    response["database_name"] = "✅ Set" if os.getenv("DATABASE_NAME") else "❌ Not Set"
    return response

if __name__ == "__main__":
    import uvicorn
    port = int(os.getenv("PORT", 8000))
    uvicorn.run(app, host="0.0.0.0", port=port)
