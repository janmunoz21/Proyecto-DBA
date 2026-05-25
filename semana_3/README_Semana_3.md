# Entrega Semana 3 - Carga de Footprints de Edificios

## 1. Objetivo de la Semana

Integrar en MongoDB las huellas de edificios provenientes de Microsoft Building Footprints y Google Open Buildings, almacenandolas en colecciones geoespaciales separadas y dejandolas preparadas para consultas espaciales y cruces con municipios PDET en la siguiente fase del proyecto.

---

## 2. Estructura del Trabajo

### 2.1 Fuentes de Datos

- **Microsoft Building Footprints**
  - Archivo esperado: `buildings_microsoft.geojson`
  - Formato geoespacial: GeoJSON
  - Uso: carga de footprints de edificios detectados por Microsoft

- **Google Open Buildings**
  - Archivo esperado: `buildings_google.geojson`
  - Formato geoespacial: GeoJSON
  - Uso: carga de footprints de edificios detectados por Google

### 2.2 Procesos Implementados

#### a) Seleccion de fuente desde menu
- El sistema permite elegir desde `main.py` la ingesta de Microsoft o Google
- Cada opcion dispara un flujo independiente de carga

#### b) Verificacion y obtencion del archivo
- Se comprueba si el dataset esta disponible localmente
- Si no existe, el sistema ofrece descargarlo o solicitar una ruta local

#### c) Lectura y transformacion geoespacial
- Los archivos se leen con GeoPandas
- Las geometrias se transforman a formato GeoJSON compatible con MongoDB
- Si el CRS no esta en WGS84, se reproyecta a `EPSG:4326`

#### d) Insercion en MongoDB
- Colecciones objetivo:
  - `buildings_microsoft`
  - `buildings_google`
- Se crea indice geoespacial `2dsphere` sobre el campo `geometry`
- Se agregan campos administrativos como fuente y fecha de ingesta

### 2.3 Esquema de Documento

#### Microsoft

```json
{
  "_id": ObjectId,
  "geometry": {
    "type": "Polygon o MultiPolygon",
    "coordinates": []
  },
  "area_m2": 123.45,
  "dataset_source": "microsoft",
  "ingested_at": ISODate("2026-05-24T00:00:00Z")
}
```

#### Google

```json
{
  "_id": ObjectId,
  "geometry": {
    "type": "Polygon o MultiPolygon",
    "coordinates": []
  },
  "area_m2": 123.45,
  "dataset_source": "google",
  "confidence_score": 0.91,
  "ingested_at": ISODate("2026-05-24T00:00:00Z")
}
```

---

## 3. Procedimientos de Administracion de Base de Datos

- Separacion de datasets por coleccion para facilitar administracion y trazabilidad
- Creacion de indice geoespacial `2dsphere` en el campo `geometry`
- Estandarizacion del CRS a `EPSG:4326` para compatibilidad con MongoDB
- Insercion masiva de documentos para mejorar el rendimiento de escritura
- Registro de `ingested_at` para auditoria basica de carga
- Registro de `dataset_source` para mantener identificable el origen de cada documento

---

## 4. Archivos Generados

- `load_buildings.py` - Script principal para la lectura y carga de footprints
- `main.py` - Menu principal y control de ejecucion
- `download_manager.py` - Gestion de disponibilidad y acceso a datasets
- `semana_3/latex/lab_report.tex` - Documentacion tecnica detallada en LaTeX

---

## 5. Disponibilidad de Documentacion Completa

La documentacion tecnica detallada de esta entrega se encuentra en:

- `semana_3/latex/lab_report.tex`

El documento desarrolla:

- arquitectura de la semana 3
- explicacion del codigo involucrado
- procedimientos administrativos sobre MongoDB
- indexacion geoespacial
- normalizacion de geometria y modelo documental
- secuencia operativa de carga

---

## 6. Proximos Pasos

**Semana 4:** Analisis geoespacial y agregaciones

- Cruce espacial entre footprints y municipios PDET
- Conteo de edificios por municipio
- Suma de area construida por fuente
- Generacion de resultados agregados para analisis territorial
