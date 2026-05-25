<<<<<<< HEAD
# Proyecto-DBA

Documentacion y desarrollo del proyecto de bases de datos NoSQL con enfoque geoespacial.

## Resumen del proyecto
=======
<div align="center">

# Análisis Geoespacial de Potencial Solar en Territorios PDET

## **Administración de Bases de Datos — Pontificia Universidad Javeriana**

![Logo de la Pontificia Universidad Javeriana](https://upload.wikimedia.org/wikipedia/commons/6/6c/Javeriana.svg)

**Autores:** Jan Marco Muñoz, Ana Sofia Arboleda, Valentina García, Nicolás Torres  
**Entregado a:** Ing. Andres Oswaldo Calderon  
**Fecha de inicio:** 27 de Abril 2026

<br>
</div>

---

## Acerca del Proyecto

Este proyecto implementa un **análisis** geoespacial reproducible para estimar el potencial de energía solar en territorios PDET (Programas de Desarrollo con Enfoque Territorial) de Colombia.

El objetivo es desarrollar una solución NoSQL escalable que permita:

- Integrar límites administrativos municipales del Marco Geoestadístico Nacional (MGN) del DANE
- Procesar footprints de edificios de múltiples fuentes (Microsoft, Google)
- Cuantificar el área de techos disponibles para instalación de paneles solares
- Generar análisis agregados por municipio para evaluación de viabilidad
>>>>>>> 0e25fbfbf3d3d867c52011a3b50671d109076a47

Este proyecto busca construir una base de datos NoSQL en MongoDB para analizar municipios PDET y, en semanas posteriores, cruzarlos con datasets de edificios.

<<<<<<< HEAD
La idea general es:

1. Disenar el esquema de la base de datos.
2. Cargar los limites municipales oficiales de los territorios PDET.
3. Cargar footprints de edificios de Microsoft y Google.
4. Hacer joins espaciales para contar edificios por municipio y sumar areas.
5. Entregar el informe final con resultados.

## Cronograma

| Semana | Objetivo |
|---|---|
| 1 | Diseno del esquema NoSQL y plan de implementacion |
| 2 | Integracion de limites municipales PDET con fuente oficial DANE/MGN |
| 3 | Carga de footprints de edificios |
| 4 | Joins espaciales y agregaciones |
| 5 | Informe tecnico final |

## Entrega de semana 2

La entrega de la semana 2 consiste en demostrar que el proyecto trabaja solamente con municipios PDET y que esos municipios fueron cargados usando limites oficiales DANE/MGN dentro de MongoDB.

### Lo que revisan

- Data Acquisition & Verification
- Data Integrity & Format
- NoSQL Spatial Integration
- Documentation of Process

### Que significa eso en palabras simples

- **Adquisicion y verificacion de datos:** explicar de donde salieron los archivos y como se verifico que si corresponden a municipios PDET.
- **Integridad y formato:** asegurar que los codigos DANE, nombres y geometrias quedaron consistentes.
- **Integracion espacial NoSQL:** guardar los municipios en MongoDB como GeoJSON y crear el indice espacial `2dsphere`.
- **Documentacion del proceso:** dejar claro que se hizo, con que archivos, con que script y que resultado se obtuvo.

## Estado actual del proyecto

Con lo que hay actualmente en el repositorio, ya esta adelantada la base tecnica de la semana 2:

- Existe un script de ingesta: [load_pdet_municipalities.py](C:\Users\Asus\Desktop\Proyecto-DBA\load_pdet_municipalities.py)
- El script lee el shapefile municipal oficial.
- El script lee la lista de municipios PDET desde un archivo Excel.
- Se construye el codigo `dane_code` a partir del departamento y municipio.
- Se filtran solo los municipios PDET.
- Las geometrias se convierten a formato GeoJSON compatible con MongoDB.
- Se reproyecta a `EPSG:4326`, requerido para indice `2dsphere`.
- Los documentos se cargan en la coleccion `municipalities`.
- Se crea el indice espacial.
- Se imprime una verificacion basica al finalizar.

En resumen: la logica principal de semana 2 ya existe, pero todavia hace falta dejar mejor documentado el proceso y ejecutar la carga con los archivos reales para registrar evidencia.

## Archivos esperados

El script actual espera estos insumos:

- `MunicipiosPDET.xlsx`
- `MGN_2025_COLOMBIA/ADMINISTRATIVO/MGN_ADM_MPIO_GRAFICO.shp`

Nota: el shapefile normalmente viene acompanado por archivos auxiliares como `.dbf`, `.shx`, `.prj` y otros. Todos deben mantenerse juntos en la misma carpeta.

## Stack tecnologico

| Componente | Herramienta | Uso en el proyecto |
|---|---|---|
| Base de datos | MongoDB 7.x | Almacenamiento NoSQL y consultas espaciales |
| Driver Python | PyMongo | Insercion y actualizacion de documentos |
| Procesamiento geoespacial | GeoPandas + Shapely | Lectura del shapefile y conversion a GeoJSON |
| Procesamiento tabular | Pandas | Lectura del Excel con municipios PDET |
| Versionamiento | GitHub | Entrega y seguimiento del proyecto |

## Proceso de semana 2

### 1. Cargar la lista oficial de municipios PDET

El script lee el archivo Excel con los municipios PDET y toma la columna del codigo DANE del municipio. Luego completa con ceros a la izquierda para asegurar que todos queden en formato de 5 digitos.

### 2. Leer el shapefile de municipios

Se abre el shapefile oficial MGN/DANE con GeoPandas. Desde ahi se obtiene:

- geometria del municipio,
- nombre del municipio,
- nombre del departamento,
- codigo del departamento,
- codigo del municipio.

### 3. Calcular area del municipio

El script calcula el area en metros cuadrados usando un CRS metrico (`EPSG:9377`) y luego guarda ese valor como `area_m2`.

### 4. Reproyectar a WGS84

MongoDB utiliza GeoJSON en coordenadas geograficas, por eso la geometria se transforma a `EPSG:4326`.

### 5. Filtrar solo municipios PDET

Se construye el `dane_code` con:

- `dpto_ccdgo` con 2 digitos
- `mpio_ccdgo` con 3 digitos

Despues se conservan unicamente los municipios cuyo `dane_code` este en la lista PDET.

### 6. Construir los documentos

Cada municipio queda almacenado con esta estructura:

```json
{
  "dane_code": "05001",
  "name": "Municipio",
  "department": "Departamento",
  "is_pdet": true,
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": []
  },
  "area_m2": 123456.78,
  "source": "MGN2025",
  "ingested_at": "ISODate"
}
```

### 7. Cargar a MongoDB

La coleccion objetivo es `municipalities` dentro de la base `upme-project`.

El script hace `upsert` por `dane_code`, lo cual evita insertar duplicados si se ejecuta varias veces.

### 8. Crear indice espacial

Se crea el indice:

```javascript
db.municipalities.createIndex({ "geometry": "2dsphere" })
```

Esto deja lista la coleccion para consultas y joins espaciales posteriores.

## Esquema de la coleccion `municipalities`

```json
{
  "_id": "ObjectId",
  "dane_code": "string",
  "name": "string",
  "department": "string",
  "is_pdet": true,
  "geometry": {
    "type": "MultiPolygon",
    "coordinates": [[[[0, 0]]]]
  },
  "area_m2": 123456.78,
  "source": "MGN2025",
  "ingested_at": "ISODate"
}
```

## Como ejecutar

### 1. Levantar MongoDB

```bash
docker run -d --name upme-mongo -p 27017:27017 mongo:7
```

### 2. Instalar dependencias

```bash
pip install pymongo geopandas shapely pandas openpyxl
```

### 3. Ejecutar la ingesta

```bash
python load_pdet_municipalities.py
```

## Evidencia que debe quedar para la entrega

Cuando ejecuten el script con los archivos reales, conviene registrar estos resultados en esta misma seccion:

- Total de municipios leidos desde el shapefile: `pendiente`
- Total de codigos PDET en el Excel: `pendiente`
- Total de municipios PDET encontrados en el shapefile: `pendiente`
- Total de documentos en MongoDB al finalizar: `pendiente`
- Indices creados: `pendiente`
- Documento de muestra insertado: `pendiente`

Tambien sirve guardar una captura de:

- la consola con la ejecucion exitosa,
- la coleccion `municipalities` en MongoDB,
- el indice `2dsphere` creado.

## Validaciones para semana 2

Estas son las validaciones que deben mencionar en la defensa:

### Data Acquisition & Verification

- El shapefile de municipios proviene de la fuente oficial MGN/DANE.
- La lista de municipios PDET proviene del archivo oficial entregado o descargado para el proyecto.
- El filtro se hace por codigo DANE, no manualmente.

### Data Integrity & Format

- El codigo `dane_code` queda con 5 digitos.
- El atributo `is_pdet` queda en `true` para todos los documentos cargados.
- Las geometrias quedan en formato GeoJSON.
- Si la geometria original es `Polygon`, se convierte a `MultiPolygon`.
- El CRS final queda en `EPSG:4326`.
- El area se guarda de forma consistente como `area_m2`.

### NoSQL Spatial Integration

- Los datos quedan cargados en MongoDB.
- La geometria se almacena en el campo `geometry`.
- La coleccion tiene indice `2dsphere`.

### Documentation of Process

- El paso a paso esta descrito en este README.
- El script principal del proceso queda versionado en el repositorio.

## Justificacion de MongoDB

MongoDB es una buena eleccion para este proyecto porque:

- soporta GeoJSON de forma nativa,
- permite crear indices espaciales `2dsphere`,
- facilita futuras consultas con `geoIntersects`,
- y encaja bien con un modelo flexible basado en documentos.

## Trabajo futuro
=======
- **Base de Datos:** MongoDB 7.x (Almacenamiento de datos geoespaciales)
- **Procesamiento:** Python 3.x, GeoPandas, PyMongo (Procesamiento de datos)
- **Infraestructura:** Docker
- **Datos:** Microsoft Building Footprints, Google Open Buildings, DANE MGN

---

## Entregas por Semana

### **Semana 1: Diseño del Esquema NoSQL y Plan de Implementación**
Definición de la arquitectura de datos, configuración de MongoDB y creación del esquema de colecciones con índices geoespaciales.

[Documentación completa](semana_1/README_Semana_1.md)

**Logros principales:**
- Diseño del modelo de datos (municipios, footprints)
- Configuración de índices 2dsphere para operaciones geoespaciales
- Stack tecnológico y plan de implementación

---

### **Semana 2: Carga de Límites Municipales PDET**
Ingesta y transformación de datos de límites administrativos desde los shapefiles de DANE (MGN).

**Objetivos:**
- Extracción y filtrado de municipios PDET
- Conversión de geometrías a GeoJSON (WGS84)
- Validación y carga en colección `municipalities`

---

### **Semana 3: Carga de Footprints de Edificios**
Integración de datos de footprints desde Microsoft Building Footprints y Google Open Buildings.

**Objetivos:**
- Descarga y procesamiento de datasets
- Normalización de geometrías (coordenadas WGS84)
- Carga en colecciones `buildings_microsoft` y `buildings_google`

---

### **Semana 4: Análisis Geoespacial y Agregaciones**
Ejecución de joins espaciales y generación de métricas de conteo de edificios y área de techos por municipio.

**Objetivos:**
- Consultas geoespaciales: edificios dentro de límites municipales
- Agregación de área total por municipio y fuente
- Generación de resultados en colección `analysis_results`

---

### **Semana 5: Informe Técnico Final**
Consolidación de metodología, resultados y recomendaciones para identificar municipios prioritarios.

**Entregables:**
- Reporte técnico con metodología y hallazgos
- Visualizaciones de resultados
- Recomendaciones para proyectos piloto de energía solar

---

## Estructura del Repositorio

```
Proyecto-DBA/
├── README.md                    # Este archivo
├── README_Semana_1.md           # Documentación detallada de Semana 1
├── project.md                   # Enunciado del proyecto y requerimientos
├── Enunciado.pdf                # Especificaciones formales (PDF)
├── load_pdet_municipalities.py  # Script para carga de datos
└── .git/                         # Control de versiones
```

---

## Comenzar

Para reproducir este proyecto en tu entorno local:

```bash
# Clonar el repositorio
git clone <repository-url>
cd Proyecto-DBA

# Instalar dependencias Python
pip install pymongo motor geopandas shapely pandas openpyxl requests

# Iniciar MongoDB con Docker
docker run -d --name upme-mongo \
  -p 27017:27017 \
  -v $(pwd)/data:/data/db \
  mongo:7
```

Para más detalles sobre configuración y diseño del esquema, consulta [README_Semana_1.md](semana_1/README_Semana_1.md).

---

## Notas

Todas las geometrías se almacenan en formato **GeoJSON** con coordenadas **WGS84 (EPSG:4326)**, garantizando compatibilidad con índices geoespaciales de MongoDB.
>>>>>>> 0e25fbfbf3d3d867c52011a3b50671d109076a47

En la semana 3 se integraran los datasets de edificios de Microsoft y Google. En la semana 4 se haran joins espaciales para contar edificios y sumar areas dentro de cada municipio PDET.
