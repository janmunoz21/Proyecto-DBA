<div align="center">

# Análisis Geoespacial de Potencial Solar en Territorios PDET

## Administración de Bases de Datos — Pontificia Universidad Javeriana

![Logo de la Pontificia Universidad Javeriana](https://upload.wikimedia.org/wikipedia/commons/6/6c/Javeriana.svg)

**Autores:** Jan Marco Muñoz, Ana Sofia Arboleda, Valentina García, Nicolás Torres  
**Entregado a:** Ing. Andres Oswaldo Calderon  
**Fecha de inicio:** 27 de Abril 2026

</div>

---

# Acerca del Proyecto

Este proyecto implementa un análisis geoespacial reproducible para estimar el potencial de energía solar en territorios PDET (Programas de Desarrollo con Enfoque Territorial) de Colombia.

El objetivo es desarrollar una solución NoSQL escalable que permita:

- Integrar límites administrativos municipales oficiales del DANE/MGN
- Procesar footprints de edificios de Microsoft y Google
- Cuantificar el área de techos disponible para instalación de paneles solares
- Generar análisis agregados por municipio

---

# Objetivos del Proyecto

1. Diseñar el esquema de la base de datos NoSQL
2. Cargar límites municipales oficiales PDET
3. Integrar footprints de edificios
4. Ejecutar joins espaciales
5. Generar análisis agregados e informe final

---

# Stack Tecnológico

| Componente | Herramienta | Uso |
|---|---|---|
| Base de datos | MongoDB 7.x | Almacenamiento NoSQL geoespacial |
| Procesamiento | Python 3.x | Scripts ETL |
| Driver MongoDB | PyMongo | Inserción y consultas |
| Procesamiento geoespacial | GeoPandas + Shapely | Manejo de geometrías |
| Procesamiento tabular | Pandas | Lectura de Excel |
| Infraestructura | Docker | Contenedores |
| Versionamiento | GitHub | Control de versiones |

---

# Cronograma

| Semana | Objetivo |
|---|---|
| 1 | Diseño del esquema NoSQL |
| 2 | Integración de municipios PDET |
| 3 | Carga de footprints de edificios |
| 4 | Joins espaciales y agregaciones |
| 5 | Informe técnico final |

---

# Semana 2 — Carga de Municipios PDET

La entrega de semana 2 consiste en demostrar que el proyecto trabaja únicamente con municipios PDET usando límites oficiales DANE/MGN cargados en MongoDB.

## Lo que se evalúa

- Data Acquisition & Verification
- Data Integrity & Format
- NoSQL Spatial Integration
- Documentation of Process

---

# Estado Actual

Actualmente el repositorio ya incluye la base técnica de la semana 2:

- Script de ingesta `load_pdet_municipalities.py`
- Lectura del shapefile oficial MGN/DANE
- Lectura de municipios PDET desde Excel
- Construcción de `dane_code`
- Filtrado exclusivo de municipios PDET
- Conversión de geometrías a GeoJSON
- Reproyección a `EPSG:4326`
- Carga en MongoDB
- Creación de índice espacial `2dsphere`

---

# Archivos Esperados

El pipeline utiliza:

- `MunicipiosPDET.xlsx`
- `MGN_2025_COLOMBIA/ADMINISTRATIVO/MGN_ADM_MPIO_GRAFICO.shp`

El shapefile debe conservar también archivos auxiliares:

- `.dbf`
- `.shx`
- `.prj`

---

# Proceso de Ingesta

## 1. Cargar municipios PDET

El script lee el archivo Excel y obtiene los códigos DANE oficiales.

## 2. Leer shapefile oficial

Se carga el shapefile MGN/DANE utilizando GeoPandas.

Campos utilizados:

- geometría
- municipio
- departamento
- código DANE

## 3. Calcular área

Las áreas se calculan en `EPSG:9377` y se almacenan como `area_m2`.

## 4. Reproyectar geometrías

MongoDB utiliza GeoJSON en `EPSG:4326`.

## 5. Filtrar municipios PDET

Se construye:

```python
dane_code = dpto_ccdgo + mpio_ccdgo