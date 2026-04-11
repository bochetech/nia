# 🔄 Mantener Postman Actualizado Automáticamente

¿Cansado de regenerar manualmente la colección de Postman cada vez que cambias un endpoint? ¡Aquí tienes varias opciones para automatizar completamente el proceso!

## 🚀 **Opciones disponibles**

### **1. 🤖 Generación automática desde OpenAPI (RECOMENDADO)**
```bash
# Generar una sola vez
make postman-generate

# Generar, probar y validar
make postman-update

# Vigilar cambios automáticamente
make postman-watch
```

**Ventajas:**
- ✅ 100% automatizado desde especificaciones OpenAPI
- ✅ Siempre sincronizado con el código
- ✅ Incluye tests automáticos
- ✅ Variables configuradas automáticamente

### **2. 🔄 GitHub Actions - CI/CD automatizado**
Se ejecuta automáticamente en:
- ✅ Cada push a `main`
- ✅ Pull requests
- ✅ Diariamente a las 2 AM
- ✅ Manualmente desde GitHub

**Configuración:**
1. Agregar secrets en GitHub:
   ```
   POSTMAN_API_KEY=your-postman-api-key
   POSTMAN_WORKSPACE_ID=your-workspace-id
   POSTMAN_COLLECTION_ID=your-collection-id
   ```

2. ¡Listo! Se actualiza solo

### **3. 👀 Watcher de desarrollo**
Para desarrollo local con vigilancia de cambios en tiempo real:

```bash
# Instalar dependencias
npm install -g chokidar-cli newman openapi-to-postman

# Ejecutar watcher
node scripts/postman-watcher.js
```

**Qué hace:**
- 👀 Vigila cambios en archivos Python de servicios
- 🔄 Regenera automáticamente la colección
- ✅ Valida que la colección sea correcta
- ⚡ Debounce para evitar regeneraciones múltiples

### **4. 🔗 Integración en tu IDE**

#### **VS Code Task**
Agrega al `.vscode/tasks.json`:
```json
{
  "label": "Regenerar Postman",
  "type": "shell",
  "command": "make postman-generate",
  "group": "build",
  "presentation": {
    "echo": true,
    "reveal": "always",
    "focus": false,
    "panel": "shared"
  }
}
```

#### **Git Hook (Pre-commit)**
```bash
#!/bin/sh
# .git/hooks/pre-commit
make postman-generate
git add .postman/NIA-Complete-Collection.json
```

## ⚙️ **Comandos Make disponibles**

| Comando | Descripción |
|---------|-------------|
| `make postman-install` | Instala herramientas necesarias |
| `make postman-generate` | Genera colección desde OpenAPI |
| `make postman-test` | Prueba la colección generada |
| `make postman-update` | Genera + prueba + levanta servicios |
| `make postman-watch` | Vigila cambios automáticamente |
| `make postman-clean` | Limpia archivos temporales |

## 🔧 **Configuración personalizada**

### **Variables de entorno**
```bash
# URL base de los servicios
export BASE_URL="http://localhost"

# Ejecutar tests después de generar
export RUN_TESTS="true"

# Timeout para tests
export TEST_TIMEOUT="30000"
```

### **Personalizar servicios**
Edita `scripts/merge-postman-collections.js`:
```javascript
const serviceConfig = {
  'mi-servicio': { 
    port: '8010', 
    icon: '🎨', 
    description: 'Mi servicio personalizado' 
  }
};
```

## 🎯 **Flujo de trabajo recomendado**

### **Para desarrollo diario:**
```bash
# Método 1: Automático
make postman-watch  # Deja ejecutándose en background

# Método 2: Manual cuando cambies endpoints
make postman-update
```

### **Para CI/CD:**
1. Configura GitHub Actions (ya incluido)
2. Los PRs automáticamente actualizan Postman
3. La colección se sube al workspace de Postman automáticamente

### **Para releases:**
```bash
# Generar colección final
make postman-generate

# Ejecutar tests completos
make postman-test

# Subir a repositorio
git add .postman/
git commit -m "📮 Update Postman collection for v1.2.0"
git push
```

## 🛠 **Personalización avanzada**

### **Agregar tests personalizados**
Edita el script global en `merge-postman-collections.js`:
```javascript
"// Tests personalizados para mi API",
"pm.test('Response has correlation ID', function () {",
"    pm.expect(pm.response.headers.get('X-Correlation-ID')).to.exist;",
"});",
```

### **Variables dinámicas**
```javascript
"// Generar datos dinámicos",
"pm.environment.set('timestamp', Date.now());",
"pm.environment.set('random_email', `user${Math.random()}@test.com`);",
```

### **Autenticación automática**
```javascript
"// Auto-login si token expiró",
"if (pm.response.code === 401) {",
"    // Ejecutar login automáticamente",
"    pm.execution.setNextRequest('Login');",
"}"
```

## 📊 **Beneficios de la automatización**

### **Sin automatización:**
- ❌ Regenerar manualmente cada cambio
- ❌ Colecciones desactualizadas
- ❌ Tests manuales
- ❌ Errores por olvidos

### **Con automatización:**
- ✅ Siempre actualizada
- ✅ Tests automáticos
- ✅ Variables configuradas
- ✅ Zero maintenance
- ✅ Integración con CI/CD
- ✅ Notificaciones de cambios

## 🚨 **Troubleshooting**

### **Error: "openapi2postmanv2 not found"**
```bash
npm install -g openapi-to-postman
```

### **Error: "Services not responding"**
```bash
# Verificar que los servicios estén ejecutándose
make up
make logs

# Esperar a que estén ready
sleep 30
```

### **Error: "Collection validation failed"**
```bash
# Limpiar archivos temporales
make postman-clean

# Regenerar desde cero
make postman-generate
```

### **Servicios en puertos diferentes**
Edita las variables en `scripts/generate-postman-collection.sh`:
```bash
declare -A SERVICES=(
    ["mi-servicio"]="8010"
    ["otro-servicio"]="8011"
)
```

## 🎉 **¡Resultado final!**

Con esta configuración tendrás:
- 🔄 **Postman siempre actualizado** automáticamente
- 🧪 **Tests que se ejecutan solos**
- 📊 **Reportes de cobertura** de API
- 🚀 **Zero configuración manual**
- 🔗 **Integración completa** con tu workflow

¡Nunca más tendrás que regenerar manualmente Postman! 🎯