# Estrategia híbrida: Monorepo + packages independientes

# Estructura propuesta:
nia-platform/                    # MONOREPO principal
├── packages/
│   ├── shared/                  # Package PyPI privado
│   ├── widget/                  # Package NPM
│   └── docs/                    # Documentación
├── services/
│   ├── core/                    # Servicios core (tenant, orchestrator)
│   ├── ai/                      # Servicios ML (model-adapter, rag)
│   └── business/                # Servicios negocio (checkout, handoff)
└── tools/
    ├── ci/                      # Scripts CI/CD
    └── dev/                     # Scripts desarrollo

# Repos separados para casos especiales:
nia-model-adapter/               # REPO INDEPENDIENTE (equipo ML)
nia-checkout/                    # REPO INDEPENDIENTE (PCI compliance) 
nia-mobile-app/                  # REPO INDEPENDIENTE (equipo mobile)

# Ventajas híbrido:
✅ Core services en monorepo (desarrollo rápido)
✅ Servicios especiales independientes (autonomía)
✅ Shared package versionado (compatibilidad)
✅ CI/CD flexible (por necesidad)