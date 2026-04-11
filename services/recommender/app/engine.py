"""
Motor de recomendación basado en scoring multi-criterio.
Algoritmo: weighted_score = Σ(wi * fi) donde fi son features normalizadas.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import date, datetime, UTC
from typing import Any

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from shared.db.redis_client import RedisKeys, get_redis
from shared.models.domain import (
    AvailabilitySlot,
    IntentEntities,
    ProductAvailability,
    RecommendationItem,
    RecommendationResult,
)
from shared.utils.logging import get_logger

logger = get_logger(__name__)

# ─────────────────────────────────────────────────────────────────
# Pesos del scoring (deben sumar ~1.0)
# ─────────────────────────────────────────────────────────────────
WEIGHT_CATEGORY_MATCH = 0.30
WEIGHT_AVAILABILITY = 0.25
WEIGHT_PRICE_FIT = 0.20
WEIGHT_LANGUAGE_MATCH = 0.10
WEIGHT_DURATION_FIT = 0.10
WEIGHT_PHYSICAL_LEVEL = 0.05


async def get_recommendations(
    *,
    tenant_id: str,
    tenant_schema: str,
    entities: IntentEntities,
    session: AsyncSession,
    top_k: int = 5,
) -> RecommendationResult:
    """
    Pipeline de recomendación:
    1. Cargar productos del tenant desde PG
    2. Filtrar por disponibilidad (con cache Redis)
    3. Scoring multi-criterio
    4. Top-K
    """
    t0 = time.perf_counter()

    # 1. Cargar productos activos del tenant
    products = await _load_products(tenant_schema, session)
    if not products:
        return RecommendationResult(
            recommendations=[],
            reason="No hay productos disponibles para este tenant",
        )

    # 2. Verificar disponibilidad en paralelo (con cache)
    availability_map = await _check_availability_bulk(
        products=products,
        tenant_schema=tenant_schema,
        target_date=entities.date,
        pax_count=entities.pax_count or 1,
        session=session,
    )

    # 3. Score cada producto
    scored: list[tuple[float, dict[str, Any]]] = []
    for product in products:
        score = _compute_score(product, entities, availability_map)
        if score > 0.0:
            scored.append((score, product))

    # 4. Ordenar y Top-K
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:top_k]

    items: list[RecommendationItem] = []
    for rank, (score, product) in enumerate(top, 1):
        avail = availability_map.get(product["id"])
        slots = avail.slots if avail and avail.has_slots else []
        items.append(
            RecommendationItem(
                product_id=product["id"],
                tenant_id=tenant_id,
                name=product["name"],
                category=product.get("category", ""),
                base_price=float(product.get("base_price", 0)),
                currency=product.get("currency", "CLP"),
                duration_minutes=product.get("duration_minutes"),
                languages=product.get("languages") or [],
                score=round(score, 4),
                rank=rank,
                availability_status="available" if (avail and avail.has_slots) else "unverified",
                available_slots=slots[:3],  # máx 3 horarios mostrados
                rank_reason=_score_reason(product, entities, availability_map),
                image_url=_first_image(product),
            )
        )

    latency = (time.perf_counter() - t0) * 1000
    logger.info(
        "recommendations_computed",
        tenant_id=tenant_id,
        candidates=len(products),
        returned=len(items),
        latency_ms=round(latency),
    )

    return RecommendationResult(
        recommendations=items,
        total_candidates_evaluated=len(products),
    )


# ─────────────────────────────────────────────────────────────────
# Scoring
# ─────────────────────────────────────────────────────────────────

def _compute_score(
    product: dict[str, Any],
    entities: IntentEntities,
    availability_map: dict[str, ProductAvailability],
) -> float:
    score = 0.0

    # Categoría
    if entities.activity_type:
        cat = (product.get("category") or "").lower()
        if entities.activity_type.lower() in cat or cat in entities.activity_type.lower():
            score += WEIGHT_CATEGORY_MATCH
        else:
            score += WEIGHT_CATEGORY_MATCH * 0.3  # partial

    # Disponibilidad
    avail = availability_map.get(product["id"])
    if avail and avail.has_slots:
        score += WEIGHT_AVAILABILITY
    elif avail and not avail.error:
        score += WEIGHT_AVAILABILITY * 0.1  # no hay slots ese día
    else:
        score += WEIGHT_AVAILABILITY * 0.5  # no verificada (no penalizar completamente)

    # Precio
    if entities.budget_max:
        price = float(product.get("base_price") or 0)
        if price <= entities.budget_max:
            # Score inversamente proporcional al precio dentro del budget
            score += WEIGHT_PRICE_FIT * (1 - price / max(entities.budget_max, 1))
        else:
            score += 0  # fuera de presupuesto = no recomendar
    else:
        score += WEIGHT_PRICE_FIT * 0.5  # sin restricción de precio

    # Idioma
    langs: list[str] = product.get("languages") or []
    if entities.language_preference and langs:
        if entities.language_preference.lower() in [l.lower() for l in langs]:
            score += WEIGHT_LANGUAGE_MATCH
    else:
        score += WEIGHT_LANGUAGE_MATCH * 0.5

    # Duración
    if entities.duration_preference_hours and product.get("duration_minutes"):
        preferred_min = entities.duration_preference_hours * 60
        actual_min = int(product["duration_minutes"])
        diff = abs(preferred_min - actual_min)
        duration_score = max(0, 1 - diff / max(preferred_min, 60))
        score += WEIGHT_DURATION_FIT * duration_score
    else:
        score += WEIGHT_DURATION_FIT * 0.5

    # Nivel físico (simplificado)
    if entities.physical_level:
        attrs = product.get("attributes") or {}
        product_level = (attrs.get("physical_level") or "moderate").lower()
        entity_level = entities.physical_level.lower()
        if entity_level == product_level:
            score += WEIGHT_PHYSICAL_LEVEL
        elif entity_level == "low" and product_level == "moderate":
            score += WEIGHT_PHYSICAL_LEVEL * 0.3
    else:
        score += WEIGHT_PHYSICAL_LEVEL * 0.5

    return round(score, 4)


def _score_reason(
    product: dict[str, Any],
    entities: IntentEntities,
    availability_map: dict[str, ProductAvailability],
) -> str:
    parts = []
    avail = availability_map.get(product["id"])
    if avail and avail.has_slots:
        parts.append("disponible")
    if entities.activity_type and entities.activity_type.lower() in (product.get("category") or "").lower():
        parts.append("categoría coincide")
    if entities.budget_max and float(product.get("base_price") or 0) <= entities.budget_max:
        parts.append("dentro del presupuesto")
    return ", ".join(parts) if parts else "recomendación general"


def _first_image(product: dict[str, Any]) -> str | None:
    images = product.get("images") or []
    return images[0] if images else None


# ─────────────────────────────────────────────────────────────────
# Data loading
# ─────────────────────────────────────────────────────────────────

async def _load_products(schema: str, session: AsyncSession) -> list[dict[str, Any]]:
    """Carga productos activos del schema del tenant."""
    try:
        result = await session.execute(
            text(f"""
                SELECT id, name, category, base_price, currency,
                       duration_minutes, languages, images, attributes, tags
                FROM {schema}.products
                WHERE is_active = TRUE
                LIMIT 200
            """)
        )
        rows = result.mappings().all()
        products = []
        for row in rows:
            p = dict(row)
            # Deserializar campos JSONB que vienen como strings en algunos drivers
            for field in ("languages", "images", "attributes", "tags"):
                if isinstance(p.get(field), str):
                    try:
                        p[field] = json.loads(p[field])
                    except Exception:
                        p[field] = []
            products.append(p)
        return products
    except Exception as exc:
        logger.error("load_products_error", schema=schema, error=str(exc))
        return []


async def _check_availability_bulk(
    *,
    products: list[dict[str, Any]],
    tenant_schema: str,
    target_date: date | None,
    pax_count: int,
    session: AsyncSession,
) -> dict[str, ProductAvailability]:
    """Verifica disponibilidad para todos los productos de una vez."""
    if not target_date:
        # Sin fecha especificada: verificar próximos 7 días, tomar el primero disponible
        from datetime import timedelta
        target_date = date.today() + timedelta(days=1)

    product_ids = [p["id"] for p in products]
    results: dict[str, ProductAvailability] = {}

    # Intentar cache Redis primero
    redis = await get_redis()
    uncached_ids = []

    for pid in product_ids:
        key = RedisKeys.availability_cache(pid, str(target_date), pax_count)
        cached_raw = await redis.get(key)
        if cached_raw:
            try:
                cached_avail = ProductAvailability(**json.loads(cached_raw))
                results[pid] = cached_avail
            except Exception:
                uncached_ids.append(pid)
        else:
            uncached_ids.append(pid)

    if not uncached_ids:
        return results

    # Consultar DB para los no cacheados
    try:
        placeholders = ", ".join([f"'{pid}'" for pid in uncached_ids])
        result = await session.execute(
            text(f"""
                SELECT
                    product_id,
                    start_time,
                    (spots_total - spots_reserved) AS spots_left,
                    guide_language,
                    guide_name
                FROM {tenant_schema}.availability
                WHERE product_id IN ({placeholders})
                  AND available_date = :target_date
                  AND (spots_total - spots_reserved) >= :pax_count
                ORDER BY product_id, start_time
            """),
            {"target_date": target_date, "pax_count": pax_count},
        )
        rows = result.mappings().all()

        # Agrupar por producto
        slots_by_product: dict[str, list[AvailabilitySlot]] = {pid: [] for pid in uncached_ids}
        for row in rows:
            pid = row["product_id"]
            slots_by_product[pid].append(
                AvailabilitySlot(
                    time=str(row["start_time"])[:5],
                    spots_left=row["spots_left"],
                    guide_language=row["guide_language"] or "es",
                    guide_name=row.get("guide_name"),
                )
            )

        for pid in uncached_ids:
            slots = slots_by_product.get(pid, [])
            avail = ProductAvailability(
                product_id=pid,
                date=target_date,
                has_slots=len(slots) > 0,
                slots=slots,
                checked_at=datetime.now(UTC),
                source="db",
            )
            results[pid] = avail

            # Cachear por 5 minutos
            key = RedisKeys.availability_cache(pid, str(target_date), pax_count)
            await redis.setex(key, 300, avail.model_dump_json())

    except Exception as exc:
        logger.error("availability_check_error", error=str(exc))
        for pid in uncached_ids:
            results[pid] = ProductAvailability(
                product_id=pid,
                date=target_date,
                has_slots=False,
                slots=[],
                source="error",
                error=True,
                error_type=str(exc)[:100],
            )

    return results
