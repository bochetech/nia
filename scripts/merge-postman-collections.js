const fs = require('fs');
const path = require('path');

/**
 * Script para combinar múltiples colecciones de Postman en una sola
 * con organización por carpetas y variables compartidas
 */

const COLLECTIONS_DIR = '.postman/collections';
const OUTPUT_FILE = '.postman/NIA-Complete-Collection.json';

// Configuración base de la colección combinada
const baseCollection = {
  info: {
    name: "NIA - Neural Intelligence Assistant (Auto-generated)",
    description: "Colección generada automáticamente desde OpenAPI specs - Actualizada: " + new Date().toISOString(),
    version: "1.0.0",
    schema: "https://schema.getpostman.com/json/collection/v2.1.0/collection.json"
  },
  variable: [
    {
      key: "base_url",
      value: "http://localhost",
      description: "URL base para todos los servicios"
    },
    {
      key: "tenant_id",
      value: "demo-tenant",
      description: "ID del tenant de prueba"
    },
    {
      key: "session_id",
      value: "{{$randomUUID}}",
      description: "ID de sesión generado automáticamente"
    },
    {
      key: "auth_token",
      value: "Bearer your-jwt-token-here",
      description: "Token de autenticación JWT"
    }
  ],
  item: [],
  auth: {
    type: "bearer",
    bearer: [
      {
        key: "token",
        value: "{{auth_token}}",
        type: "string"
      }
    ]
  },
  event: [
    {
      listen: "prerequest",
      script: {
        type: "text/javascript",
        exec: [
          "// Auto-generated pre-request script",
          "console.log('🚀 NIA API Request:', pm.request.name);",
          "",
          "// Generar session_id único si no existe",
          "if (!pm.environment.get('session_id') || pm.environment.get('session_id') === '') {",
          "    pm.environment.set('session_id', pm.variables.replaceIn('{{$randomUUID}}'));",
          "}"
        ]
      }
    },
    {
      listen: "test",
      script: {
        type: "text/javascript",
        exec: [
          "// Tests automáticos globales",
          "pm.test('Response time is acceptable', function () {",
          "    pm.expect(pm.response.responseTime).to.be.below(5000);",
          "});",
          "",
          "pm.test('Status code is successful', function () {",
          "    pm.expect(pm.response.code).to.be.oneOf([200, 201, 202, 204]);",
          "});",
          "",
          "if (pm.response.headers.get('Content-Type')?.includes('application/json')) {",
          "    pm.test('Response is valid JSON', function () {",
          "        pm.expect(() => pm.response.json()).to.not.throw();",
          "    });",
          "}"
        ]
      }
    }
  ]
};

// Mapeo de servicios a puertos y iconos
const serviceConfig = {
  'orchestrator': { port: '8001', icon: '🎯', description: 'Servicio central del sistema - Maneja el flujo de conversación y FSM' },
  'rag-service': { port: '8002', icon: '📚', description: 'Servicio de Retrieval-Augmented Generation para base de conocimiento turística' },
  'tenant-manager': { port: '8003', icon: '👥', description: 'Gestión de tenants, configuración multi-tenant y autenticación' },
  'recommender': { port: '8004', icon: '🎯', description: 'Sistema de recomendaciones de productos turísticos' },
  'model-adapter': { port: '8005', icon: '🤖', description: 'Adaptador para diferentes providers de LLM (LM Studio, Vertex AI, OpenAI)' },
  'checkout': { port: '8006', icon: '💳', description: 'Servicio de checkout y gestión de reservas con integración Bokun' },
  'handoff': { port: '8007', icon: '🤝', description: 'Servicio de transferencia a agentes humanos vía Microsoft Teams' },
  'transcript': { port: '8008', icon: '📝', description: 'Servicio de transcripciones, historial de conversaciones y exportación' },
  'fallback': { port: '8009', icon: '🔄', description: 'Servicio de respuestas de contingencia cuando fallan otros servicios' }
};

function processCollection(serviceName, collectionData) {
  const config = serviceConfig[serviceName] || { port: '8000', icon: '⚙️', description: 'Servicio' };
  
  // Crear carpeta del servicio
  const serviceFolder = {
    name: `${config.icon} ${serviceName.charAt(0).toUpperCase() + serviceName.slice(1)} Service (${config.port})`,
    description: config.description,
    item: []
  };

  // Agregar variable de puerto
  baseCollection.variable.push({
    key: `${serviceName.replace('-', '_')}_port`,
    value: config.port,
    description: `Puerto del servicio ${serviceName}`
  });

  // Procesar items de la colección original
  if (collectionData.item && Array.isArray(collectionData.item)) {
    collectionData.item.forEach(item => {
      // Actualizar URLs para usar variables
      if (item.request && item.request.url) {
        updateUrlWithVariables(item.request.url, serviceName, config.port);
      }
      
      // Agregar headers comunes
      if (item.request && item.request.header) {
        addCommonHeaders(item.request.header);
      }

      serviceFolder.item.push(item);
    });
  }

  return serviceFolder;
}

function updateUrlWithVariables(url, serviceName, port) {
  const portVar = `{{${serviceName.replace('-', '_')}_port}}`;
  
  if (typeof url === 'string') {
    // URL como string
    return url.replace(new RegExp(`:${port}`, 'g'), `:${portVar}`);
  } else if (url.raw) {
    // URL como objeto
    url.raw = url.raw.replace(new RegExp(`:${port}`, 'g'), `:${portVar}`);
    if (url.host) {
      url.host = ['{{base_url}}'];
    }
    if (url.port) {
      url.port = portVar.replace(/[{}]/g, '');
    }
  }
}

function addCommonHeaders(headers) {
  // Verificar si ya tiene Content-Type
  const hasContentType = headers.some(h => h.key && h.key.toLowerCase() === 'content-type');
  if (!hasContentType) {
    headers.unshift({
      key: 'Content-Type',
      value: 'application/json'
    });
  }

  // Agregar X-Tenant-ID si no existe
  const hasTenantId = headers.some(h => h.key && h.key.toLowerCase() === 'x-tenant-id');
  if (!hasTenantId) {
    headers.push({
      key: 'X-Tenant-ID',
      value: '{{tenant_id}}'
    });
  }
}

async function mergeCollections() {
  console.log('🔗 Iniciando combinación de colecciones...');

  if (!fs.existsSync(COLLECTIONS_DIR)) {
    console.error(`❌ Directorio ${COLLECTIONS_DIR} no encontrado`);
    process.exit(1);
  }

  const collectionFiles = fs.readdirSync(COLLECTIONS_DIR)
    .filter(file => file.endsWith('.json'));

  if (collectionFiles.length === 0) {
    console.error('❌ No se encontraron archivos de colección');
    process.exit(1);
  }

  console.log(`📋 Procesando ${collectionFiles.length} colecciones...`);

  collectionFiles.forEach(file => {
    const serviceName = path.basename(file, '.json');
    const filePath = path.join(COLLECTIONS_DIR, file);
    
    try {
      const collectionData = JSON.parse(fs.readFileSync(filePath, 'utf8'));
      const serviceFolder = processCollection(serviceName, collectionData);
      
      baseCollection.item.push(serviceFolder);
      console.log(`  ✅ ${serviceName} - ${serviceFolder.item.length} endpoints`);
    } catch (error) {
      console.error(`  ❌ Error procesando ${serviceName}:`, error.message);
    }
  });

  // Crear directorio de salida si no existe
  const outputDir = path.dirname(OUTPUT_FILE);
  if (!fs.existsSync(outputDir)) {
    fs.mkdirSync(outputDir, { recursive: true });
  }

  // Guardar colección combinada
  fs.writeFileSync(OUTPUT_FILE, JSON.stringify(baseCollection, null, 2));
  
  console.log(`\n✅ Colección combinada guardada en: ${OUTPUT_FILE}`);
  console.log(`📊 Total de servicios: ${baseCollection.item.length}`);
  console.log(`📊 Total de variables: ${baseCollection.variable.length}`);
  
  const totalEndpoints = baseCollection.item.reduce((total, service) => {
    return total + (service.item ? service.item.length : 0);
  }, 0);
  console.log(`📊 Total de endpoints: ${totalEndpoints}`);
}

// Ejecutar si es llamado directamente
if (require.main === module) {
  mergeCollections().catch(console.error);
}

module.exports = { mergeCollections };