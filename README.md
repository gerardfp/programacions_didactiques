# 📘 Generador Sistemático de Programaciones Didácticas FP

Sistema integral de generación sistemática y automatizada de **Programaciones Didácticas oficiales de Formación Profesional** en formato nativo OpenDocument (`.odt`), editable directamente con LibreOffice Writer y conforme a la **Ley Orgánica 3/2022** y el **Real Decreto 659/2023**.

---

## 🚀 1. Comandos de Generación (CLI)

El generador se ejecuta desde la terminal mediante el script principal [`generador_pd.py`](generador_pd.py). Produce directamente documentos `.odt` listos para su uso docente e inspección educativa.

### Requisitos previos
- **Python 3.10** o superior.
- No requiere dependencias externas obligatorias (utiliza bibliotecas nativas de la biblioteca estándar de Python: `xml.etree.ElementTree`, `zipfile`, `json`, `re`, `argparse`).
- Para abrir, editar o exportar a PDF los archivos generados: **LibreOffice** (v7.x / v24.x o posterior).

---

### Casos de uso principales

#### A. Generar sistemáticamente TODOS los ciclos y módulos
Genera las 30 programaciones didácticas de todos los ciclos formativos configurados (DAM, DAW, SMX):
```bash
python generador_pd.py --all
```

#### B. Generar todas las programaciones de un ciclo específico
Utiliza el parámetro `--ciclo` seguido del código del ciclo (`DAM`, `DAW`, `SMX`):
```bash
python generador_pd.py --ciclo DAM
python generador_pd.py --ciclo DAW
python generador_pd.py --ciclo SMX
```

#### C. Generar un único módulo profesional
Utiliza el parámetro `--modulo` indicando su código oficial de 4 dígitos o parte de su nombre:
```bash
# Por código oficial de módulo
python generador_pd.py --modulo 0489

# Especificando ciclo para resolver módulos comunes (ej. 0483 Sistemas Informáticos)
python generador_pd.py --ciclo DAM --modulo 0483
python generador_pd.py --ciclo DAW --modulo 0483
```

---

### Parámetros y Opciones Avanzadas

| Parámetro | Argumento | Descripción | Valor por defecto |
| :--- | :--- | :--- | :--- |
| `--all` | Ninguno | Genera sistemáticamente todos los módulos de todos los ciclos | — |
| `--ciclo` | `CODIGO` | Filtra por ciclo formativo (ej. `DAM`, `DAW`, `SMX`) | Todos |
| `--modulo` | `CODIGO` | Genera solo el módulo indicado (código o nombre) | — |
| `--curso-escolar` / `--curso-academico` | `"AÑO / AÑO"` | Curso escolar reflejado en portadas y encabezados | `"2026 / 2027"` |
| `--plantilla` / `--template` | `RUTA.fodt` | Ruta a una plantilla ODF base alternativa | `plantilla.fodt` |
| `--output-dir` | `CARPETA` | Carpeta raíz de salida de los documentos | `programaciones` |
| `--output` / `-o` | `ARCHIVO.odt` | Nombre de archivo de salida personalizado (con `--modulo`) | Nomenclatura estándar |

#### Ejemplos de personalización:
```bash
# Cambiar el curso escolar a 2025/2026:
python generador_pd.py --all --curso-escolar "2025 / 2026"

# Usar una plantilla visual alternativa:
python generador_pd.py --all --plantilla plantilla_V2.fodt

# Generar un módulo en un archivo específico de destino:
python generador_pd.py --modulo 0489 --output mi_programacion_pdm.odt
```

---

### Nomenclatura estándar de los archivos generados

Los archivos `.odt` se guardan automáticamente dentro de subcarpetas por ciclo (`programaciones/DAM/`, `programaciones/DAW/`, `programaciones/SMX/`) siguiendo el patrón estandarizado:

$$\mathbf{PD\_\{curso\_escolar\}\_\{ciclo\}\{curso\}\_\{codigo\}\_\{siglas\}.odt}$$

- **Ejemplo**: `PD_26-27_DAM2_0489_PMYDM.odt`
  - `PD`: Programación Didáctica
  - `26-27`: Curso escolar 2026 / 2027
  - `DAM2`: Ciclo DAM, 2º curso
  - `0489`: Código oficial del módulo en el Real Decreto
  - `PMYDM`: Siglas oficiales del módulo (Programación multimedia y dispositivos móviles)

---

## 🧩 2. Procedimiento para Añadir Nuevos Ciclos Formativos

El sistema está diseñado para incorporar nuevos títulos de Formación Profesional de manera modular sin tener que modificar la lógica del motor de generación.

Hay dos vías posibles:

### Opción A (Recomendada): Ingesta Automática del XML Oficial del BOE

1. **Descargar el Real Decreto del título en XML**:
   - Entra en el portal del [Boletín Oficial del Estado (BOE)](https://www.boe.es).
   - Localiza el Real Decreto que establece el título y las enseñanzas mínimas del ciclo (por ejemplo, *Real Decreto 405/2023 de ASIR* o *Ciberseguridad*).
   - Abre la versión XML oficial de la disposición (enlace *«XML»* en la cabecera de la web del BOE).
2. **Guardar el archivo XML**:
   - Guarda el archivo en la carpeta `curriculums_originals/` con el nombre del ciclo en mayúsculas (ej. `curriculums_originals/ASIR.xml`).
3. **Ejecutar el generador**:
   - Al ejecutar `python generador_pd.py --ciclo ASIR` o `python generador_pd.py --all`:
     - El componente `BoeCurriculumXmlParser` detecta automáticamente el nuevo archivo XML.
     - Extrae la normativa, las competencias generales y profesionales, las cualificaciones, las unidades de competencia, los módulos profesionales, todos los Resultados de Aprendizaje (RAs) con sus Criterios de Evaluación (CEs) y las orientaciones pedagógicas del BOE.
     - Crea automáticamente el archivo caché `curriculum_asir.json` y genera los documentos `.odt`.

---

### Opción B: Creación Directa de un archivo JSON (`curriculum_<ciclo>.json`)

Si no se dispone del XML del BOE, puede crearse un archivo `curriculum_<codigo_ciclo>.json` en la raíz del proyecto (ej. `curriculum_asir.json`):

```json
{
  "ciclo": "ASIR",
  "codigo_ciclo": "IFCS02",
  "titulo": "Ciclo Formativo de Grado Superior en Administración de Sistemas Informáticos en Red",
  "familia_profesional": "Informática y Comunicaciones",
  "nivel": "Grado Superior",
  "normativa_referencia": "Real Decreto 1629/2009, de 30 de octubre",
  "competencias_profesionales_personales_sociales": {
    "a": "Administrar sistemas operativos de servidor...",
    "b": "Configurar y administrar redes locales...",
    "c": "Implantar y gestionar bases de datos..."
  },
  "cualificaciones_profesionales": [
    {
      "codigo": "IFC365_3",
      "denominacion": "Administración de sistemas informáticos",
      "unidades_competencia": ["UC0490_3", "UC0491_3"]
    }
  ],
  "unidades_competencia": {
    "UC0490_3": "Gestionar servicios en el sistema informático",
    "UC0491_3": "Administrar sistemas operativos de servidor"
  },
  "modulos": [
    {
      "codigo": "0369",
      "nombre": "Implantación de sistemas operativos",
      "curso_orientativo": "1º",
      "horas": 160,
      "creditos_ects": 8,
      "unidades_competencia": ["UC0491_3"],
      "competencias_titulo": ["a", "b", "c"],
      "orientaciones_pedagogicas": "La formación del módulo contribuye a alcanzar las competencias...",
      "resultados_aprendizaje": [
        {
          "numero": 1,
          "descripcion": "Instala sistemas operativos planificando el proceso...",
          "criterios_evaluacion": [
            {"letra": "a", "descripcion": "Se han identificado los elementos del hardware..."},
            {"letra": "b", "descripcion": "Se ha seleccionado el sistema operativo..."}
          ]
        }
      ]
    }
  ]
}
```

---

## 📖 3. Procedimiento para Añadir o Personalizar Módulos Profesionales

### Paso 1: Definir los Datos Pedagógicos en `pedagogia_modulos.json`

Abre el archivo `pedagogia_modulos.json` y añade una entrada identificada por el código de 4 dígitos del módulo (ej. `"0369"`):

```json
"0369": {
  "unidades": [
    {
      "codigo": "UD 1",
      "nombre": "Arquitectura y Selección de Sistemas Operativos",
      "ras": [1],
      "horas": 30,
      "trimestre": "1er Trimestre",
      "inicio": "Septiembre",
      "fin": "Octubre"
    },
    {
      "codigo": "UD 2",
      "nombre": "Instalación y Configuración del Sistema",
      "ras": [1, 2],
      "horas": 35,
      "trimestre": "1er Trimestre",
      "inicio": "Octubre",
      "fin": "Noviembre"
    }
  ],
  "ra_ponderaciones": {
    "1": 20.0,
    "2": 25.0,
    "3": 25.0,
    "4": 30.0
  },
  "formula_evaluacion": "Módulo = 0.20 · RA_1 + 0.25 · RA_2 + 0.25 · RA_3 + 0.30 · RA_4",
  "instrumentos": {
    "1": [
      {
        "nombre": "Prácticas de laboratorio de instalación y particionado",
        "peso_ra": 60.0
      },
      {
        "nombre": "Prueba escrita objetiva de conceptos arquitectónicos",
        "peso_ra": 40.0
      }
    ]
  },
  "metodologia": "El módulo se desarrolla mediante supuestos prácticos en máquinas virtuales...",
  "recursos_software": [
    "VirtualBox / VMware Workstation",
    "Distribuciones GNU/Linux Ubuntu Server y Rocky Linux",
    "Microsoft Windows Server"
  ],
  "recursos_hardware": [
    "Equipos con soporte de virtualización hardware (VT-x / AMD-V)",
    "Red de laboratorio con switch dedicado"
  ],
  "espacios": "Aula polivalente y laboratorio de informática de redes y sistemas."
}
```

> **Nota**: Si añades un módulo al currículo pero **no** lo defines en `pedagogia_modulos.json`, el generador no fallará: calculará automáticamente una distribución matemática coherente de unidades didácticas, ponderaciones equitativas que sumen exactamente 100.0%, fórmula de evaluación e instrumentos estándar (60% práctico / 40% teórico).

---

### Paso 2: Registrar las Siglas del Módulo para la Nomenclatura de Archivos

En `generador_pd.py`, localiza el diccionario `KNOWN_MODULE_INITIALS` (alrededor de la línea 50) y añade el código de módulo junto a sus siglas oficiales:

```python
KNOWN_MODULE_INITIALS = {
    # ... módulos existentes ...
    "0369": "ISO",      # Implantación de sistemas operativos
    "0370": "PAR",      # Planificación y administración de redes
    "0371": "FH",       # Fundamentos de hardware
    "0372": "GBD",      # Gestión de bases de datos
}
```
*Si un módulo no está en este diccionario, el generador extraerá automáticamente las siglas a partir de las iniciales de su denominación oficial.*

---

## 🎨 4. Personalización de la Plantilla Maestra (`plantilla.fodt`)

La plantilla base está en formato **Flat XML ODF** (`plantilla.fodt`). Puede abrirse y modificarse directamente con **LibreOffice Writer**:

1. **Editar diseño con LibreOffice**:
   - Abre `plantilla.fodt` con LibreOffice Writer.
   - Modifica tipografías, colores corporativos, logotipos, márgenes de página o estilos de celda.
   - Guarda el documento directamente en LibreOffice (*Guardar* o `Ctrl+S`).
2. **Requisitos de tablas para el generador**:
   El motor de clonación ODF identifica las tablas por su nombre (`table:name`). Para asegurar la compatibilidad, **no cambies el nombre de las siguientes tablas**:
   - `CoverMeta`: Ficha técnica de la portada (8 filas predefinidas).
   - `Table_36848684`: Tabla de Unidades de Competencia (2 columnas: UC y Cualificación).
   - `Table_49111049`: Tabla de RAs y Competencias del Título vinculadas.
   - `Tabla1`: Secuenciación temporal de Unidades Didácticas (6 columnas: UP, RAs, Duración, Trimestre, Inicio, Fin).
   - `Tabla_Evaluacion_RA`: Ponderación de los RAs sobre la nota del módulo.
   - `Tabla_Evaluacion_Instrumentos`: Instrumentos de evaluación por cada RA y porcentaje final.
3. **Placeholders admitidos**:
   Puedes insertar libremente placeholders en el texto o celdas de la plantilla:
   - `{{modulo}}`: Denominación oficial completa (código y nombre).
   - `{{codigo_modulo}}`: Código de 4 dígitos.
   - `{{ciclo}}`: Título completo del ciclo y siglas.
   - `{{familia}}`: Familia profesional.
   - `{{curso}}`: Curso (1º o 2º).
   - `{{horas}}`: Horas lectivas totales.
   - `{{ects}}`: Créditos ECTS.
   - `{{normativa_referencia}}`: Real Decreto del título.
   - `{{profesor}}`: Profesorado responsable del departamento.
   - `{{centro}}`: Nombre del centro educativo.
   - `{{curso_academico}}`: Curso escolar (ej. 2026 / 2027).
   - `{{contextualizacion_modulo}}`: Expansión automática por párrafos y viñetas del BOE.
   - `{{metodologia_especifica}}`, `{{recursos_especificos}}`, `{{espacios_especificos}}`, `{{formula_evaluacion}}`.

---

## 📁 5. Estructura del Proyecto

```text
programacions_didactiques/
├── generador_pd.py             # Script principal y orquestador CLI de generación
├── plantilla.fodt              # Plantilla maestra editable en LibreOffice Writer
├── README.md                   # Esta documentación técnica de referencia
├── curriculum_dam.json         # Currículo oficial de DAM (BOE)
├── curriculum_daw.json         # Currículo oficial de DAW (BOE)
├── curriculum_smx.json         # Currículo oficial de SMX (BOE)
├── pedagogia_modulos.json      # Programación pedagógica detallada por módulo
├── curriculums_originals/      # Depósito de archivos XML oficiales descargados del BOE
│   ├── DAM_DAW.xml
│   ├── SMX.xml
│   └── (futuros ciclos: ASIR.xml, etc.)
└── programaciones/             # Directorio de salida de los documentos generados
    ├── DAM/                    # Archivos PD_26-27_DAM*.odt
    ├── DAW/                    # Archivos PD_26-27_DAW*.odt
    └── SMX/                    # Archivos PD_26-27_SMX*.odt
```

---

## ⚖️ Marco Normativo Aplicado

Las programaciones didácticas generadas cumplen con la normativa educativa de Formación Profesional en España:
- **Ley Orgánica 3/2022, de 31 de marzo**, de ordenación e integración de la Formación Profesional.
- **Real Decreto 659/2023, de 18 de julio**, por el que se desarrolla la ordenación del Sistema de Formación Profesional.
- **Real Decreto 500/2024, de 21 de mayo**, de adecuación de créditos ECTS y atribuciones docentes.
- **Principios DUA (Diseño Universal para el Aprendizaje)**: Garantía de accesibilidad, múltiples formas de representación y evaluación formativa continua.
