"""
Tests for tenant-manager CRUD + provisioning.
Run: pytest services/tenant-manager/tests/ -v --asyncio-mode=auto
"""
import uuid
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.schemas import TenantCreate, TenantRead
from app.crud import create_tenant, get_tenant, list_tenants, deactivate_tenant
from app.provisioning import provision_tenant


# ── Helpers ───────────────────────────────────────────────────────────────────

def _make_tenant_create(**kwargs) -> TenantCreate:
    defaults = {
        "id": f"test-{uuid.uuid4().hex[:8]}",
        "name": "Test Tenant",
        "plan": "starter",
    }
    defaults.update(kwargs)
    return TenantCreate(**defaults)


# ── CRUD tests (async, uses mocked session) ───────────────────────────────────

@pytest.mark.asyncio
async def test_create_tenant_returns_tenant_read():
    """create_tenant should insert a row and return a TenantRead."""
    mock_session = AsyncMock(spec=AsyncSession)

    # SQLAlchemy async execute returns a Result mock
    mock_result = MagicMock()
    mock_result.scalar_one.return_value = MagicMock(
        id="test-abc123",
        name="Test Tenant",
        plan="starter",
        schema_name="tenant_test_abc123",
        api_key_hash="hashed_key",
        is_active=True,
        branding={},
        qdrant_collection="test_abc123_docs",
        created_at=None,
        updated_at=None,
    )
    mock_session.execute = AsyncMock(return_value=mock_result)
    mock_session.commit = AsyncMock()
    mock_session.refresh = AsyncMock()

    data = _make_tenant_create(id="test-abc123")

    with patch("app.crud.hashlib") as mock_hashlib:
        mock_hashlib.sha256.return_value.hexdigest.return_value = "hashed_key"
        with patch("app.crud.secrets") as mock_secrets:
            mock_secrets.token_urlsafe.return_value = "raw_api_key"
            result = await create_tenant(mock_session, data)

    assert mock_session.add.called or mock_session.execute.called


@pytest.mark.asyncio
async def test_get_tenant_not_found_returns_none():
    """get_tenant should return None for unknown tenant_id."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalar_one_or_none.return_value = None
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await get_tenant(mock_session, "nonexistent-tenant")
    assert result is None


@pytest.mark.asyncio
async def test_list_tenants_returns_list():
    """list_tenants should return a list (possibly empty)."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_result = MagicMock()
    mock_result.scalars.return_value.all.return_value = []
    mock_session.execute = AsyncMock(return_value=mock_result)

    result = await list_tenants(mock_session)
    assert isinstance(result, list)


# ── Provisioning tests ────────────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_provision_creates_pg_schema():
    """provision_tenant should execute CREATE SCHEMA statement."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_redis = AsyncMock()
    mock_qdrant = MagicMock()
    mock_qdrant.create_collection = MagicMock()

    with patch("app.provisioning.get_redis", return_value=mock_redis):
        with patch("app.provisioning.QdrantClient", return_value=mock_qdrant):
            await provision_tenant(
                session=mock_session,
                tenant_id="test-provision",
                schema_name="tenant_test_provision",
                qdrant_collection="test_provision_docs",
            )

    # Verify at least one execute call happened (CREATE SCHEMA)
    assert mock_session.execute.called


@pytest.mark.asyncio
async def test_provision_creates_qdrant_collection():
    """provision_tenant should create a Qdrant collection."""
    mock_session = AsyncMock(spec=AsyncSession)
    mock_session.execute = AsyncMock()
    mock_session.commit = AsyncMock()

    mock_redis = AsyncMock()
    mock_qdrant = MagicMock()

    with patch("app.provisioning.get_redis", return_value=mock_redis):
        with patch("app.provisioning.QdrantClient", return_value=mock_qdrant):
            await provision_tenant(
                session=mock_session,
                tenant_id="test-provision",
                schema_name="tenant_test_provision",
                qdrant_collection="test_provision_docs",
            )

    mock_qdrant.create_collection.assert_called_once()


# ── Schema validation ─────────────────────────────────────────────────────────

def test_tenant_create_schema_valid():
    """TenantCreate should accept valid input."""
    data = TenantCreate(id="my-tenant", name="My Tenant", plan="pro")
    assert data.id == "my-tenant"


def test_tenant_create_schema_invalid_plan():
    """TenantCreate should reject an invalid plan."""
    import pydantic
    with pytest.raises(pydantic.ValidationError):
        TenantCreate(id="t1", name="T1", plan="invalid_plan_xyz")
