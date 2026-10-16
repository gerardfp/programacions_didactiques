# Sistema de Traducción Neuronal Local (`tools/`)

Este directorio contiene las herramientas reproducibles basadas en **`uv`** (PEP 723) para traducir localmente los archivos `curriculum_<ciclo>.json` (Español $\to$ Catalán) y `pedagogia_<ciclo>.json` (Catalán $\leftrightarrow$ Español), generando los archivos por idioma `*_cas.json` y `*_val.json`.

---

## 1. Evaluación Técnica de Motores Locales

| Criterio | **Softcatalà NMT (`Softcatala/nmt-models`)** *(Por defecto)* | **`BSC-LT/salamandraTA-7b-instruct`** *(Opcional)* |
| :--- | :--- | :--- |
| **Arquitectura** | Transformer (`OpenNMT-tf` exportado a **CTranslate2** INT8) + `SentencePiece` | LLM Causal de **7.7B parámetros** basado en `Salamandra-7b` (ChatML / GGUF `Q4_K_M`) |
| **Entrenamiento ES $\leftrightarrow$ CA** | **7,6 millones de frases** curadas por Softcatalà (**BLEU 88.8** `spa-cat` / **87.5** `cat-spa`) | Multilingüe (40 idiomas), entrenado en el supercomputador MareNostrum 5 (BSC) |
| **Peso en disco** | **~360 MB** en total (ambas direcciones `spa-cat` y `cat-spa`) | **~4.8 GB** (GGUF `Q4_K_M`) o **~15.5 GB** (`bfloat16`) |
| **Consumo de RAM** | **< 500 MB** | **~6.5 GB RAM** (GGUF) / **~16 GB VRAM** (`bfloat16`) |
| **Tiempo de ejecución en CPU (8 hilos)** | **~15–20 segundos** para traducir los 4 ciclos completos (~3.500 oraciones) | **~3–4 horas** en CPU con GGUF (~5–8 s/oración) |
| **Caso de uso ideal** | Traducción masiva y rápida en local sobre CPU sin GPU dedicada | Estaciones de trabajo con GPU dedicada o traducción guiada por glosario estricto |

---

## 2. Uso Reproducible con `uv`

No es necesario crear entornos virtuales manualmente ni instalar paquetes en el Python del sistema. El script [`tools/translate_json.py`](./translate_json.py) declara sus dependencias mediante el estándar **PEP 723** (`# /// script`) y utiliza `uv` para aprovisionar automáticamente Python 3.12 y las ruedas precompiladas de `ctranslate2`, `sentencepiece` y `huggingface-hub`.

### Ejecución en un solo comando (instala `uv` si no existe y traduce todo):

```bash
./tools/setup_and_translate.sh --all
```

### Ejecución directa con `uv`:

```bash
# Traducir todos los ciclos con el motor por defecto (Softcatalà NMT CTranslate2):
uv run tools/translate_json.py --all

# Traducir únicamente un ciclo concreto (dam, daw, ia, smx):
uv run tools/translate_json.py --ciclo dam

# Usar el modelo BSC-LT/salamandraTA-7b-instruct (GGUF vía llama-cpp-python):
uv run --with llama-cpp-python tools/translate_json.py --engine salamandra --ciclo ia
```

---

## 3. Flujo de Archivos Generados

1. **Entrada base**:
   - `curriculum_<ciclo>.json` (extraído del BOE en español)
   - `pedagogia_<ciclo>.json` (datos pedagógicos del centro)
2. **Salida generada por `tools/translate_json.py`**:
   - `curriculum_<ciclo>_cas.json` y `curriculum_<ciclo>_val.json`
   - `pedagogia_<ciclo>_cas.json` y `pedagogia_<ciclo>_val.json`
3. **Generación de programaciones ODT (`.odt`)**:
   ```bash
   python3 generador_pd.py --all --idioma ambos
   ```
   `generador_pd.py` carga directamente los JSON del idioma correspondiente (`_cas.json` con `plantilla.fodt` para `_CAS.odt`, y `_val.json` con `plantilla_val.fodt` para `_VAL.odt`) sin realizar sustituciones por expresiones regulares en tiempo de ejecución.
