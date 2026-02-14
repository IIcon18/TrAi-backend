from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ARRAY, Index
from sqlalchemy.sql import func
from app.core.base import Base


class Product(Base):
    """База продуктов и блюд для быстрого расчета БЖУ"""
    __tablename__ = "products"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False, index=True)
    name_lower = Column(String(255), nullable=False, index=True)  # для поиска
    name_variants = Column(ARRAY(String), default=list)  # синонимы и варианты написания

    # БЖУ на 100 грамм
    calories_per_100g = Column(Float, nullable=False)
    protein_per_100g = Column(Float, nullable=False)
    fat_per_100g = Column(Float, nullable=False)
    carbs_per_100g = Column(Float, nullable=False)

    # Метаданные
    category = Column(String(50))  # "крупы", "мясо", "овощи", "фрукты", "молочное", etc.
    verified = Column(Boolean, default=False)  # проверено вручную
    source = Column(String(50), default="manual")  # "manual", "usda", "ai"

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())

    __table_args__ = (
        Index('idx_name_lower', 'name_lower'),
        Index('idx_category', 'category'),
    )


class AINutritionCache(Base):
    """Кеш результатов AI анализа блюд"""
    __tablename__ = "ai_nutrition_cache"

    id = Column(Integer, primary_key=True, index=True)
    dish_name = Column(String(255), nullable=False)
    normalized_name = Column(String(255), nullable=False, unique=True, index=True)

    # БЖУ на указанные граммы (сохраняем как есть)
    grams = Column(Float, nullable=False)
    calories = Column(Float, nullable=False)
    protein = Column(Float, nullable=False)
    fat = Column(Float, nullable=False)
    carbs = Column(Float, nullable=False)

    # Также сохраняем на 100г для переиспользования
    calories_per_100g = Column(Float, nullable=False)
    protein_per_100g = Column(Float, nullable=False)
    fat_per_100g = Column(Float, nullable=False)
    carbs_per_100g = Column(Float, nullable=False)

    # Метаданные
    source = Column(String(50))  # "github_models", "gemini"
    verified = Column(Boolean, default=False)
    usage_count = Column(Integer, default=1)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
    last_used_at = Column(DateTime(timezone=True), server_default=func.now())

    __table_args__ = (
        Index('idx_normalized_name', 'normalized_name'),
    )
