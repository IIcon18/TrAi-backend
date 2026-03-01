from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, PlainTextResponse, JSONResponse
from sqlalchemy import select

from app.api.router import api_router
from app.core import init_database
from app.core.config import settings
from app.core.test_data import create_test_data, create_admin_user
from app.core.db import AsyncSessionLocal

app = FastAPI(title="TrAi - your personal training intelligence")

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8080",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(api_router, prefix="/api/v1")


@app.on_event("startup")
async def startup_event():
    await init_database()

    from app.services import s3_service
    await s3_service.ensure_bucket_exists()

    from app.models.user import User

    async with AsyncSessionLocal() as session:
        result = await session.execute(select(User).where(User.email == "test@example.com"))
        if not result.scalar_one_or_none():
            await create_test_data(session)

        result = await session.execute(select(User).where(User.email == "admin@trai.com"))
        if not result.scalar_one_or_none():
            await create_admin_user(session)


@app.exception_handler(404)
async def not_found_handler(request: Request, exc):
    return JSONResponse(status_code=404, content={"detail": "Не найдено"})


@app.get("/robots.txt", include_in_schema=False)
async def robots_txt():
    content = (
        "User-agent: *\n"
        "Allow: /login\n"
        "Allow: /register\n"
        "Disallow: /dashboard\n"
        "Disallow: /profile\n"
        "Disallow: /progress\n"
        "Disallow: /workouts\n"
        "Disallow: /admin\n"
        "Disallow: /api/\n"
        "\n"
        f"Sitemap: {settings.FRONTEND_BASE_URL}/sitemap.xml\n"
    )
    return PlainTextResponse(content)


@app.get("/sitemap.xml", include_in_schema=False)
async def sitemap_xml():
    base = settings.FRONTEND_BASE_URL
    content = (
        '<?xml version="1.0" encoding="UTF-8"?>\n'
        '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">\n'
        "  <url>\n"
        f"    <loc>{base}/login</loc>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.8</priority>\n"
        "  </url>\n"
        "  <url>\n"
        f"    <loc>{base}/register</loc>\n"
        "    <changefreq>monthly</changefreq>\n"
        "    <priority>0.9</priority>\n"
        "  </url>\n"
        "</urlset>"
    )
    return Response(content, media_type="application/xml")


@app.get("/")
async def root():
    base_url = "http://localhost:8000"

    return {
        "app": "TrAi",
        "message": "Trai - your personal training intelligence",
        "links": {
            "Dashboard": f"{base_url}/dashboard",
            "Workouts": f"{base_url}/workouts",
            "Progress": f"{base_url}/progress",
            "Profile": f"{base_url}/profile",
            "Goals": f"{base_url}/goals",
            "Nutrition": f"{base_url}/nutrition",
            "Docs": f"{base_url}/docs",
            "ReDoc": f"{base_url}/redoc"
        }
    }
