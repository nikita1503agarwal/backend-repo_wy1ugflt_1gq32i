import os
from datetime import datetime, timedelta, timezone
from typing import Optional, List, Dict, Any

from fastapi import FastAPI, HTTPException, Depends
from fastapi.middleware.cors import CORSMiddleware
from fastapi.security import OAuth2PasswordBearer
from pydantic import BaseModel, EmailStr
from bson import ObjectId
import jwt
import bcrypt

from database import db, create_document, get_documents

app = FastAPI(title="East Link Connect API", description="Connect businesses, products, attractions, and community updates across the Eastern Region of Ghana.")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

JWT_SECRET = os.getenv("JWT_SECRET", "dev-secret")
JWT_ALGORITHM = "HS256"
ACCESS_TOKEN_EXPIRE_MINUTES = 60 * 24 * 7  # 7 days

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")


@app.get("/")
def root():
    return {"name": "East Link Connect API", "status": "ok"}


# Schemas endpoint for admin tooling
@app.get("/schema")
def get_schema():
    try:
        from schemas import Business, Product, Attraction, Review, Update, User  # noqa: F401
        return {"status": "ok", "collections": ["business", "product", "attraction", "review", "update", "user"]}
    except Exception as e:
        return {"status": "error", "detail": str(e)}


# Helper to convert ObjectId to string

def serialize_doc(doc: Dict[str, Any]):
    if not doc:
        return doc
    doc = dict(doc)
    _id = doc.get("_id")
    if isinstance(_id, ObjectId):
        doc["id"] = str(_id)
        del doc["_id"]
    return doc


# =============== AUTH ===============
class UserCreate(BaseModel):
    name: str
    email: EmailStr
    password: str
    avatar: Optional[str] = None


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: Dict[str, Any]


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt()).decode("utf-8")


def verify_password(password: str, hashed: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), hashed.encode("utf-8"))
    except Exception:
        return False


def create_access_token(data: dict, expires_delta: Optional[timedelta] = None):
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + (expires_delta or timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES))
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, JWT_SECRET, algorithm=JWT_ALGORITHM)


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    if db is None:
        raise HTTPException(status_code=500, detail="Database not configured")
    user = db["user"].find_one({"email": email})
    return user


def get_current_user(token: str = Depends(oauth2_scheme)):
    credentials_exception = HTTPException(status_code=401, detail="Could not validate credentials")
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[JWT_ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except Exception:
        raise credentials_exception
    user = db["user"].find_one({"_id": ObjectId(user_id)})
    if not user:
        raise credentials_exception
    user = serialize_doc(user)
    # don't expose hashed password
    user.pop("hashed_password", None)
    return user


@app.post("/auth/register", response_model=TokenResponse)
def register(user_in: UserCreate):
    from schemas import User
    if get_user_by_email(user_in.email):
        raise HTTPException(status_code=400, detail="Email already registered")
    user_doc = User(
        name=user_in.name,
        email=user_in.email,
        hashed_password=hash_password(user_in.password),
        avatar=user_in.avatar,
    ).model_dump()
    inserted_id = db["user"].insert_one(user_doc).inserted_id
    access_token = create_access_token({"sub": str(inserted_id)})
    public_user = serialize_doc({"_id": inserted_id, **user_doc})
    public_user.pop("hashed_password", None)
    return {"access_token": access_token, "user": public_user, "token_type": "bearer"}


@app.post("/auth/login", response_model=TokenResponse)
def login(payload: LoginRequest):
    user = get_user_by_email(payload.email)
    if not user or not verify_password(payload.password, user.get("hashed_password", "")):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    token = create_access_token({"sub": str(user["_id"])})
    user_pub = serialize_doc(user)
    user_pub.pop("hashed_password", None)
    return {"access_token": token, "user": user_pub, "token_type": "bearer"}


@app.get("/auth/me")
def me(current_user: dict = Depends(get_current_user)):
    return current_user


class FollowUpdate(BaseModel):
    towns: List[str] = []


@app.patch("/auth/follow")
def update_follows(payload: FollowUpdate, current_user: dict = Depends(get_current_user)):
    # Update the user's followed towns/tags
    user_id = current_user.get("id")
    if not user_id:
        raise HTTPException(status_code=400, detail="Invalid user")
    db["user"].update_one({"_id": ObjectId(user_id)}, {"$set": {"follows": payload.towns, "updated_at": datetime.now(timezone.utc)}})
    user = db["user"].find_one({"_id": ObjectId(user_id)})
    user = serialize_doc(user)
    user.pop("hashed_password", None)
    return user


# =============== CORE ENTITIES ===============
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
def create_business(payload: BusinessIn, current_user: dict = Depends(get_current_user)):
    from schemas import Business
    try:
        biz = Business(**payload.model_dump())
        inserted_id = create_document("business", biz)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/businesses")
def list_businesses(q: Optional[str] = None, town: Optional[str] = None, category: Optional[str] = None, limit: int = 50):
    filter_dict: Dict[str, Any] = {}
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
def create_product(payload: ProductIn, current_user: dict = Depends(get_current_user)):
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
    filter_dict: Dict[str, Any] = {}
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
def create_attraction(payload: AttractionIn, current_user: dict = Depends(get_current_user)):
    from schemas import Attraction
    try:
        doc = Attraction(**payload.model_dump())
        inserted_id = create_document("attraction", doc)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/attractions")
def list_attractions(q: Optional[str] = None, town: Optional[str] = None, limit: int = 50):
    filter_dict: Dict[str, Any] = {}
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
def create_review(payload: ReviewIn, current_user: dict = Depends(get_current_user)):
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
    filter_dict: Dict[str, Any] = {}
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
def create_update(payload: UpdateIn, current_user: dict = Depends(get_current_user)):
    from schemas import Update
    try:
        doc = Update(**payload.model_dump())
        inserted_id = create_document("update", doc)
        return {"id": inserted_id}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))


@app.get("/api/updates")
def list_updates(town: Optional[str] = None, category: Optional[str] = None, q: Optional[str] = None, limit: int = 50):
    filter_dict: Dict[str, Any] = {}
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


# Stories feed (latest updates, optionally filtered by followed towns)
@app.get("/stories")
def stories(towns: Optional[str] = None, limit: int = 20):
    if db is None:
        raise HTTPException(status_code=500, detail="Database not available")
    filter_dict: Dict[str, Any] = {}
    if towns:
        towns_list = [t.strip() for t in towns.split(",") if t.strip()]
        if towns_list:
            filter_dict["town"] = {"$in": towns_list}
    cursor = db["update"].find(filter_dict).sort("created_at", -1).limit(limit)
    return [serialize_doc(doc) for doc in cursor]


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
