# Entrega Semana 2 — Carga de Límites Municipales PDET (MGN/DANE)

## 1. Objetivo de la Semana

Procesar y cargar en MongoDB los límites administrativos de los municipios colombianos con estatus **PDET** (Programas de Desarrollo con Enfoque Territorial), utilizando los shapefiles del Marco Geoestadístico Nacional (MGN) versión 2025 proporcionados por el DANE.

---

## 2. Estructura del Trabajo

### 2.1 Fuentes de Datos

- **Archivo shapefile:** `MGN_2025_COLOMBIA/ADMINISTRATIVO/MGN_ADM_MPIO_GRAFICO.shp`
  - Contiene geometrías (polígonos) de todos los municipios colombianos
  - Proyección: WGS84 (EPSG:4326)
  - Formato: MultiPolygon (donde corresponda)

- **Lista de municipios PDET:** Identificación según código DIVIPOLA (ej. "05001")

### 2.2 Procesos Implementados

#### a) Lectura del Shapefile
- Conversión de geometrías Shapely a formato GeoJSON compatible con MongoDB
- Normalización de coordenadas al estándar [lon, lat] requerido por los índices 2dsphere

#### b) Filtrado de Municipios PDET
- Extracción de solo aquellos municipios con designación PDET en el territorio nacional
- Retención de atributos clave: código DIVIPOLA, nombre del municipio, departamento

#### c) Cálculo de Atributos
- **area_km2:** Área en kilómetros cuadrados (calculada sobre WGS84)
- **is_pdet:** Booleano siempre `true` tras el filtrado
- **ingested_at:** Timestamp ISO de ingesta en la base de datos

#### d) Inserción en MongoDB
- Colección: `municipalities`
- Creación de índice geoespacial 2dsphere para futuras consultas espaciales
- Cantidad de documentos: ~170 municipios PDET

### 2.3 Esquema de Documento

```json
{
  "_id": ObjectId,
  "dane_code": "05001",
  "name": "Medellín",
  "department": "Antioquia",
  "is_pdet": true,
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [[[[-75.123, 6.456], [...]]]]
  },
  "area_km2": 380.64,
  "source": "MGN2025",
  "ingested_at": ISODate("2026-05-11T00:00:00Z")
}
```

---

## 3. Validaciones Realizadas

- ✓ Geometrías válidas en formato GeoJSON (estructura y coordenadas)
- ✓ Proyección correcta (WGS84 / EPSG:4326)
- ✓ Ausencia de valores nulos en atributos clave
- ✓ Índice 2dsphere creado exitosamente
- ✓ ~170 documentos insertados en la colección

---

## 4. Archivos Generados

- `load_pdet_municipalities.py` — Script Python para lectura, transformación e inserción de datos
- Logs de ejecución en consola con conteos y validaciones

---

## 5. Disponibilidad de Documentación Completa

**La documentación técnica completa, resultados detallados y análisis de validación se encuentran en el archivo PDF adjunto.**

El PDF incluye:
- Diagrama de arquitectura de datos
- Descripciones detalladas de cada proceso
- Resultados de validación de geometrías
- Conteos finales de municipios cargados
- Ejemplos de documentos en la base de datos
- Preparación para la Semana 3 (carga de footprints de edificios)

---

## 6. Próximos Pasos

**Semana 3:** Carga de footprints de edificios
- Microsoft Global ML Building Footprints
- Google Open Buildings
- Asignación preliminar a municipios PDET