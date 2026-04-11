#!/usr/bin/env node

/**
 * Watcher de desarrollo para mantener Postman actualizado
 * Vigila cambios en los servicios y regenera automáticamente
 */

const chokidar = require('chokidar');
const { exec } = require('child_process');
const path = require('path');
const fs = require('fs');

const WATCH_PATHS = [
  'services/*/app/**/*.py',
  'services/*/main.py',
  'services/**/routers/**/*.py'
];

const DEBOUNCE_TIME = 2000; // 2 segundos
let timeout = null;
let isGenerating = false;

console.log('👀 NIA Postman Watcher iniciado...');
console.log('🔍 Vigilando cambios en:', WATCH_PATHS.join(', '));

// Verificar dependencias
checkDependencies();

// Crear watcher
const watcher = chokidar.watch(WATCH_PATHS, {
  ignored: /(__pycache__|\.pyc|\.pytest_cache)/,
  persistent: true,
  ignoreInitial: true
});

watcher
  .on('change', handleFileChange)
  .on('add', handleFileChange)
  .on('unlink', handleFileChange)
  .on('ready', () => {
    console.log('✅ Watcher ready! Esperando cambios...');
    console.log('💡 Presiona Ctrl+C para detener');
  })
  .on('error', error => {
    console.error('❌ Error en watcher:', error);
  });

function handleFileChange(filePath) {
  console.log(`🔄 Cambio detectado: ${path.relative(process.cwd(), filePath)}`);
  
  // Debounce para evitar regeneraciones múltiples
  if (timeout) {
    clearTimeout(timeout);
  }
  
  timeout = setTimeout(() => {
    if (!isGenerating) {
      generatePostmanCollection();
    }
  }, DEBOUNCE_TIME);
}

async function generatePostmanCollection() {
  if (isGenerating) {
    console.log('⏳ Ya hay una generación en proceso, saltando...');
    return;
  }

  isGenerating = true;
  console.log('\n🚀 Regenerando colección de Postman...');
  
  const startTime = Date.now();
  
  try {
    await executeCommand('chmod +x scripts/generate-postman-collection.sh');
    await executeCommand('./scripts/generate-postman-collection.sh');
    
    const duration = Date.now() - startTime;
    console.log(`✅ Colección regenerada en ${duration}ms`);
    console.log('📋 Archivo actualizado: .postman/NIA-Complete-Collection.json');
    
    // Opcional: validar la colección generada
    await validateCollection();
    
  } catch (error) {
    console.error('❌ Error generando colección:', error.message);
  } finally {
    isGenerating = false;
    console.log('\n👀 Esperando más cambios...\n');
  }
}

function executeCommand(command) {
  return new Promise((resolve, reject) => {
    exec(command, (error, stdout, stderr) => {
      if (error) {
        reject(error);
        return;
      }
      
      if (stdout) console.log(stdout);
      if (stderr) console.error(stderr);
      resolve();
    });
  });
}

async function validateCollection() {
  const collectionPath = '.postman/NIA-Complete-Collection.json';
  
  if (!fs.existsSync(collectionPath)) {
    throw new Error('Colección no generada correctamente');
  }
  
  try {
    const collection = JSON.parse(fs.readFileSync(collectionPath, 'utf8'));
    
    if (!collection.item || collection.item.length === 0) {
      throw new Error('Colección vacía o mal formada');
    }
    
    const totalEndpoints = collection.item.reduce((total, service) => {
      return total + (service.item ? service.item.length : 0);
    }, 0);
    
    console.log(`📊 Validación OK: ${collection.item.length} servicios, ${totalEndpoints} endpoints`);
    
  } catch (error) {
    throw new Error(`Colección inválida: ${error.message}`);
  }
}

function checkDependencies() {
  const dependencies = ['newman', 'openapi2postmanv2'];
  
  dependencies.forEach(dep => {
    exec(`which ${dep}`, (error) => {
      if (error) {
        console.warn(`⚠️  Dependencia faltante: ${dep}`);
        console.warn(`   Instala con: npm install -g ${dep}`);
      }
    });
  });
}

// Manejar cierre graceful
process.on('SIGINT', () => {
  console.log('\n👋 Cerrando watcher...');
  watcher.close();
  process.exit(0);
});

process.on('SIGTERM', () => {
  watcher.close();
  process.exit(0);
});