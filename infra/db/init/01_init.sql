-- ─────────────────────────────────────────────────────────────────
-- NIA Platform — PostgreSQL init script
-- Se ejecuta UNA VEZ al levantar el contenedor de postgres en dev.
-- Las migraciones Alembic se encargan del schema después.
-- ─────────────────────────────────────────────────────────────────

-- Extensiones requeridas
CREATE EXTENSION IF NOT EXISTS "uuid-ossp";
CREATE EXTENSION IF NOT EXISTS "pg_trgm";         -- búsqueda fuzzy de texto
CREATE EXTENSION IF NOT EXISTS "unaccent";         -- comparación sin tildes
CREATE EXTENSION IF NOT EXISTS "pg_stat_statements"; -- análisis de queries

-- Schema público: usado por tenant-manager para metadatos globales
-- Los schemas por tenant se crean dinámicamente en el provisioning.
