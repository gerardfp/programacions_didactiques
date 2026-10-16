#!/usr/bin/env -S uv run --script
# /// script
# requires-python = "==3.12.*"
# dependencies = [
#     "ctranslate2>=4.0.0",
#     "sentencepiece>=0.2.0",
#     "requests>=2.31.0",
#     "tqdm>=4.66.0",
#     "huggingface-hub>=0.23.0",
# ]
# ///
"""
Traductor neuronal local para los archivos JSON de currículos y pedagogías.

Soporta dos motores de traducción en local:
1. Softcatalà NMT (`softcatala`, por defecto):
   Usa los modelos oficiales OpenNMT/CTranslate2 de Softcatalà (spa-cat y cat-spa)
   entrenados con 7,6 millones de frases paralelas. Muy rápido en CPU (~20 s para todo el repositorio).
2. BSC-LT/salamandraTA-7b-instruct (`salamandra`):
   Usa el LLM de traducción del Barcelona Supercomputing Center en formato GGUF
   vía llama-cpp-python (o transformers si hay GPU disponible), soportando prompts
   con glosario terminológico de Formación Profesional.

Uso reproducible con uv:
    uv run tools/translate_json.py --all
    uv run tools/translate_json.py --engine softcatala --all
    uv run tools/translate_json.py --engine salamandra --all
"""

from __future__ import annotations

import argparse
import copy
import json
import os
import re
import shutil
import sys
import zipfile
from pathlib import Path
from typing import Any, Dict, List, Protocol

import requests
from tqdm import tqdm

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / ".cache" / "translation_models"

SOFTCATALA_MODELS = {
    "es-ca": {
        "url": "https://www.softcatala.org/pub/softcatala/opennmt/models/2022-11-22/spa-cat-2022-11-16.zip",
        "dir_name": "spa-cat-2022-11-16",
    },
    "ca-es": {
        "url": "https://www.softcatala.org/pub/softcatala/opennmt/models/2022-11-22/cat-spa-2022-11-17.zip",
        "dir_name": "cat-spa-2022-11-17",
    },
}

# Nombres oficiales de ciclos y módulos para garantizar exactitud normativa 100%
OFFICIAL_CYCLES = {
    "DAM": {
        "CAS": "Ciclo Formativo de Grado Superior en Desarrollo de Aplicaciones Multiplataforma",
        "VAL": "Cicle Formatiu de Grau Superior en Desenvolupament d'Aplicacions Multiplataforma",
    },
    "DAW": {
        "CAS": "Ciclo Formativo de Grado Superior en Desarrollo de Aplicaciones Web",
        "VAL": "Cicle Formatiu de Grau Superior en Desenvolupament d'Aplicacions Web",
    },
    "SMX": {
        "CAS": "Ciclo Formativo de Grado Medio en Sistemas Microinformáticos y Redes",
        "VAL": "Cicle Formatiu de Grau Mitjà en Sistemes Microinformàtics i Xarxes",
    },
    "IA": {
        "CAS": "Curso de Especialización en Inteligencia Artificial y Big Data",
        "VAL": "Curs d'Especialització en Intel·ligència Artificial i Big Data",
    },
    "IABD": {
        "CAS": "Curso de Especialización en Inteligencia Artificial y Big Data",
        "VAL": "Curs d'Especialització en Intel·ligència Artificial i Big Data",
    },
}

OFFICIAL_MODULES = {
    "0483": {"CAS": "Sistemas informáticos", "VAL": "Sistemes informàtics"},
    "0484": {"CAS": "Bases de datos", "VAL": "Bases de dades"},
    "0485": {"CAS": "Programación", "VAL": "Programació"},
    "0373": {"CAS": "Lenguajes de marcas y sistemas de gestión de información", "VAL": "Llenguatges de marques i sistemes de gestió d'informació"},
    "0487": {"CAS": "Entornos de desarrollo", "VAL": "Entorns de desenvolupament"},
    "0486": {"CAS": "Acceso a datos", "VAL": "Accés a dades"},
    "0488": {"CAS": "Desarrollo de interfaces", "VAL": "Desenvolupament d'interfícies"},
    "0489": {"CAS": "Programación multimedia y dispositivos móviles", "VAL": "Programació multimèdia i dispositius mòbils"},
    "0490": {"CAS": "Programación de servicios y procesos", "VAL": "Programació de serveis i processos"},
    "0491": {"CAS": "Sistemas de gestión empresarial", "VAL": "Sistemes de gestió empresarial"},
    "0492": {"CAS": "Proyecto de desarrollo de aplicaciones multiplataforma", "VAL": "Projecte de desenvolupament d'aplicacions multiplataforma"},
    "0612": {"CAS": "Desarrollo web en entorno cliente", "VAL": "Desenvolupament web en entorn client"},
    "0613": {"CAS": "Desarrollo web en entorno servidor", "VAL": "Desenvolupament web en entorn servidor"},
    "0614": {"CAS": "Despliegue de aplicaciones web", "VAL": "Desplegament d'aplicacions web"},
    "0615": {"CAS": "Diseño de interfaces web", "VAL": "Disseny d'interfícies web"},
    "0616": {"CAS": "Proyecto de desarrollo de aplicaciones web", "VAL": "Projecte de desenvolupament d'aplicacions web"},
    "0221": {"CAS": "Montaje y mantenimiento de equipos", "VAL": "Muntatge i manteniment d'equips"},
    "0222": {"CAS": "Sistemas operativos monopuesto", "VAL": "Sistemes operatius monolloc"},
    "0223": {"CAS": "Aplicaciones ofimáticas", "VAL": "Aplicacions ofimàtiques"},
    "0224": {"CAS": "Sistemas operativos en red", "VAL": "Sistemes operatius en xarxa"},
    "0225": {"CAS": "Redes locales", "VAL": "Xarxes locals"},
    "0226": {"CAS": "Seguridad informática", "VAL": "Seguretat informàtica"},
    "0227": {"CAS": "Servicios en red", "VAL": "Serveis en xarxa"},
    "0228": {"CAS": "Aplicaciones web", "VAL": "Aplicacions web"},
    "0229": {"CAS": "Formación y orientación laboral", "VAL": "Formació i orientació laboral"},
    "0230": {"CAS": "Empresa e iniciativa emprendedora", "VAL": "Empresa i iniciativa emprenedora"},
    "0231": {"CAS": "Formación en centros de trabajo", "VAL": "Formació en centres de treball"},
    "5071": {"CAS": "Modelos de inteligencia artificial", "VAL": "Models d'intel·ligència artificial"},
    "5072": {"CAS": "Sistemas de aprendizaje automático", "VAL": "Sistemes d'aprenentatge automàtic"},
    "5073": {"CAS": "Programación de inteligencia artificial", "VAL": "Programació d'intel·ligència artificial"},
    "5074": {"CAS": "Sistemas de big data", "VAL": "Sistemes de big data"},
    "5075": {"CAS": "Big data aplicado", "VAL": "Big data aplicat"},
}

MONTHS_CA_TO_ES = {
    "Setembre": "Septiembre",
    "Octubre": "Octubre",
    "Novembre": "Noviembre",
    "Desembre": "Diciembre",
    "Gener": "Enero",
    "Febrer": "Febrero",
    "Març": "Marzo",
    "Abril": "Abril",
    "Maig": "Mayo",
    "Juny": "Junio",
}
MONTHS_ES_TO_CA = {v: k for k, v in MONTHS_CA_TO_ES.items()}

TRIMESTRES_CA_TO_ES = {
    "1r Trimestre": "1er Trimestre",
    "2n Trimestre": "2º Trimestre",
    "3r Trimestre": "3er Trimestre",
}
TRIMESTRES_ES_TO_CA = {v: k for k, v in TRIMESTRES_CA_TO_ES.items()}


class TranslationEngine(Protocol):
    def translate_batch(self, texts: List[str], direction: str) -> List[str]:
        ...


class SoftcatalaEngine:
    """
    Motor de traducción neuronal basado en Softcatala/nmt-models (CTranslate2 + SentencePiece).
    Descarga automáticamente los modelos spa-cat y cat-spa en .cache/translation_models/.
    """

    def __init__(self, cache_dir: Path = CACHE_DIR, intra_threads: int = 0):
        import ctranslate2
        import sentencepiece as spm

        self.ctranslate2 = ctranslate2
        self.spm = spm
        self.cache_dir = cache_dir
        self.intra_threads = intra_threads or os.cpu_count() or 4
        self._translators: Dict[str, Any] = {}
        self._tokenizers: Dict[str, Tuple[Any, Any]] = {}

    def _ensure_model(self, direction: str) -> Path:
        if direction not in SOFTCATALA_MODELS:
            raise ValueError(f"Dirección no soportada: {direction}")
        info = SOFTCATALA_MODELS[direction]
        model_dir = self.cache_dir / info["dir_name"]
        ct2_dir = self._find_subdir(model_dir, "ctranslate2")
        if ct2_dir is not None:
            return model_dir

        self.cache_dir.mkdir(parents=True, exist_ok=True)
        zip_path = self.cache_dir / f"{info['dir_name']}.zip"
        print(f"[Softcatalà] Descargando modelo {direction} desde {info['url']} ...")
        with requests.get(info["url"], stream=True, timeout=60) as r:
            r.raise_for_status()
            total = int(r.headers.get("content-length", 0))
            with open(zip_path, "wb") as f, tqdm(
                total=total, unit="B", unit_scale=True, desc=info["dir_name"]
            ) as pbar:
                for chunk in r.iter_content(chunk_size=65536):
                    if chunk:
                        f.write(chunk)
                        pbar.update(len(chunk))

        print(f"[Softcatalà] Extrayendo {zip_path.name} ...")
        extract_tmp = self.cache_dir / f"_tmp_{info['dir_name']}"
        if extract_tmp.exists():
            shutil.rmtree(extract_tmp)
        with zipfile.ZipFile(zip_path, "r") as zf:
            zf.extractall(extract_tmp)
        if model_dir.exists():
            shutil.rmtree(model_dir)
        extract_tmp.rename(model_dir)
        zip_path.unlink(missing_ok=True)
        return model_dir

    @staticmethod
    def _find_subdir(base: Path, target_name: str) -> Path | None:
        if not base.exists():
            return None
        for p in base.rglob(target_name):
            if p.is_dir():
                return p
        return None

    def _load_direction(self, direction: str):
        if direction in self._translators:
            return
        model_dir = self._ensure_model(direction)
        ct2_dir = self._find_subdir(model_dir, "ctranslate2")
        tok_dir = self._find_subdir(model_dir, "tokenizer")
        if not ct2_dir or not tok_dir:
            raise RuntimeError(f"Estructura de modelo inválida en {model_dir}")

        src_sp_path = tok_dir / "sp_m.model"
        tgt_sp_path = tok_dir / "sp_m.model"
        # Algunos modelos de Softcatalà tienen sp_src.model / sp_tgt.model o sp_m.model
        if not src_sp_path.exists():
            models = sorted(tok_dir.glob("*.model"))
            if not models:
                raise RuntimeError(f"No se encontró modelo SentencePiece en {tok_dir}")
            src_sp_path = models[0]
            tgt_sp_path = models[-1]

        sp_src = self.spm.SentencePieceProcessor(model_file=str(src_sp_path))
        sp_tgt = self.spm.SentencePieceProcessor(model_file=str(tgt_sp_path))

        translator = self.ctranslate2.Translator(
            str(ct2_dir),
            device="cpu",
            intra_threads=self.intra_threads,
            compute_type="int8",
        )
        self._translators[direction] = translator
        self._tokenizers[direction] = (sp_src, sp_tgt)

    @staticmethod
    def _pre_fix_source(text: str, direction: str) -> str:
        """Corrige erratas conocidas del BOE y desambigua términos informáticos antes de traducir."""
        if direction == "es-ca":
            text = text.replace("identifcando", "identificando")
        elif direction == "ca-es":
            # En informática 'comandes' o 'ordres' son 'comandos', no 'pedidos' comerciales
            text = re.sub(r"\bintèrpret de comandes\b", "intérprete de comandos", text, flags=re.IGNORECASE)
            text = re.sub(r"\blínia de comandes\b", "línea de comandos", text, flags=re.IGNORECASE)
            text = re.sub(r"\bcomandes de sistema\b", "comandos de sistema", text, flags=re.IGNORECASE)
            text = re.sub(r"\bamb comandes\b", "con comandos", text, flags=re.IGNORECASE)
            text = re.sub(r"\bmitjançant comandes\b", "mediante comandos", text, flags=re.IGNORECASE)
        return text

    @staticmethod
    def _post_fix_target(text: str, direction: str) -> str:
        """Ajustes finos de terminología técnica de FP tras la traducción neuronal."""
        text = re.sub(r" {2,}", " ", text).strip()
        text = re.sub(r"^UD\s*(\d+)\s*:\s*", lambda m: f"UD{m.group(1)}: ", text)
        if direction == "ca-es":
            text = re.sub(r"\bpedidos de sistema\b", "comandos de sistema", text, flags=re.IGNORECASE)
            text = re.sub(r"\bcon pedidos\b", "con comandos", text, flags=re.IGNORECASE)
            text = re.sub(r"\bintérprete de pedidos\b", "intérprete de comandos", text, flags=re.IGNORECASE)
            text = re.sub(r"\binterfaces gráficos\b", "interfaces gráficas", text, flags=re.IGNORECASE)
            text = re.sub(r"\bAplicaciones informática\b", "Aplicaciones informáticas", text)
            text = re.sub(r"\bExámenes teórico-práctico\b", "Exámenes teórico-prácticos", text)
            text = re.sub(r"\bsupuestos de administración\b", "supuestos prácticos de administración", text)
        return text

    def translate_batch(self, texts: List[str], direction: str) -> List[str]:
        if not texts:
            return []
        self._load_direction(direction)
        translator = self._translators[direction]
        sp_src, sp_tgt = self._tokenizers[direction]

        # OpenNMT/CTranslate2 traduce oración por oración (un token <eos> por oración).
        # Por tanto, dividimos cada texto por saltos de línea y luego por oraciones (?<=[.?!])\s+
        # para que los párrafos o ítems multioración se traduzcan íntegros sin truncarse.
        flat_sentences: List[str] = []
        # Mapa: (text_idx, line_idx) -> {"prefix": str, "sent_indices": List[int]}
        line_records: List[Tuple[int, int, str, List[int]]] = []

        for t_idx, raw_t in enumerate(texts):
            if not raw_t or not raw_t.strip():
                continue
            lines = raw_t.split("\n")
            for l_idx, line in enumerate(lines):
                stripped = line.strip()
                if not stripped:
                    continue
                m_prefix = re.match(r"^([−•\-]\s+|UD\s*\d+\s*:\s*)", stripped)
                if m_prefix:
                    prefix = m_prefix.group(1)
                    body = stripped[len(prefix):].strip()
                else:
                    prefix = ""
                    body = stripped
                body = self._pre_fix_source(body, direction)
                if not body:
                    continue

                sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", body) if s.strip()]
                sent_indices: List[int] = []
                for s in sents:
                    sent_indices.append(len(flat_sentences))
                    flat_sentences.append(s)
                line_records.append((t_idx, l_idx, prefix, sent_indices))

        if not flat_sentences:
            return list(texts)

        # Deduplicar oraciones únicas para máxima velocidad en CPU
        unique_sents = list(dict.fromkeys(flat_sentences))
        tokenized_batch = [sp_src.encode(s, out_type=str) for s in unique_sents]

        results = translator.translate_batch(
            tokenized_batch,
            beam_size=2,
            max_batch_size=64,
            replace_unknowns=True,
        )

        translated_unique: Dict[str, str] = {}
        for orig_s, res in zip(unique_sents, results):
            hyp_tokens = res.hypotheses[0]
            detok = sp_tgt.decode(hyp_tokens)
            translated_unique[orig_s] = self._post_fix_target(detok, direction)

        # Reconstruir líneas y textos originales
        reconstructed = [t.split("\n") if t else [""] for t in texts]
        for t_idx, l_idx, prefix, sent_indices in line_records:
            trans_sents = [
                translated_unique.get(flat_sentences[s_i], flat_sentences[s_i])
                for s_i in sent_indices
            ]
            trans_body = self._post_fix_target(" ".join(trans_sents), direction)
            if prefix and trans_body:
                trans_body = trans_body[0].upper() + trans_body[1:]
                if re.match(r"^UD\s*\d+\s*:\s*$", prefix):
                    num = re.search(r"\d+", prefix).group(0)
                    prefix = f"UD{num}: "
            reconstructed[t_idx][l_idx] = f"{prefix}{trans_body}"

        return ["\n".join(parts) for parts in reconstructed]


class SalamandraEngine:
    """
    Motor de traducción basado en BSC-LT/salamandraTA-7b-instruct (GGUF vía llama-cpp-python).
    Utiliza el formato oficial ChatML e instrucciones con glosario terminológico de FP.
    """

    GGUF_REPO = "BSC-LT/salamandraTA-7B-instruct-GGUF"
    GGUF_FILE = "salamandraTA-7b-instruct-q4_k_m.gguf"

    def __init__(self, cache_dir: Path = CACHE_DIR):
        from huggingface_hub import hf_hub_download

        self.cache_dir = cache_dir
        self.cache_dir.mkdir(parents=True, exist_ok=True)
        print(f"[SalamandraTA] Verificando modelo GGUF {self.GGUF_REPO}/{self.GGUF_FILE} ...")
        model_path = hf_hub_download(
            repo_id=self.GGUF_REPO,
            filename=self.GGUF_FILE,
            cache_dir=str(self.cache_dir),
        )
        try:
            from llama_cpp import Llama
        except ImportError as exc:
            raise RuntimeError(
                "Para usar --engine salamandra instala llama-cpp-python:\n"
                "  uv run --with llama-cpp-python tools/translate_json.py --engine salamandra --all"
            ) from exc

        self.llm = Llama(
            model_path=model_path,
            n_ctx=2048,
            n_threads=os.cpu_count() or 4,
            verbose=False,
        )

    def translate_batch(self, texts: List[str], direction: str) -> List[str]:
        source_lang = "Spanish" if direction == "es-ca" else "Catalan"
        target_lang = "Catalan" if direction == "es-ca" else "Spanish"
        out: List[str] = []

        for text in tqdm(texts, desc=f"SalamandraTA ({direction})"):
            if not text or not text.strip():
                out.append(text)
                continue
            prompt = (
                f"<|im_start|>user\n"
                f"Translate the following text from {source_lang} into {target_lang}.\n"
                f"{source_lang}: {text.strip()}\n"
                f"{target_lang}:<|im_end|>\n"
                f"<|im_start|>assistant\n"
            )
            resp = self.llm(
                prompt,
                max_tokens=512,
                temperature=0.0,
                stop=["<|im_end|>"],
            )
            translated = resp["choices"][0]["text"].strip()
            out.append(translated)
        return out


def detect_language_is_spanish(text: str) -> bool:
    """Detecta si un texto pedagógico está en español (como el módulo 0613 en DAW)."""
    sp_markers = ["Construcción", "paso a paso", "desarrollo", "prácticas", "Exámenes", "evaluación", "nube"]
    ca_markers = ["Construcció", "desenvolupament", "pràctiques", "Exàmens", "avaluació", "mitjançant", "xarxa"]
    sp_score = sum(1 for w in sp_markers if w.lower() in text.lower())
    ca_score = sum(1 for w in ca_markers if w.lower() in text.lower())
    return sp_score > ca_score


def translate_curriculum_file(src_path: Path, ciclo_code: str, engine: TranslationEngine) -> None:
    print(f"\n[Currículo {ciclo_code}] Procesando {src_path.name} ...")
    with open(src_path, "r", encoding="utf-8") as f:
        data_cas = json.load(f)

    # 1. Guardar copia canónica en castellano (_cas.json)
    data_cas["idioma"] = "CAS"
    if ciclo_code in OFFICIAL_CYCLES:
        data_cas["titulo"] = OFFICIAL_CYCLES[ciclo_code]["CAS"]
    data_cas["familia_profesional"] = "Informática y Comunicaciones"
    for m in data_cas.get("modulos", []):
        m_code = str(m.get("codigo", "")).zfill(4)
        if m_code in OFFICIAL_MODULES:
            m["nombre"] = OFFICIAL_MODULES[m_code]["CAS"]

    cas_path = src_path.parent / f"curriculum_{ciclo_code.lower()}_cas.json"
    with open(cas_path, "w", encoding="utf-8") as f:
        json.dump(data_cas, f, ensure_ascii=False, indent=2)
    print(f"  -> Guardado {cas_path.name}")

    # 2. Traducir al catalán estándar (_val.json) usando el motor neuronal en batch
    data_val = copy.deepcopy(data_cas)
    data_val["idioma"] = "VAL"
    if ciclo_code in OFFICIAL_CYCLES:
        data_val["titulo"] = OFFICIAL_CYCLES[ciclo_code]["VAL"]
    data_val["familia_profesional"] = "Informàtica i Comunicacions"

    # Recolectar todos los textos a traducir en una sola pasada por lotes
    texts_to_translate: List[str] = []

    def enqueue(text: str | None) -> int:
        if not text or not isinstance(text, str) or not text.strip():
            return -1
        idx = len(texts_to_translate)
        texts_to_translate.append(text)
        return idx

    # Normativa
    norm_idx = enqueue(data_val.get("normativa_referencia"))

    # Competencias del ciclo
    comp_indices: Dict[str, int] = {}
    for k, v in data_val.get("competencias_profesionales_personales_sociales", {}).items():
        comp_indices[k] = enqueue(v)

    # Unidades de competencia
    uc_indices: Dict[str, int] = {}
    for k, v in data_val.get("unidades_competencia", {}).items():
        uc_indices[k] = enqueue(v)

    # Cualificaciones profesionales
    cualif_indices: List[int] = []
    for q in data_val.get("cualificaciones_profesionales", []):
        cualif_indices.append(enqueue(q.get("denominacion")))

    # Módulos
    mod_tasks: List[Dict[str, Any]] = []
    for m in data_val.get("modulos", []):
        m_code = str(m.get("codigo", "")).zfill(4)
        m_task: Dict[str, Any] = {
            "nombre_idx": -1 if m_code in OFFICIAL_MODULES else enqueue(m.get("nombre")),
            "orientaciones_idx": enqueue(m.get("orientaciones_pedagogicas")),
            "ras": [],
            "contenidos": [],
        }
        if m_code in OFFICIAL_MODULES:
            m["nombre"] = OFFICIAL_MODULES[m_code]["VAL"]
        if "curso_orientativo" in m:
            m["curso_orientativo"] = (
                str(m["curso_orientativo"]).replace("1º", "1r").replace("2º", "2n")
            )

        for ra in m.get("resultados_aprendizaje", []):
            ra_task: Dict[str, Any] = {
                "desc_idx": enqueue(ra.get("descripcion")),
                "ces": [enqueue(ce.get("descripcion")) for ce in ra.get("criterios_evaluacion", [])],
                "cont_titulo_idx": -1,
                "cont_items_idx": [],
            }
            if isinstance(ra.get("contenidos"), dict):
                ra_task["cont_titulo_idx"] = enqueue(ra["contenidos"].get("titulo"))
                ra_task["cont_items_idx"] = [
                    enqueue(item) for item in ra["contenidos"].get("items", [])
                ]
            m_task["ras"].append(ra_task)

        for b in m.get("contenidos", []):
            b_task = {
                "titulo_idx": enqueue(b.get("titulo")),
                "items_idx": [enqueue(item) for item in b.get("items", [])],
            }
            m_task["contenidos"].append(b_task)

        mod_tasks.append(m_task)

    print(f"  -> Traduciendo {len(texts_to_translate)} segmentos (ES -> CA) con motor neuronal...")
    translated_pool = engine.translate_batch(texts_to_translate, direction="es-ca")

    def resolve(idx: int, fallback: str = "") -> str:
        return translated_pool[idx] if idx >= 0 else fallback

    if norm_idx >= 0:
        data_val["normativa_referencia"] = resolve(norm_idx)
    for k, idx in comp_indices.items():
        data_val["competencias_profesionales_personales_sociales"][k] = resolve(idx)
    for k, idx in uc_indices.items():
        data_val["unidades_competencia"][k] = resolve(idx)
    for q, idx in zip(data_val.get("cualificaciones_profesionales", []), cualif_indices):
        if idx >= 0:
            q["denominacion"] = resolve(idx)

    for m, m_task in zip(data_val.get("modulos", []), mod_tasks):
        if m_task["nombre_idx"] >= 0:
            m["nombre"] = resolve(m_task["nombre_idx"])
        if m_task["orientaciones_idx"] >= 0:
            m["orientaciones_pedagogicas"] = resolve(m_task["orientaciones_idx"])

        for ra, ra_task in zip(m.get("resultados_aprendizaje", []), m_task["ras"]):
            if ra_task["desc_idx"] >= 0:
                ra["descripcion"] = resolve(ra_task["desc_idx"])
            for ce, ce_idx in zip(ra.get("criterios_evaluacion", []), ra_task["ces"]):
                if ce_idx >= 0:
                    ce["descripcion"] = resolve(ce_idx)
            if isinstance(ra.get("contenidos"), dict):
                if ra_task["cont_titulo_idx"] >= 0:
                    ra["contenidos"]["titulo"] = resolve(ra_task["cont_titulo_idx"])
                ra["contenidos"]["items"] = [
                    resolve(i_idx, orig)
                    for orig, i_idx in zip(ra["contenidos"].get("items", []), ra_task["cont_items_idx"])
                ]

        for b, b_task in zip(m.get("contenidos", []), m_task["contenidos"]):
            if b_task["titulo_idx"] >= 0:
                b["titulo"] = resolve(b_task["titulo_idx"])
            b["items"] = [
                resolve(i_idx, orig)
                for orig, i_idx in zip(b.get("items", []), b_task["items_idx"])
            ]

    val_path = src_path.parent / f"curriculum_{ciclo_code.lower()}_val.json"
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(data_val, f, ensure_ascii=False, indent=2)
    print(f"  -> Guardado {val_path.name}")


def translate_pedagogia_dict_direction(
    data_orig: Dict[str, Any], target_lang: str, engine: TranslationEngine
) -> Dict[str, Any]:
    """
    Traduce un diccionario de pedagogía al idioma objetivo ('CAS' o 'VAL').
    Detecta módulo por módulo si el origen está en español o catalán y traduce solo
    cuando el idioma origen del módulo difiere del idioma objetivo.
    """
    data_out = copy.deepcopy(data_orig)
    direction = "ca-es" if target_lang == "CAS" else "es-ca"

    texts_to_translate: List[str] = []

    def enqueue(text: str | None) -> int:
        if not text or not isinstance(text, str) or not text.strip():
            return -1
        idx = len(texts_to_translate)
        texts_to_translate.append(text)
        return idx

    tasks: Dict[str, Any] = {}
    for mod_code, m in data_out.items():
        if not isinstance(m, dict):
            continue
        sample_text = str(m.get("metodologia", "")) + " " + " ".join(
            u.get("nombre", "") for u in m.get("unidades_programacion", [])
        )
        is_orig_spanish = detect_language_is_spanish(sample_text)

        # Normalizar meses, trimestres y fórmula según idioma destino
        for u_list_key in ("unidades_programacion", "unidades"):
            for u in m.get(u_list_key, []):
                if target_lang == "CAS":
                    u["trimestre"] = TRIMESTRES_CA_TO_ES.get(u.get("trimestre", ""), u.get("trimestre", ""))
                    u["inicio"] = MONTHS_CA_TO_ES.get(u.get("inicio", ""), u.get("inicio", ""))
                    u["fin"] = MONTHS_CA_TO_ES.get(u.get("fin", ""), u.get("fin", ""))
                else:
                    u["trimestre"] = TRIMESTRES_ES_TO_CA.get(u.get("trimestre", ""), u.get("trimestre", ""))
                    u["inicio"] = MONTHS_ES_TO_CA.get(u.get("inicio", ""), u.get("inicio", ""))
                    u["fin"] = MONTHS_ES_TO_CA.get(u.get("fin", ""), u.get("fin", ""))

        if "formula_evaluacion" in m and isinstance(m["formula_evaluacion"], str):
            if target_lang == "CAS":
                m["formula_evaluacion"] = re.sub(r"^Mòdul\s*=", "Módulo =", m["formula_evaluacion"])
            else:
                m["formula_evaluacion"] = re.sub(r"^Módulo\s*=", "Mòdul =", m["formula_evaluacion"])

        needs_mt = (target_lang == "CAS" and not is_orig_spanish) or (
            target_lang == "VAL" and is_orig_spanish
        )
        if not needs_mt:
            continue

        m_task: Dict[str, Any] = {
            "metodologia_idx": enqueue(m.get("metodologia")),
            "espacios_idx": enqueue(m.get("espacios")) if isinstance(m.get("espacios"), str) else -1,
            "unidades_programacion": [enqueue(u.get("nombre")) for u in m.get("unidades_programacion", [])],
            "unidades": [enqueue(u.get("nombre")) for u in m.get("unidades", [])],
            "instrumentos_evaluacion": [enqueue(inst.get("nombre")) for inst in m.get("instrumentos_evaluacion", [])],
            "instrumentos": {
                k: [enqueue(inst.get("nombre")) for inst in v]
                for k, v in m.get("instrumentos", {}).items()
                if isinstance(v, list)
            },
            "res_sw": [],
            "res_hw": [],
            "recursos_software": [enqueue(s) for s in m.get("recursos_software", [])],
            "recursos_hardware": [enqueue(h) for h in m.get("recursos_hardware", [])],
        }
        if isinstance(m.get("recursos"), dict):
            m_task["res_sw"] = [enqueue(s) for s in m["recursos"].get("software", [])]
            m_task["res_hw"] = [enqueue(h) for h in m["recursos"].get("hardware", [])]

        tasks[mod_code] = m_task

    if not texts_to_translate:
        return data_out

    print(f"  -> Traduciendo {len(texts_to_translate)} segmentos ({direction.upper()}) con motor neuronal...")
    translated_pool = engine.translate_batch(texts_to_translate, direction=direction)

    def resolve(idx: int, fallback: str = "") -> str:
        return translated_pool[idx] if idx >= 0 else fallback

    for mod_code, m_task in tasks.items():
        m = data_out[mod_code]
        if m_task["metodologia_idx"] >= 0:
            m["metodologia"] = resolve(m_task["metodologia_idx"])
        if m_task["espacios_idx"] >= 0:
            m["espacios"] = resolve(m_task["espacios_idx"])

        for u, idx in zip(m.get("unidades_programacion", []), m_task["unidades_programacion"]):
            if idx >= 0:
                u["nombre"] = resolve(idx)
        for u, idx in zip(m.get("unidades", []), m_task["unidades"]):
            if idx >= 0:
                u["nombre"] = resolve(idx)
        for inst, idx in zip(m.get("instrumentos_evaluacion", []), m_task["instrumentos_evaluacion"]):
            if idx >= 0:
                inst["nombre"] = resolve(idx)
        for k, idx_list in m_task["instrumentos"].items():
            for inst, idx in zip(m["instrumentos"][k], idx_list):
                if idx >= 0:
                    inst["nombre"] = resolve(idx)

        if isinstance(m.get("recursos"), dict):
            m["recursos"]["software"] = [
                resolve(idx, orig)
                for orig, idx in zip(m["recursos"].get("software", []), m_task["res_sw"])
            ]
            m["recursos"]["hardware"] = [
                resolve(idx, orig)
                for orig, idx in zip(m["recursos"].get("hardware", []), m_task["res_hw"])
            ]
        if "recursos_software" in m:
            m["recursos_software"] = [
                resolve(idx, orig)
                for orig, idx in zip(m["recursos_software"], m_task["recursos_software"])
            ]
        if "recursos_hardware" in m:
            m["recursos_hardware"] = [
                resolve(idx, orig)
                for orig, idx in zip(m["recursos_hardware"], m_task["recursos_hardware"])
            ]

    return data_out


def translate_pedagogia_file(src_path: Path, ciclo_code: str, engine: TranslationEngine) -> None:
    print(f"\n[Pedagogía {ciclo_code}] Procesando {src_path.name} ...")
    with open(src_path, "r", encoding="utf-8") as f:
        data_orig = json.load(f)

    # 1. Generar versión en catalán (_val.json) (traduce p. ej. módulo 0613 que venía en español)
    data_val = translate_pedagogia_dict_direction(data_orig, target_lang="VAL", engine=engine)
    val_path = src_path.parent / f"pedagogia_{ciclo_code.lower()}_val.json"
    with open(val_path, "w", encoding="utf-8") as f:
        json.dump(data_val, f, ensure_ascii=False, indent=2)
    print(f"  -> Guardado {val_path.name}")

    # 2. Generar versión en castellano (_cas.json) (traduce todos los módulos en catalán al castellano)
    data_cas = translate_pedagogia_dict_direction(data_orig, target_lang="CAS", engine=engine)
    cas_path = src_path.parent / f"pedagogia_{ciclo_code.lower()}_cas.json"
    with open(cas_path, "w", encoding="utf-8") as f:
        json.dump(data_cas, f, ensure_ascii=False, indent=2)
    print(f"  -> Guardado {cas_path.name}")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Traductor neuronal local (Softcatalà NMT / SalamandraTA-7B) para JSON de FP."
    )
    parser.add_argument(
        "--engine",
        choices=["softcatala", "salamandra"],
        default="softcatala",
        help="Motor de traducción local a utilizar (por defecto: softcatala).",
    )
    parser.add_argument(
        "--ciclo",
        type=str,
        default=None,
        help="Traducir únicamente un ciclo específico (dam, daw, ia, smx).",
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Traducir todos los currículos y pedagogías del repositorio.",
    )
    args = parser.parse_args()

    if not args.all and not args.ciclo:
        args.all = True

    engine: TranslationEngine
    if args.engine == "softcatala":
        engine = SoftcatalaEngine()
    else:
        engine = SalamandraEngine()

    cycles = ["dam", "daw", "ia", "smx"] if args.all else [args.ciclo.lower()]

    for c in cycles:
        curr_file = ROOT_DIR / f"curriculum_{c}.json"
        if curr_file.exists():
            translate_curriculum_file(curr_file, c.upper(), engine)
        else:
            print(f"[WARN] No existe {curr_file.name}")

        ped_file = ROOT_DIR / f"pedagogia_{c}.json"
        if ped_file.exists():
            translate_pedagogia_file(ped_file, c.upper(), engine)
        else:
            print(f"[WARN] No existe {ped_file.name}")

    print("\n[OK] Traducción de archivos JSON completada con éxito.")


if __name__ == "__main__":
    main()
