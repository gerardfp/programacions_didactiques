#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generador_pd.py
===============
Sistema unificado, modular y sistemático de generación de Programaciones Didácticas
para Formación Profesional basado en plantilla nativa OpenDocument (plantilla.fodt).

Contiene 3 funciones / subsistemas utilizables de forma totalmente individual:
1. PARTE 1: Parseo de XML del BOE y validación estructural del currículo JSON.
2. PARTE 2: Generación del andamiaje pedagógico oficial por ciclo (pedagogia_<ciclo>.json).
3. PARTE 3: Generación y maquetación de Programaciones Didácticas oficiales en formato .odt.

Política de guardado seguro:
Ningún archivo JSON existente es jamás borrado ni sobrescrito. Si el archivo base ya existe,
la nueva versión generada se guarda con una marca de tiempo (_YYYYMMDD_HHMMSS.json).
"""

import os
import sys
import re
import glob
import copy
import json
import shutil
import zipfile
import argparse
import datetime
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple

try:
    from pypdf import PdfReader
except ImportError:
    PdfReader = None

# Configurar stdout/stderr en UTF-8 seguro para Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8', errors='replace')


def slugify(text: str) -> str:
    """Genera un slug limpio y seguro para nombres de archivo."""
    text = unicodedata.normalize('NFD', text)
    text = ''.join(c for c in text if unicodedata.category(c) != 'Mn')
    text = re.sub(r'[^a-zA-Z0-9]+', '_', text).strip('_').lower()
    return text[:40]


def safe_save_json(filepath: str, data: Any, indent: int = 2) -> str:
    """
    Guarda los datos en 'filepath' en formato JSON con codificación UTF-8.
    POLÍTICA DE GUARDADO:
    Si 'filepath' ya existe, no se sobrescribe ni se borra: la NUEVA versión
    se guarda con una marca de tiempo (_YYYYMMDD_HHMMSS).
    Retorna la ruta donde se ha guardado el archivo.
    Guarda los datos en formato JSON con codificación UTF-8 sin sobrescribir versiones previas.
    POLÍTICA DE VERSIONADO Y ARCHIVADO:
    1. La NUEVA versión siempre se guarda con marca de tiempo (_YYYYMMDD_HHMMSS) en el directorio de destino.
    2. Las versiones anteriores del mismo tipo/familia de archivo existentes en dicho directorio
       se trasladan a la subcarpeta 'old_jsons/'.
    3. En el directorio raíz solo queda la versión más reciente.
    Retorna la ruta donde se ha guardado el nuevo archivo.
    """
    target_path = filepath
    if os.path.exists(filepath):
        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
        base, ext = os.path.splitext(filepath)
        target_path = f"{base}_{timestamp}{ext}"
        counter = 1
        while os.path.exists(target_path):
            target_path = f"{base}_{timestamp}_{counter}{ext}"
            counter += 1
        print(f"[*] El archivo base '{filepath}' ya existe. Nueva versión guardada como: '{target_path}'")
    else:
        print(f"[*] Guardando archivo nuevo: '{target_path}'")
    dir_path = os.path.dirname(filepath) or "."
    filename = os.path.basename(filepath)
    stem, ext = os.path.splitext(filename)
    if not ext:
        ext = ".json"

    # Extraer el prefijo base de la familia (quitando timestamp previo si existiera)
    match = re.match(r"^(.*?)(?:_\d{8}_\d{6}(?:_\d+)?)?$", stem)
    base_prefix = match.group(1) if match else stem

    # Generar el nombre de la nueva versión con marca de tiempo
    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")
    new_filename = f"{base_prefix}_{timestamp}{ext}"
    target_path = os.path.join(dir_path, new_filename)
    counter = 1
    while os.path.exists(target_path):
        new_filename = f"{base_prefix}_{timestamp}_{counter}{ext}"
        target_path = os.path.join(dir_path, new_filename)
        counter += 1

    # Preparar la carpeta de archivado 'old_jsons'
    old_dir = os.path.join(dir_path, "old_jsons")
    os.makedirs(old_dir, exist_ok=True)

    # Identificar y mover las versiones anteriores de esta misma familia en dir_path
    family_pattern = rf"^{re.escape(base_prefix)}(?:_\d{{8}}_\d{{6}}(?:_\d+)?)?{re.escape(ext)}$"
    for item in os.listdir(dir_path):
        item_path = os.path.join(dir_path, item)
        if not os.path.isfile(item_path):
            continue
        if os.path.abspath(item_path) == os.path.abspath(target_path):
            continue
        if re.match(family_pattern, item, re.IGNORECASE):
            dest_name = item
            dest_path = os.path.join(old_dir, dest_name)
            if os.path.exists(dest_path):
                d_stem, d_ext = os.path.splitext(dest_name)
                c = 1
                while os.path.exists(os.path.join(old_dir, f"{d_stem}_{c}{d_ext}")):
                    c += 1
                dest_path = os.path.join(old_dir, f"{d_stem}_{c}{d_ext}")
            try:
                shutil.move(item_path, dest_path)
                print(f"[*] Versión anterior '{item}' archivada en 'old_jsons/{os.path.basename(dest_path)}'")
            except Exception as e:
                print(f"[WARN] No se pudo archivar '{item}' en 'old_jsons/': {e}", file=sys.stderr)

    # Guardar la nueva versión en la raíz
    os.makedirs(os.path.dirname(os.path.abspath(target_path)), exist_ok=True)
    with open(target_path, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=indent)
    print(f"[OK] Archivo guardado correctamente en: '{target_path}'")
    print(f"[OK] Nueva versión guardada en: '{target_path}'")
    return target_path


# ==============================================================================
# CONFIGURACIÓN Y VALORES POR DEFECTO DEL SISTEMA
# ==============================================================================

DEFAULT_CONFIG: Dict[str, Any] = {
    "metadata": {
        "centro": "IES Benigasló",
        "profesor": "Profesorado del Departamento de Informática",
        "curso_academico": "2026 / 2027",
        "familia_profesional": "Informática y Comunicaciones",
        "nivel": "Grado Superior",
        "curso_orientativo": "1º",
        "creditos_ects": 8,
        "normativa_referencia": "Normativa de referencia oficial del título",
        "output_dir": "programaciones",
        "template_path": "plantilla.fodt",
    },
    "acreditacion": {
        "sin_uc_text": "Módulo profesional de carácter complementario / transversal; no acredita directamente Unidades de Competencia del Catálogo Nacional (CNCP).",
        "sin_uc_label": "Sin acreditación directa de Unidades de Competencia",
        "sin_ifc_label": "Módulo formativo transversal / complementario",
        "cualif_default": "Cualificación de referencia del Catálogo Nacional",
    },
    "pedagogia": {
        "empty_units": [
            {
                "codigo": "UD 1",
                "nombre": "Fundamentos y principios teóricos",
                "ras": [1],
                "horas_ratio": 0.5,
                "trimestre": "1er Trimestre",
                "inicio": "",
                "fin": ""
            },
            {
                "codigo": "UD 2",
                "nombre": "Aplicaciones avanzadas y proyectos",
                "ras": [1],
                "horas_ratio": 0.5,
                "trimestre": "2º Trimestre",
                "inicio": "",
                "fin": ""
            }
        ],
        "evaluacion": {
            "instrumentos_fallback": [
                {"nombre": "Prueba de evaluación práctica / proyecto", "peso_ra": 60.0},
                {"nombre": "Prueba de evaluación teórico-conceptual", "peso_ra": 40.0}
            ],
            "instrumento_unico_nombre": "Pruebas de evaluación teórico-prácticas y proyectos",
            "formula_prefix": "Módulo =",
        },
        "metodologia_template": (
            "El módulo de {mod_name} se desarrolla combinando sesiones de exposición inductiva con "
            "trabajo práctico intensivo en el laboratorio informático. Se prioriza el Aprendizaje Basado en Proyectos (ABP), "
            "la resolución sistemática de problemas reales y el aprendizaje cooperativo, integrando buenas prácticas profesionales."
        ),
        "contextualizacion_template": (
            "La formación del módulo profesional de {mod_name} capacita al alumnado para desempeñar con "
            "solvencia las funciones técnicas, organizativas y operativas asociadas al perfil laboral del título, "
            "garantizando la calidad, seguridad y cumplimiento de los estándares del sector profesional."
        ),
        "competencia_desc_default": "Descripción de la competencia en el currículo oficial",
        "recursos_software": [
            "Plataforma de aprendizaje",
            "Herramientas de gestión"
        ],
        "recursos_hardware": [
            "Computadora con acceso a internet"
        ],
        "recursos_especificos_fallback": [
            "• Software técnico: Plataforma de aprendizaje y herramientas de gestión.",
            "• Hardware e instrumental: Computadora con acceso a internet."
        ],
        "espacios": "Aula polivalente"
    }
}


# ==============================================================================
# GESTIÓN DE SIGLAS Y NOMENCLATURA ESTÁNDAR
# ==============================================================================

def get_module_initials(
    mod_data: Optional[Dict[str, Any]] = None,
    mod_code: str = "",
    mod_name: str = ""
) -> str:
    """
    Obtiene las siglas oficiales del módulo directamente de los datos del currículo (campo 'siglas' o 'iniciales').
    Si no están definidas en el currículo JSON, genera dinámicamente siglas algorítmicas basadas en el nombre.
    """
    if mod_data:
        siglas = mod_data.get("siglas") or mod_data.get("iniciales")
        if siglas:
            return str(siglas).strip().upper()
        if not mod_code:
            mod_code = str(mod_data.get("codigo", ""))
        if not mod_name:
            mod_name = str(mod_data.get("nombre", ""))

    words = re.findall(r'[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ]+', mod_name)
    stopwords = {'de', 'del', 'en', 'la', 'el', 'los', 'las', 'a', 'para', 'por', 'sobre', 'con', 'y', 'o'}
    sig_words = [w for w in words if w.lower() not in stopwords]
    
    if len(sig_words) == 1 and len(sig_words[0]) > 4:
        return sig_words[0][:4].upper()
        
    initials = []
    for w in sig_words:
        c = unicodedata.normalize('NFD', w[0])[0].upper()
        initials.append(c)
    return "".join(initials) if initials else "MOD"


def get_pd_filename(
    ciclo: str,
    curso: str,
    mod_code: str,
    mod_name: str,
    mod_data: Optional[Dict[str, Any]] = None,
    curso_academico: Optional[str] = None,
    idioma: str = "CAS"
) -> str:
    """
    Genera el nombre estándar de archivo:
    PD_{curso_escolar}_{ciclo}{curso}_{codigo}_{iniciales}_{IDIOMA}.odt
    Ejemplo: PD_26-27_DAM2_0489_PMYDM_CAS.odt
             PD_26-27_DAM2_0489_PMYDM_VAL.odt
    """
    if curso_academico is None:
        curso_academico = DEFAULT_CONFIG["metadata"]["curso_academico"]

    # 1. Curso escolar: "2026 / 2027" -> "26-27"
    years = re.findall(r'\b\d{2,4}\b', curso_academico)
    if len(years) >= 2:
        y1 = years[0][-2:]
        y2 = years[1][-2:]
        curso_esc = f"{y1}-{y2}"
    else:
        curso_esc = "26-27"

    # 2. Ciclo y curso: DAM + 2 -> DAM2
    c_digits = re.findall(r'\d', str(curso))
    c_num = c_digits[0] if c_digits else "1"
    ciclo_curso = f"{ciclo.upper()}{c_num}"

    # 3. Código numérico de 4 dígitos
    code_str = str(mod_code).zfill(4)

    # 4. Siglas del módulo (leídas directamente de mod_data o calculadas si no existen)
    initials = get_module_initials(mod_data=mod_data, mod_code=code_str, mod_name=mod_name)

    # 5. Sufijo de idioma: _VAL o _CAS
    lang_tag = "VAL" if str(idioma).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"

    return f"PD_{curso_esc}_{ciclo_curso}_{code_str}_{initials}_{lang_tag}.odt"


# ==============================================================================
# PARTE 1: PARSER Y VALIDADOR DE CURRÍCULOS BOE XML
# ==============================================================================

# ==============================================================================
# SUBSISTEMAS DE SANITIZACIÓN Y GENERACIÓN DE DATOS GENÉRICOS
# ==============================================================================

class CurriculumSanitizer:
    """
    Inspecciona y subsana automáticamente currículos JSON o datos extraídos del BOE.
    Cuando detecta datos ausentes o incompletos, advierte al usuario con mensajes [AVISO]
    y genera datos genéricos consistentes para garantizar la ejecución ininterrumpida.
    """
    @classmethod
    def sanitize_and_repair(cls, data: Dict[str, Any], source_desc: str = "Currículo") -> Dict[str, Any]:
        if not isinstance(data, dict):
            print(f"[AVISO] [{source_desc}] La estructura debe ser un objeto JSON (dict). Se reinicializa a estructura base.")
            data = {}

        meta_def = DEFAULT_CONFIG["metadata"]

        # 1. Ciclo
        if not data.get("ciclo") or not isinstance(data["ciclo"], str) or not data["ciclo"].strip():
            inferred = "FP"
            m = re.search(r'curriculum_([a-zA-Z0-9]+)', source_desc, re.I)
            if m:
                inferred = m.group(1).upper()
            data["ciclo"] = inferred
            print(f"[AVISO] [{source_desc}] Falta el campo 'ciclo'. Se ha asignado '{inferred}'.")
        else:
            data["ciclo"] = data["ciclo"].strip().upper()

        c_code = data["ciclo"]

        # 2. Título
        if not data.get("titulo") or not isinstance(data["titulo"], str) or not data["titulo"].strip():
            gen_titulo = f"Ciclo Formativo de Formación Profesional en {c_code}"
            data["titulo"] = gen_titulo
            print(f"[AVISO] [{source_desc}] Falta el título oficial ('titulo'). Se ha generado título genérico: '{gen_titulo}'.")

        # 3. Familia profesional
        if not data.get("familia_profesional") or not isinstance(data["familia_profesional"], str) or not data["familia_profesional"].strip():
            data["familia_profesional"] = meta_def["familia_profesional"]
            print(f"[AVISO] [{source_desc}] Falta 'familia_profesional'. Se ha asignado por defecto: '{meta_def['familia_profesional']}'.")

        # 4. Nivel
        if not data.get("nivel") or not isinstance(data["nivel"], str) or not data["nivel"].strip():
            data["nivel"] = meta_def["nivel"]

        # 5. Normativa de referencia
        if not data.get("normativa_referencia") or not isinstance(data["normativa_referencia"], str) or not data["normativa_referencia"].strip():
            data["normativa_referencia"] = meta_def["normativa_referencia"]
            print(f"[AVISO] [{source_desc}] Falta 'normativa_referencia'. Se ha asignado normativa genérica: '{meta_def['normativa_referencia']}'.")

        # 6. Competencias profesionales, personales y sociales
        comps = data.get("competencias_profesionales_personales_sociales")
        if not isinstance(comps, dict) or len(comps) == 0:
            data["competencias_profesionales_personales_sociales"] = {
                "a": f"Planificar, desarrollar y mantener los sistemas y procesos asociados al perfil profesional de {c_code}.",
                "b": "Aplicar las normas de seguridad, calidad y optimización en las actividades profesionales.",
                "c": "Trabajar en equipo y adaptarse a la evolución de las herramientas tecnológicas y normativas del sector."
            }
            print(f"[AVISO] [{source_desc}] No se encontraron competencias profesionales, personales y sociales. Se han generado competencias genéricas.")

        # 7. Módulos
        mods = data.get("modulos")
        if not isinstance(mods, list):
            data["modulos"] = []
            print(f"[AVISO] [{source_desc}] No se encontró la lista 'modulos'. Se inicializa como lista vacía.")
        else:
            for idx, mod in enumerate(data["modulos"]):
                cls.sanitize_module(mod, source_desc=f"{source_desc} -> Módulo #{idx+1}", c_code=c_code)

        return data

    @classmethod
    def sanitize_module(cls, mod: Dict[str, Any], source_desc: str = "", c_code: str = "") -> Dict[str, Any]:
        if not isinstance(mod, dict):
            return mod

        meta_def = DEFAULT_CONFIG["metadata"]

        # Código
        raw_code = str(mod.get("codigo", "")).strip()
        code_digits = "".join(c for c in raw_code if c.isdigit())
        if len(code_digits) in (3, 4):
            mod["codigo"] = code_digits.zfill(4)
        elif code_digits:
            mod["codigo"] = code_digits[:4].zfill(4)
        else:
            mod["codigo"] = "0000"
            print(f"[AVISO] [{source_desc}] Módulo sin código numérico oficial. Se asigna código provisional '0000'.")

        code = mod["codigo"]

        # Nombre
        if not mod.get("nombre") or not isinstance(mod["nombre"], str) or not mod["nombre"].strip():
            mod["nombre"] = f"Módulo Profesional {code}"
            print(f"[AVISO] [{source_desc} ({code})] Falta el nombre del módulo. Se asigna '{mod['nombre']}'.")

        nombre = mod["nombre"]

        # Siglas
        if not mod.get("siglas") or not isinstance(mod["siglas"], str) or not mod["siglas"].strip():
            gen_siglas = get_module_initials(mod_name=nombre, mod_code=code)
            mod["siglas"] = gen_siglas
            print(f"[AVISO] [{source_desc} ({code})] Faltan las 'siglas'. Se han calculado siglas genéricas: '{gen_siglas}'.")

        # Curso orientativo
        if not mod.get("curso_orientativo") or not isinstance(mod["curso_orientativo"], str) or not mod["curso_orientativo"].strip():
            mod["curso_orientativo"] = meta_def["curso_orientativo"]
            print(f"[AVISO] [{source_desc} ({code})] Falta 'curso_orientativo'. Se asigna por defecto '{meta_def['curso_orientativo']}'.")

        # Horas
        try:
            mod["horas"] = int(mod.get("horas", 0))
        except (ValueError, TypeError):
            mod["horas"] = 0
        if mod["horas"] <= 0:
            ects = mod.get("creditos_ects", meta_def["creditos_ects"])
            try:
                mod["horas"] = int(ects) * 25
            except (ValueError, TypeError):
                mod["horas"] = 160
            print(f"[AVISO] [{source_desc} ({code})] Faltan las 'horas' lectivas. Se han asignado {mod['horas']} horas por defecto.")

        # Créditos ECTS
        try:
            mod["creditos_ects"] = int(mod.get("creditos_ects", 0))
        except (ValueError, TypeError):
            mod["creditos_ects"] = 0
        if mod["creditos_ects"] <= 0:
            mod["creditos_ects"] = max(1, round(mod["horas"] / 25))
            print(f"[AVISO] [{source_desc} ({code})] Faltan 'creditos_ects'. Se han asignado {mod['creditos_ects']} ECTS por defecto.")

        # Resultados de Aprendizaje
        ras = mod.get("resultados_aprendizaje")
        if not isinstance(ras, list) or len(ras) == 0:
            mod["resultados_aprendizaje"] = [
                {
                    "numero": 1,
                    "descripcion": f"Desarrolla las competencias y destrezas básicas asociadas al módulo de {nombre}.",
                    "criterios_evaluacion": [
                        {"letra": "a", "descripcion": "Se han identificado los conceptos clave y fundamentos técnicos del módulo."},
                        {"letra": "b", "descripcion": "Se han ejecutado las tareas prácticas y aplicado las buenas prácticas establecidas."}
                    ]
                }
            ]
            print(f"[AVISO] [{source_desc} ({code})] No tiene 'resultados_aprendizaje' definidos. Se ha generado 1 Resultado de Aprendizaje genérico con sus Criterios de Evaluación.")
        else:
            for r_idx, ra in enumerate(ras, start=1):
                if not isinstance(ra, dict):
                    continue
                if "numero" not in ra or not isinstance(ra["numero"], (int, float)):
                    ra["numero"] = r_idx
                if not ra.get("descripcion") or not str(ra["descripcion"]).strip():
                    ra["descripcion"] = f"Aplica los fundamentos y procedimientos prácticos del RA {ra['numero']} de {nombre}."
                    print(f"[AVISO] [{source_desc} ({code}) -> RA #{ra['numero']}] Falta descripción del RA. Se genera descripción genérica.")
                ces = ra.get("criterios_evaluacion")
                if not isinstance(ces, list) or len(ces) == 0:
                    ra["criterios_evaluacion"] = [
                        {"letra": "a", "descripcion": f"Se han comprendido y aplicado los conceptos esenciales del RA {ra['numero']}."},
                        {"letra": "b", "descripcion": "Se han resuelto los supuestos prácticos con rigor técnico y metodológico."}
                    ]
                    print(f"[AVISO] [{source_desc} ({code}) -> RA #{ra['numero']}] Faltan criterios de evaluación. Se han generado criterios genéricos (a y b).")

        return mod


class PedagogicalSanitizer:
    """
    Inspecciona y subsana la estructura pedagógica de un módulo.
    Advierte si faltan campos y sintetiza datos genéricos coherentes (unidades,
    ponderaciones proporcionales 100%, instrumentos prácticos/teóricos, metodología y recursos).
    """
    @classmethod
    def sanitize_and_repair(
        cls,
        mod_code: str,
        ped_data: Optional[Dict[str, Any]],
        mod_data: Dict[str, Any],
        ciclo: str = ""
    ) -> Dict[str, Any]:
        mod_name = mod_data.get("nombre", f"Módulo {mod_code}")
        ras = mod_data.get("resultados_aprendizaje", [])

        if ped_data is None or not isinstance(ped_data, dict):
            print(f"[AVISO] [Módulo {mod_code}] No existen datos pedagógicos específicos en los archivos JSON. Se genera andamiaje pedagógico genérico completo.")
            return PedagogicalScaffoldGenerator.generate_module_scaffold(mod_data, ciclo_code=ciclo)

        ped_defaults = DEFAULT_CONFIG["pedagogia"]

        # 0. Normalización de alias y estructuras anidadas
        if "unidades" not in ped_data and "unidades_programacion" in ped_data:
            ped_data["unidades"] = ped_data["unidades_programacion"]

        if "ra_ponderaciones" not in ped_data and "ponderaciones_ra" in ped_data:
            praw = ped_data["ponderaciones_ra"]
            if isinstance(praw, list):
                dict_w = {}
                for item in praw:
                    c = str(item.get("codigo") or item.get("ra") or "")
                    m_num = re.search(r'\d+', c)
                    k = m_num.group(0) if m_num else str(len(dict_w) + 1)
                    dict_w[k] = float(item.get("peso", 0.0))
                ped_data["ra_ponderaciones"] = dict_w
            elif isinstance(praw, dict):
                ped_data["ra_ponderaciones"] = {str(k): float(v) for k, v in praw.items()}

        if "recursos" in ped_data and isinstance(ped_data["recursos"], dict):
            if "recursos_software" not in ped_data and "software" in ped_data["recursos"]:
                ped_data["recursos_software"] = ped_data["recursos"]["software"]
            if "recursos_hardware" not in ped_data and "hardware" in ped_data["recursos"]:
                ped_data["recursos_hardware"] = ped_data["recursos"]["hardware"]

        if "espacios" in ped_data and isinstance(ped_data["espacios"], list):
            ped_data["espacios"] = ", ".join(ped_data["espacios"])

        # 1. Ponderaciones de RAs
        ra_ponderaciones = ped_data.get("ra_ponderaciones")
        if not isinstance(ra_ponderaciones, dict) or len(ra_ponderaciones) == 0:
            print(f"[AVISO] [Módulo {mod_code}] Faltan 'ra_ponderaciones'. Se calculan ponderaciones proporcionales equitativas (suman 100%).")
            ped_data["ra_ponderaciones"] = cls._generate_proportional_weights(ras)
        else:
            for r_idx, ra in enumerate(ras, start=1):
                r_num = str(ra.get("numero", r_idx))
                if r_num not in ped_data["ra_ponderaciones"]:
                    print(f"[AVISO] [Módulo {mod_code}] Falta ponderación para RA #{r_num}. Se recalcula ponderación equitativa.")
                    ped_data["ra_ponderaciones"] = cls._generate_proportional_weights(ras)
                    break

        # 2. Unidades de programación
        unidades = ped_data.get("unidades")
        if not isinstance(unidades, list) or len(unidades) == 0:
            print(f"[AVISO] [Módulo {mod_code}] Faltan 'unidades' didácticas. Se generan unidades genéricas basadas en los RAs.")
            scaffold = PedagogicalScaffoldGenerator.generate_module_scaffold(mod_data, ciclo_code=ciclo)
            ped_data["unidades"] = scaffold["unidades"]

        # 3. Fórmula de evaluación
        if not ped_data.get("formula_evaluacion") or not str(ped_data["formula_evaluacion"]).strip():
            terms = [f"{float(w)/100:.2f} · RA_{r}" for r, w in ped_data["ra_ponderaciones"].items()]
            ped_data["formula_evaluacion"] = f"Módulo = {' + '.join(terms)}"
            print(f"[AVISO] [Módulo {mod_code}] Falta 'formula_evaluacion'. Se ha generado automáticamente a partir de las ponderaciones.")

        # 4. Instrumentos de evaluación
        instrumentos = ped_data.get("instrumentos")
        inst_eval_list = ped_data.get("instrumentos_evaluacion")
        if (not isinstance(instrumentos, dict) or len(instrumentos) == 0) and isinstance(inst_eval_list, list) and len(inst_eval_list) > 0:
            ped_data["instrumentos"] = {}
            for r_key in ped_data["ra_ponderaciones"].keys():
                ped_data["instrumentos"][r_key] = [
                    {
                        "nombre": item.get("nombre", "Instrumento de evaluación"),
                        "peso_ra": float(item.get("porcentaje", item.get("peso", 50.0)))
                    }
                    for item in inst_eval_list
                ]
        elif not isinstance(instrumentos, dict) or len(instrumentos) == 0:
            ped_data["instrumentos"] = {}
            for r_key in ped_data["ra_ponderaciones"].keys():
                ped_data["instrumentos"][r_key] = [
                    {"nombre": "Prueba de evaluación práctica / proyecto", "peso_ra": 60.0},
                    {"nombre": "Prueba de evaluación teórico-conceptual", "peso_ra": 40.0}
                ]
            print(f"[AVISO] [Módulo {mod_code}] Faltan 'instrumentos' de evaluación. Se asignan instrumentos genéricos (60% práctica / 40% teoría).")
        else:
            for r_key in ped_data["ra_ponderaciones"].keys():
                if r_key not in ped_data["instrumentos"] or not ped_data["instrumentos"][r_key]:
                    ped_data["instrumentos"][r_key] = [
                        {"nombre": "Prueba de evaluación práctica / proyecto", "peso_ra": 60.0},
                        {"nombre": "Prueba de evaluación teórico-conceptual", "peso_ra": 40.0}
                    ]
                    print(f"[AVISO] [Módulo {mod_code}] Faltan instrumentos de evaluación para RA #{r_key}. Se asignan instrumentos estándar.")

        # 5. Metodología
        if not ped_data.get("metodologia") or not str(ped_data["metodologia"]).strip():
            ped_data["metodologia"] = ped_defaults["metodologia_template"].format(mod_name=mod_name)
            print(f"[AVISO] [Módulo {mod_code}] Falta 'metodologia'. Se asigna metodología activa estándar.")

        # 6. Recursos software
        sw = ped_data.get("recursos_software")
        if not isinstance(sw, list) or len(sw) == 0:
            ped_data["recursos_software"] = list(ped_defaults["recursos_software"])
            print(f"[AVISO] [Módulo {mod_code}] Faltan 'recursos_software'. Se asignan recursos software genéricos.")

        # 7. Recursos hardware
        hw = ped_data.get("recursos_hardware")
        if not isinstance(hw, list) or len(hw) == 0:
            ped_data["recursos_hardware"] = list(ped_defaults["recursos_hardware"])
            print(f"[AVISO] [Módulo {mod_code}] Faltan 'recursos_hardware'. Se asignan recursos hardware genéricos.")

        # 8. Espacios
        esp = ped_data.get("espacios")
        if isinstance(esp, list):
            ped_data["espacios"] = ", ".join(esp)
        elif not esp or not str(esp).strip():
            ped_data["espacios"] = ped_defaults["espacios"]
            print(f"[AVISO] [Módulo {mod_code}] Faltan 'espacios'. Se asigna '{ped_defaults['espacios']}' por defecto.")

        return ped_data

    @staticmethod
    def _generate_proportional_weights(ras: list) -> Dict[str, float]:
        num_ras = len(ras)
        if num_ras == 0:
            return {"1": 100.0}
        base_w = round(100.0 / num_ras, 1)
        res = {}
        curr_sum = 0.0
        for idx, ra in enumerate(ras, start=1):
            r_num = str(ra.get("numero", idx))
            if idx == num_ras:
                w = round(100.0 - curr_sum, 1)
            else:
                w = base_w
                curr_sum += w
            res[r_num] = w
        return res


class BoeCurriculumParser:
    """
    Parsea decretos oficiales en XML del BOE y construye la estructura oficial
    de currículo formativo con competencias, módulos, siglas, RAs y CEs.
    """
    @classmethod
    def parse_xml_file(cls, xml_path: str, forced_ciclo: Optional[str] = None) -> Dict[str, Any]:
        if not os.path.exists(xml_path):
            raise FileNotFoundError(f"Archivo XML no encontrado: '{xml_path}'")

        tree = ET.parse(xml_path)
        root = tree.getroot()

        # Extraer título oficial de metadatos o texto
        titulo_decreto = root.findtext('.//metadatos/titulo')
        if titulo_decreto:
            titulo_decreto = titulo_decreto.strip()

        # Buscar el elemento de texto con contenido
        texto_elem = root.find('./texto')
        if texto_elem is None or len(list(texto_elem.iter('p'))) == 0:
            for cand in root.findall('.//texto'):
                if len(list(cand.iter('p'))) > 0:
                    texto_elem = cand
                    break
        if texto_elem is None:
            texto_elem = root

        p_texts = []
        for p in texto_elem.iter('p'):
            t = "".join(p.itertext()).strip()
            if t:
                p_texts.append(t)

        if not titulo_decreto:
            for p in p_texts[:15]:
                if "Real Decreto" in p or "Orden" in p:
                    titulo_decreto = p
                    break
        if not titulo_decreto:
            titulo_decreto = f"Decreto oficial ({os.path.basename(xml_path)})"

        file_base = os.path.splitext(os.path.basename(xml_path))[0].upper()
        if forced_ciclo:
            cycle_key = forced_ciclo.strip().upper()
        elif "IABD" in file_base or "IA" in file_base:
            cycle_key = "IA"
        else:
            cycle_key = file_base

        is_ce = "ESPECIALIZACI" in titulo_decreto.upper() or cycle_key in ["IA", "IABD", "CEIABD"]
        nivel = "Curso de Especialización" if is_ce else DEFAULT_CONFIG["metadata"]["nivel"]
        if is_ce and "Inteligencia Artificial" in titulo_decreto:
            titulo_ciclo = "Curso de Especialización en Inteligencia Artificial y Big Data"
        else:
            titulo_ciclo = f"Ciclo Formativo en {cycle_key}"

        # Extraer competencias profesionales, personales y sociales
        competencias = {}
        in_comp = False
        for p in p_texts:
            if not competencias and (
                re.search(r'^Art[ií]culo\s+\d+[\.\s]+Competencias\s+profesionales', p.strip(), re.I) or
                re.search(r'^Competencias\s+profesionales,\s*personales\s+y\s+sociales', p.strip(), re.I)
            ):
                in_comp = True
                continue
            if in_comp:
                if re.search(r'^Art[ií]culo\s+\d+\b', p.strip(), re.I) or re.search(r'^Cap[ií]tulo\b', p.strip(), re.I) or re.match(r'^ANEXO\b', p.strip(), re.I):
                    in_comp = False
                    continue
                m = re.match(r'^([a-zñáéíóú])\)\s*(.+)', p, re.IGNORECASE)
                if m:
                    competencias[m.group(1).lower()] = m.group(2).strip()

        # Fallback para estructuras donde no hay delimitador estricto
        if not competencias:
            for p in p_texts:
                m = re.match(r'^([a-zñ])\)\s+(.+)', p)
                if m:
                    letra = m.group(1).lower()
                    if letra not in competencias and len(m.group(2).strip()) > 10:
                        competencias[letra] = m.group(2).strip()

        # Delimitar Anexo I (módulos) y Anexo II
        anexo1_idx = 0
        for idx, p in enumerate(p_texts):
            if re.match(r'^ANEXO\s+I\b', p.strip(), re.I):
                anexo1_idx = idx
                break

        anexo2_idx = len(p_texts)
        for idx in range(anexo1_idx + 1, len(p_texts)):
            if re.match(r'^ANEXO\s+II\b', p.strip(), re.I):
                anexo2_idx = idx
                break

        mod_starts = []
        for idx in range(anexo1_idx, anexo2_idx):
            if re.search(r'^M[oó]dulo\s+profesional\s*:', p_texts[idx], re.I):
                mod_starts.append(idx)
        mod_starts.append(anexo2_idx)

        modules = []
        for i in range(len(mod_starts) - 1):
            s_idx = mod_starts[i]
            e_idx = mod_starts[i + 1]
            m_lines = p_texts[s_idx:e_idx]

            header_line = m_lines[0]
            m_name = re.sub(r'^M[oó]dulo\s+profesional\s*:\s*', '', header_line, flags=re.IGNORECASE).rstrip('.').strip()

            m_code = ""
            ects = 0
            mod_hours = 0
            for l in m_lines[:8]:
                code_m = re.search(r'C[oó]digo:\s*(\d{3,4})', l, re.I)
                if code_m:
                    m_code = code_m.group(1).zfill(4)
                ects_m = re.search(r'cr[eé]ditos\s+ECTS:\s*(\d+)', l, re.I)
                if ects_m:
                    ects = int(ects_m.group(1))

            for l in m_lines:
                h_m = re.search(r'Duraci[oó]n:\s*(\d+)\s*horas', l, re.I)
                if h_m:
                    mod_hours = int(h_m.group(1))
                    break

            if not mod_hours:
                mod_hours = (ects * 25) if ects > 0 else 160
            if not ects and mod_hours:
                ects = max(1, round(mod_hours / 25))
            if not m_code:
                m_code = str(i + 1).zfill(4)

            ras = []
            in_ras = False
            current_ra = None
            orientaciones = []
            in_orientaciones = False
            in_cb = False
            cb_lines = []

            for l in m_lines:
                if re.search(r'Resultados\s+de\s+aprendizaje\s+y\s+criterios\s+de\s+evaluaci[oó]n', l, re.I) or re.search(r'^Resultados\s+de\s+aprendizaje\b', l, re.I):
                    in_ras = True
                    continue
                if re.search(r'^Contenidos(?:\s+b[aá]sicos)?\s*:?', l, re.I):
                    in_ras = False
                    in_cb = True
                    continue
                if re.search(r'Orientaciones\s+pedag[oó]gicas', l, re.I):
                    in_ras = False
                    in_cb = False
                    in_orientaciones = True
                    continue
                if in_orientaciones:
                    if re.search(r'Duraci[oó]n:\s*\d+\s*horas', l, re.I):
                        in_orientaciones = False
                    else:
                        orientaciones.append(l)
                    continue
                if in_cb:
                    cb_lines.append(l)
                    continue
                if in_ras:
                    ra_m = re.match(r'^(\d+)\.\s*(.+)', l)
                    if ra_m and not re.match(r'^Criterios\s+de\s+evaluaci[oó]n', l, re.I):
                        if current_ra:
                            ras.append(current_ra)
                        current_ra = {
                            "numero": int(ra_m.group(1)),
                            "descripcion": ra_m.group(2).strip(),
                            "criterios_evaluacion": []
                        }
                        continue
                    if current_ra:
                        ce_m = re.match(r'^([a-zñáéíóú])\)\s*(.+)', l, re.I)
                        if ce_m:
                            letter = ce_m.group(1).lower()
                            ra_num = current_ra["numero"]
                            current_ra["criterios_evaluacion"].append({
                                "letra": letter,
                                "codigo": f"RA{ra_num}.{letter}",
                                "descripcion": ce_m.group(2).strip()
                            })
                        else:
                            # Intento de extracción múltiple si vienen agrupados
                            ces_matches = re.findall(r'([a-zñ])\)\s*([^a-zñ\)]+)', l)
                            for letter, ce_desc in ces_matches:
                                ra_num = current_ra["numero"]
                                current_ra["criterios_evaluacion"].append({
                                    "letra": letter.lower(),
                                    "codigo": f"RA{ra_num}.{letter.lower()}",
                                    "descripcion": ce_desc.strip()
                                })

            if current_ra:
                ras.append(current_ra)

            # Parsear bloques de contenidos básicos
            cb_blocks = []
            curr_block = None
            for l in cb_lines:
                clean_l = l.strip()
                if not clean_l:
                    continue
                is_bullet = clean_l.startswith(('−', '-', '•', '*', '–', '·'))
                title_split = re.match(r'^([A-ZÁÉÍÓÚ][^:\.]{3,70}):\s*(.*)', clean_l)
                if not is_bullet and title_split:
                    is_header = True
                    header_title = title_split.group(1).strip()
                    remainder = title_split.group(2).strip()
                elif not is_bullet and (clean_l.endswith(':') or (len(clean_l) < 70 and not clean_l.endswith('.'))):
                    is_header = True
                    header_title = clean_l.rstrip(':').strip()
                    remainder = ""
                else:
                    is_header = False
                    header_title = ""
                    remainder = clean_l

                if is_header:
                    if curr_block:
                        cb_blocks.append(curr_block)
                    curr_block = {"titulo": header_title, "items": []}
                    if remainder:
                        clean_rem = remainder.lstrip('−-•*–· ').strip()
                        if clean_rem:
                            curr_block["items"].append(clean_rem)
                else:
                    if curr_block is None:
                        curr_block = {"titulo": "General", "items": []}
                    item_text = clean_l.lstrip('−-•*–· ').strip()
                    if item_text:
                        curr_block["items"].append(item_text)
            if curr_block:
                cb_blocks.append(curr_block)

            contenidos_list = []
            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                r_desc = ra.get("descripcion", "")
                if idx - 1 < len(cb_blocks):
                    b = cb_blocks[idx - 1]
                    b_title = b["titulo"]
                    b_items = b["items"]
                else:
                    b_title = f"Contenidos del RA{r_num}"
                    b_items = [f"Contenidos y procedimientos aplicados a: {r_desc}"]
                contenidos_list.append({
                    "ra": r_num,
                    "codigo_ra": f"RA{r_num}",
                    "titulo": b_title,
                    "items": b_items
                })
                ra["contenidos"] = {"titulo": b_title, "items": b_items}

            orientaciones_text = "\n\n".join([o.strip() for o in orientaciones if o.strip()])
            mod_comps = list(competencias.keys())[:3]
            curso = "1º" if (is_ce or i % 2 == 0) else "2º"

            modules.append({
                "codigo": m_code,
                "nombre": m_name,
                "siglas": get_module_initials(mod_name=m_name),
                "curso_orientativo": curso,
                "horas": mod_hours,
                "creditos_ects": ects,
                "unidades_competencia": [],
                "competencias_titulo": sorted(mod_comps),
                "orientaciones_pedagogicas": orientaciones_text,
                "resultados_aprendizaje": ras,
                "contenidos": contenidos_list
            })

        meta_def = DEFAULT_CONFIG["metadata"]
        return {
            "ciclo": cycle_key,
            "codigo_ciclo": f"IFC_{cycle_key}",
            "titulo": titulo_ciclo,
            "familia_profesional": meta_def["familia_profesional"],
            "nivel": nivel,
            "normativa_referencia": titulo_decreto,
            "competencias_profesionales_personales_sociales": competencias,
            "cualificaciones_profesionales": [],
            "unidades_competencia": {},
            "correspondencia_unidades_competencia": {},
            "modulos": modules
        }


def run_parse_curriculum(xml_path: str, ciclo: Optional[str] = None, output_path: Optional[str] = None) -> str:
    """Función ejecutable para la Parte 1: Parsear XML y generar JSON con sanitización y guardado seguro."""
    print(f"[*] Parseando archivo BOE XML: {xml_path}")
    curriculum_data = BoeCurriculumParser.parse_xml_file(xml_path, forced_ciclo=ciclo)
    
    print("[*] Comprobando y subsanando posibles datos ausentes...")
    curriculum_data = CurriculumSanitizer.sanitize_and_repair(curriculum_data, source_desc=os.path.basename(xml_path))

    c_code = curriculum_data.get("ciclo", "CICLO").lower()
    target_output = output_path if output_path else f"curriculum_{c_code}.json"
    saved = safe_save_json(target_output, curriculum_data)
    print(f"[OK] Currículo generado exitosamente en: '{saved}'")
    return saved


# ==============================================================================
# PARTE 2: GENERADOR DE ANDAMIAJE PEDAGÓGICO POR CICLO
# ==============================================================================

class PedagogicalScaffoldGenerator:
    """
    Genera el andamiaje pedagógico genérico para todos los módulos de un ciclo formativo
    a partir de la información curricular oficial.
    """
    GENERIC_SOFTWARE = [
        "Plataforma de aprendizaje",
        "Herramientas de gestión"
    ]

    GENERIC_HARDWARE = [
        "Computadora con acceso a internet"
    ]

    GENERIC_ESPACIO = "Aula polivalente"

    @classmethod
    def generate_for_cycle(cls, curriculum_data: Dict[str, Any]) -> Dict[str, Any]:
        ciclo_code = curriculum_data.get("ciclo", "").upper()
        curriculum_data = CurriculumSanitizer.sanitize_and_repair(curriculum_data, source_desc=f"Ciclo {ciclo_code}")
        modules = curriculum_data.get("modulos", [])
        pedagogia_dict = {}

        for mod in modules:
            mod_code = str(mod.get("codigo", "")).zfill(4)
            mod_ped = cls.generate_module_scaffold(mod, ciclo_code)
            pedagogia_dict[mod_code] = mod_ped

        # Incluir módulo genérico del ciclo para resolución en cascada
        generic_mod_scaffold = {
            "nombre": f"Módulo Formativo Genérico ({ciclo_code})",
            "unidades": [
                {
                    "codigo": "UP 1",
                    "nombre": f"Unidad de Programación 1: Fundamentos y competencias clave de {ciclo_code}",
                    "ras": [1],
                    "horas": 160,
                    "trimestre": "1er Trimestre",
                    "inicio": "",
                    "fin": ""
                }
            ],
            "ra_ponderaciones": {"1": 100.0},
            "formula_evaluacion": "Módulo = 1.00 · RA_1",
            "instrumentos": {
                "1": [
                    {"nombre": "Prueba de evaluación práctica / proyecto", "peso_ra": 60.0},
                    {"nombre": "Prueba de evaluación teórico-conceptual", "peso_ra": 40.0}
                ]
            },
            "metodologia": (
                f"El módulo profesional se desarrolla mediante metodologías activas orientadas al perfil de {ciclo_code}, "
                f"priorizando supuestos prácticos, resolución colaborativa de problemas y rigor profesional."
            ),
            "recursos_software": list(cls.GENERIC_SOFTWARE),
            "recursos_hardware": list(cls.GENERIC_HARDWARE),
            "espacios": cls.GENERIC_ESPACIO
        }
        pedagogia_dict["generico"] = generic_mod_scaffold

        return pedagogia_dict

    @classmethod
    def generate_module_scaffold(cls, mod_data: Dict[str, Any], ciclo_code: str = "") -> Dict[str, Any]:
        mod_name = mod_data.get("nombre", "")
        ras = mod_data.get("resultados_aprendizaje", [])
        num_ras = len(ras)
        total_hours = int(mod_data.get("horas") or (mod_data.get("creditos_ects", 8) * 25))

        # 1. Ponderaciones proporcionales de RAs sumando exactamente 100.0%
        ra_ponderaciones = {}
        if num_ras > 0:
            base_w = round(100.0 / num_ras, 1)
            current_sum = 0.0
            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                if idx == num_ras:
                    w = round(100.0 - current_sum, 1)
                else:
                    w = base_w
                    current_sum += w
                ra_ponderaciones[str(r_num)] = w
        else:
            ra_ponderaciones["1"] = 100.0

        # 2. Unidades de Programación (1 UP por cada RA)
        unidades = []
        if num_ras == 0:
            unidades = [
                {
                    "codigo": "UP 1",
                    "nombre": f"Unidad de Programación 1: Fundamentos y desarrollo de {mod_name}",
                    "ras": [1],
                    "horas": total_hours,
                    "trimestre": "1er Trimestre",
                    "inicio": "",
                    "fin": ""
                }
            ]
        else:
            hours_per_ra = max(1, total_hours // num_ras)
            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                r_desc = ra.get("descripcion", "").strip().rstrip(",.:; ")

                if idx <= max(1, (num_ras + 2) // 3):
                    trim = "1er Trimestre"
                elif idx <= max(2, (2 * num_ras + 1) // 3):
                    trim = "2º Trimestre"
                else:
                    trim = "3er Trimestre"

                u_hours = hours_per_ra if idx < num_ras else max(1, (total_hours - hours_per_ra * (num_ras - 1)))

                unidades.append({
                    "codigo": f"UP {idx}",
                    "nombre": f"Unidad de Programación {idx}: {r_desc}",
                    "ras": [r_num],
                    "horas": u_hours,
                    "trimestre": trim,
                    "inicio": "",
                    "fin": ""
                })

        # 3. Dos instrumentos de evaluación genéricos por cada RA (60% práctico / 40% teórico)
        instrumentos = {}
        for r_str in ra_ponderaciones.keys():
            instrumentos[r_str] = [
                {
                    "nombre": "Prueba de evaluación práctica / proyecto",
                    "peso_ra": 60.0
                },
                {
                    "nombre": "Prueba de evaluación teórico-conceptual",
                    "peso_ra": 40.0
                }
            ]

        # 4. Fórmula LaTeX de evaluación
        formula_terms = [f"{w/100:.2f} · RA_{r}" for r, w in ra_ponderaciones.items()]
        formula = f"Módulo = {' + '.join(formula_terms)}"

        # 5. Metodología pedagógica base
        metodologia = (
            f"El módulo profesional de {mod_name} se desarrolla mediante metodologías activas centradas en "
            f"el alumnado, combinando sesiones teóricas inductivas con prácticas aplicadas. Se fomenta el "
            f"Aprendizaje Basado en Proyectos (ABP), la resolución colaborativa de problemas técnicos y "
            f"el rigor metodológico profesional."
        )

        return {
            "nombre": mod_name,
            "unidades": unidades,
            "ra_ponderaciones": ra_ponderaciones,
            "formula_evaluacion": formula,
            "instrumentos": instrumentos,
            "metodologia": metodologia,
            "recursos_software": list(cls.GENERIC_SOFTWARE),
            "recursos_hardware": list(cls.GENERIC_HARDWARE),
            "espacios": cls.GENERIC_ESPACIO
        }


def run_generate_cycle_pedagogy(curriculum_path: str, output_path: Optional[str] = None) -> str:
    """Función ejecutable para generar el archivo pedagogia_<ciclo>.json para un currículo dado."""
    if not os.path.exists(curriculum_path):
        raise FileNotFoundError(f"Currículo no encontrado: '{curriculum_path}'")

    with open(curriculum_path, "r", encoding="utf-8") as f:
        curr_data = json.load(f)

    curr_data = CurriculumSanitizer.sanitize_and_repair(curr_data, source_desc=os.path.basename(curriculum_path))
    c_code = curr_data.get("ciclo", "FP").strip().upper()
    ped_data = PedagogicalScaffoldGenerator.generate_for_cycle(curr_data)

    target_file = output_path if output_path else f"pedagogia_{c_code.lower()}.json"
    saved_path = safe_save_json(target_file, ped_data)
    return saved_path


def run_generate_all_pedagogy(base_dir: str = ".") -> List[str]:
    """Función ejecutable para generar la pedagogía de todos los currículos disponibles."""
    curr_files = glob.glob(os.path.join(base_dir, "curriculum_*.json"))
    base_currs = [f for f in curr_files if not re.search(r'_\d{8}_\d{6}', f)]
    print(f"[*] Generando JSON pedagógico para {len(base_currs)} ciclos disponibles...")
    cycle_files: Dict[str, List[str]] = {}
    json_pattern = os.path.join(base_dir, "curriculum_*.json")
    for j_file in glob.glob(json_pattern):
        m = re.search(r'curriculum_([a-zA-Z0-9]+)(?:_\d{8}_\d{6}(?:_\d+)?)?\.json', os.path.basename(j_file), re.IGNORECASE)
        if m:
            c_code = m.group(1).upper()
            cycle_files.setdefault(c_code, []).append(j_file)

    # Check old_jsons as fallback if any cycle is missing
    old_json_pattern = os.path.join(base_dir, "old_jsons", "curriculum_*.json")
    for j_file in glob.glob(old_json_pattern):
        m = re.search(r'curriculum_([a-zA-Z0-9]+)(?:_\d{8}_\d{6}(?:_\d+)?)?\.json', os.path.basename(j_file), re.IGNORECASE)
        if m:
            c_code = m.group(1).upper()
            if c_code not in cycle_files:
                cycle_files.setdefault(c_code, []).append(j_file)

    latest_currs = []
    for c_code, flist in sorted(cycle_files.items()):
        flist.sort(key=lambda p: (PedagogicalDataProvider._extract_timestamp(p), os.path.getmtime(p)), reverse=True)
        latest_currs.append(flist[0])

    print(f"[*] Generando JSON pedagógico para {len(latest_currs)} ciclos disponibles...")
    generated = []
    for c_file in latest_currs:
        saved = run_generate_cycle_pedagogy(c_file)
        generated.append(saved)
        print(f"    - {c_file} -> {saved}")
    print(f"[OK] Generación completada con éxito. Total: {len(generated)} archivos.")
    return generated


# ==============================================================================
# PARTE 3: GENERADOR DE PROGRAMACIONES DIDÁCTICAS ODT
# ==============================================================================

class CurriculumRepository:
    """
    Descubre y gestiona los currículos de todos los ciclos formativos.
    Carga la versión más reciente disponible (base o con timestamp) para cada ciclo.
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.curriculums: Dict[str, Dict[str, Any]] = {}
        self.curriculums_by_lang: Dict[Tuple[str, str], Dict[str, Any]] = {}
        self._load()

    def _register_cycle_lang(self, c_code: str, lang_tag: str, data: Dict[str, Any]):
        c_up = c_code.upper()
        self.curriculums_by_lang[(c_up, lang_tag)] = data
        if c_up == "IA":
            self.curriculums_by_lang[("IABD", lang_tag)] = data
        elif c_up == "IABD":
            self.curriculums_by_lang[("IA", lang_tag)] = data
        elif c_up == "SMX":
            self.curriculums_by_lang[("SMR", lang_tag)] = data
        elif c_up == "SMR":
            self.curriculums_by_lang[("SMX", lang_tag)] = data

    def _load(self):
        # 1. Cargar archivos específicos por idioma: curriculum_<ciclo>_(cas|val).json
        json_pattern = os.path.join(self.base_dir, "curriculum_*.json")
        for j_file in sorted(glob.glob(json_pattern)):
            fname = os.path.basename(j_file)
            m_lang = re.match(r'^curriculum_([a-zA-Z0-9]+)_(cas|val)\.json$', fname, re.IGNORECASE)
            if m_lang:
                c_code = m_lang.group(1).upper()
                lang_tag = m_lang.group(2).upper()
                try:
                    with open(j_file, "r", encoding="utf-8") as f:
                        data = json.load(f)
                        data = CurriculumSanitizer.sanitize_and_repair(data, source_desc=fname)
                        ciclo_id = data.get("ciclo", c_code).upper()
                        data["ciclo"] = ciclo_id
                        self._register_cycle_lang(ciclo_id, lang_tag, data)
                        self._register_cycle_lang(c_code, lang_tag, data)
                        if lang_tag == "CAS":
                            self.curriculums[ciclo_id] = data
                except Exception as e:
                    print(f"[WARN] No se pudo cargar {j_file}: {e}", file=sys.stderr)

        # 2. Cargar archivos base: curriculum_<ciclo>.json como respaldo
        cycle_files: Dict[str, List[str]] = {}
        for j_file in glob.glob(json_pattern):
            fname = os.path.basename(j_file)
            if re.match(r'^curriculum_([a-zA-Z0-9]+)_(cas|val)\.json$', fname, re.IGNORECASE):
                continue
            m = re.search(r'curriculum_([a-zA-Z0-9]+)(?:_\d{8}_\d{6}(?:_\d+)?)?\.json', fname, re.IGNORECASE)
            if m:
                c_code = m.group(1).upper()
                cycle_files.setdefault(c_code, []).append(j_file)

        # Fallback a old_jsons si algún ciclo no está en la raíz
        old_json_pattern = os.path.join(self.base_dir, "old_jsons", "curriculum_*.json")
        for j_file in glob.glob(old_json_pattern):
            m = re.search(r'curriculum_([a-zA-Z0-9]+)(?:_\d{8}_\d{6}(?:_\d+)?)?\.json', os.path.basename(j_file), re.IGNORECASE)
            if m:
                c_code = m.group(1).upper()
                if c_code not in cycle_files:
                    cycle_files.setdefault(c_code, []).append(j_file)

        for c_code, file_list in cycle_files.items():
            file_list.sort(key=lambda p: (PedagogicalDataProvider._extract_timestamp(p), os.path.getmtime(p)), reverse=True)
            chosen_file = file_list[0]
            try:
                with open(chosen_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data = CurriculumSanitizer.sanitize_and_repair(data, source_desc=os.path.basename(chosen_file))
                    ciclo_id = data.get("ciclo", c_code).upper()
                    data["ciclo"] = ciclo_id
                    if ciclo_id not in self.curriculums:
                        self.curriculums[ciclo_id] = data
                    if (ciclo_id, "CAS") not in self.curriculums_by_lang:
                        self._register_cycle_lang(ciclo_id, "CAS", data)
            except Exception as e:
                print(f"[WARN] No se pudo cargar {chosen_file}: {e}", file=sys.stderr)

        # Descubrir XMLs en curriculums_originals/ si no tienen JSON previo
        xml_dir = os.path.join(self.base_dir, "curriculums_originals")
        if os.path.exists(xml_dir):
            for x_file in glob.glob(os.path.join(xml_dir, "*.xml")):
                base_name = os.path.splitext(os.path.basename(x_file))[0].upper()
                mapped_name = "IA" if "IABD" in base_name else base_name
                if mapped_name not in self.curriculums and base_name not in self.curriculums and base_name != "DAM_DAW":
                    try:
                        parsed = BoeCurriculumParser.parse_xml_file(x_file)
                        if isinstance(parsed, dict) and "ciclo" in parsed:
                            c_code = parsed["ciclo"].upper()
                            self.curriculums[c_code] = parsed
                            out_j = os.path.join(self.base_dir, f"curriculum_{c_code.lower()}.json")
                            safe_save_json(out_j, parsed)
                    except Exception as e:
                        print(f"[WARN] Error parseando XML {x_file}: {e}", file=sys.stderr)

    def get_all_cycles(self) -> Dict[str, Dict[str, Any]]:
        return self.curriculums

    def get_cycle_data(self, ciclo: str, idioma: str = "CAS") -> Optional[Dict[str, Any]]:
        c_upper = ciclo.strip().upper()
        tag = "VAL" if str(idioma).upper() in ("VAL", "VALENCIANO", "VALENCIÀ", "CA", "CAT") else "CAS"
        if (c_upper, tag) in self.curriculums_by_lang:
            return self.curriculums_by_lang[(c_upper, tag)]
        return self.curriculums.get(c_upper)

    def get_module(
        self,
        ciclo: Optional[str],
        identifier: str,
        idioma: str = "CAS"
    ) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        clean_id = str(identifier).strip()
        code_match = re.search(r'\b([0-9]{3,4})\b', clean_id)
        search_code = code_match.group(1).zfill(4) if code_match else None
        tag = "VAL" if str(idioma).upper() in ("VAL", "VALENCIANO", "VALENCIÀ", "CA", "CAT") else "CAS"

        search_cycles = []
        if ciclo:
            c_data = self.get_cycle_data(ciclo, idioma=tag)
            if c_data:
                search_cycles.append(c_data)
        else:
            for c_key in self.curriculums.keys():
                c_data = self.get_cycle_data(c_key, idioma=tag)
                if c_data:
                    search_cycles.append(c_data)

        for c_data in search_cycles:
            for mod in c_data.get("modulos", []):
                code = str(mod.get("codigo", "")).zfill(4)
                if search_code and code == search_code:
                    return mod, c_data
                if clean_id.lower() in mod.get("nombre", "").lower():
                    return mod, c_data

        return None


class PedagogicalDataProvider:
    """
    Suministra la información pedagógica de cada módulo (unidades didácticas,
    ponderaciones de RAs, fórmulas de evaluación, instrumentos, metodología y recursos).
    
    RESOLUCIÓN EN CASCADA (estricta según especificación):
    1. Archivo específico de ciclo y módulo: pedagogia_{ciclo}_{modulo}[_timestamp].json
       (se usa la versión más reciente en caso de existir versiones con timestamp).
    2. Archivo específico de ciclo: pedagogia_{ciclo}[_timestamp].json
       - Si contiene el módulo específico, se usa ese.
       - Si no, y contiene una entrada 'generico', se usa el módulo genérico del ciclo.
    3. Archivo global de pedagogía: pedagogia[_timestamp].json
       - Si contiene el módulo específico o una entrada 'generico', se usa esa.
       (También se consulta como fallback intermedio el archivo 'pedagogia_modulos.json' si existe).
    4. Si al ejecutarse el programa para generar programaciones no se encuentra NINGÚN
       fichero de pedagogía en el sistema:
       - Se genera automáticamente el archivo global 'pedagogia.json' con un módulo genérico.
       - Se informa al usuario de dicha creación.
       - Se utiliza dicho módulo genérico adaptado a las horas y RAs del módulo en curso.
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self._ensure_pedagogy_exists()

    @staticmethod
    def _extract_timestamp(filepath: str) -> str:
        """Extrae la marca temporal _YYYYMMDD_HHMMSS si existe en el nombre de archivo."""
        m = re.search(r'_(\d{8}_\d{6})', os.path.basename(filepath))
        return m.group(1) if m else ""

    def _ensure_pedagogy_exists(self):
        """
        Regla 4: Si al ejecutarse el programa no se encuentra ningún fichero de pedagogía
        (ningún pedagogia*.json), genera 'pedagogia.json' con un módulo genérico.
        """
        pattern = os.path.join(self.base_dir, "pedagogia*.json")
        existing = glob.glob(pattern)
        if not existing:
            old_pattern = os.path.join(self.base_dir, "old_jsons", "pedagogia*.json")
            if glob.glob(old_pattern):
                return
            print("[AVISO] No se encontró ningún archivo de pedagogía en el sistema.")
            print("[AVISO] Generando archivo de pedagogía global genérico: 'pedagogia.json'...")
            default_global = {
                "generico": {
                    "nombre": "Módulo Formativo Genérico",
                    "unidades": [
                        {
                            "codigo": "UP 1",
                            "nombre": "Unidad de Programación 1: Fundamentos y competencias clave",
                            "ras": [1],
                            "horas": 160,
                            "trimestre": "1er Trimestre",
                            "inicio": "",
                            "fin": ""
                        }
                    ],
                    "ra_ponderaciones": {
                        "1": 100.0
                    },
                    "formula_evaluacion": "Módulo = 1.00 · RA_1",
                    "instrumentos": {
                        "1": [
                            {
                                "nombre": "Prueba de evaluación práctica / proyecto",
                                "peso_ra": 60.0
                            },
                            {
                                "nombre": "Prueba de evaluación teórico-conceptual",
                                "peso_ra": 40.0
                            }
                        ]
                    },
                    "metodologia": (
                        "El módulo profesional se desarrolla mediante metodologías activas centradas en el alumnado, "
                        "combinando sesiones teóricas inductivas con supuestos prácticos aplicados en el aula/laboratorio. "
                        "Se fomenta el Aprendizaje Basado en Proyectos (ABP), la resolución de problemas y el trabajo colaborativo."
                    ),
                    "recursos_software": list(DEFAULT_CONFIG["pedagogia"]["recursos_software"]),
                    "recursos_hardware": list(DEFAULT_CONFIG["pedagogia"]["recursos_hardware"]),
                    "espacios": DEFAULT_CONFIG["pedagogia"]["espacios"]
                }
            }
            safe_save_json(os.path.join(self.base_dir, "pedagogia.json"), default_global)
            print("[OK] Creado archivo 'pedagogia.json' con módulo genérico para uso del sistema.")

    def get_pedagogical_data(
        self,
        mod_code: str,
        mod_data: Dict[str, Any],
        ciclo: str = "",
        idioma: str = "CAS"
    ) -> Dict[str, Any]:
        clean_code = str(mod_code).strip().zfill(4)
        c_upper = ciclo.strip().upper()
        c_lower = ciclo.strip().lower()
        lang_suffix = "val" if str(idioma).upper() in ("VAL", "VALENCIANO", "VALENCIÀ", "CA", "CAT") else "cas"

        raw_ped_data = None
        source_desc = ""

        # Identificadores posibles para el módulo en nombres de archivo
        mod_identifiers = [clean_code]
        alt_num = clean_code.lstrip('0')
        if alt_num and alt_num != clean_code:
            mod_identifiers.append(alt_num)
        siglas = str(mod_data.get("siglas", "")).strip().lower()
        if siglas:
            mod_identifiers.append(siglas)

        # ----------------------------------------------------------------------
        # NIVEL 1: Archivo específico de ciclo y módulo:
        # pedagogia_{ciclo}_{modulo}[_timestamp].json
        # ----------------------------------------------------------------------
        level1_candidates = []
        for mid in mod_identifiers:
            pattern = f"pedagogia_{c_lower}_{mid}*.json"
            for fpath in glob.glob(os.path.join(self.base_dir, pattern)):
                fname = os.path.basename(fpath)
                if re.match(rf'^pedagogia_{re.escape(c_lower)}_{re.escape(mid)}(?:_\d{{8}}_\d{{6}})?\.json$'.replace('{{8}}', '{8}').replace('{{6}}', '{6}'), fname, re.IGNORECASE):
                    level1_candidates.append(fpath)
            for search_dir in [self.base_dir, os.path.join(self.base_dir, "old_jsons")]:
                if not os.path.exists(search_dir):
                    continue
                for fpath in glob.glob(os.path.join(search_dir, pattern)):
                    fname = os.path.basename(fpath)
                    if re.match(rf'^pedagogia_{re.escape(c_lower)}_{re.escape(mid)}(?:_\d{{8}}_\d{{6}}(?:_\d+)?)?\.json$', fname, re.IGNORECASE):
                        level1_candidates.append(fpath)
                if level1_candidates:
                    break
            if level1_candidates:
                break

        if level1_candidates:
            level1_candidates.sort(key=lambda p: (self._extract_timestamp(p), os.path.getmtime(p)), reverse=True)
            chosen_file = level1_candidates[0]
            try:
                with open(chosen_file, "r", encoding="utf-8") as f:
                    file_dict = json.load(f)
                if isinstance(file_dict, dict):
                    if clean_code in file_dict:
                        raw_ped_data = copy.deepcopy(file_dict[clean_code])
                        source_desc = f"Nivel 1: Archivo '{os.path.basename(chosen_file)}' (clave {clean_code})"
                    elif "generico" in file_dict or "genérico" in file_dict:
                        raw_ped_data = copy.deepcopy(file_dict.get("generico") or file_dict.get("genérico"))
                        source_desc = f"Nivel 1: Archivo '{os.path.basename(chosen_file)}' (módulo genérico)"
                    else:
                        raw_ped_data = copy.deepcopy(file_dict)
                        source_desc = f"Nivel 1: Archivo '{os.path.basename(chosen_file)}'"
            except Exception as e:
                print(f"[AVISO] Error al leer '{chosen_file}': {e}", file=sys.stderr)

        # ----------------------------------------------------------------------
        # NIVEL 2: Archivo específico de ciclo (priorizando el archivo del idioma _{cas|val}.json):
        # pedagogia_{ciclo}_{cas|val}.json -> pedagogia_{ciclo}[_timestamp].json
        # ----------------------------------------------------------------------
        if raw_ped_data is None and c_lower:
            c_aliases = [c_lower]
            if c_lower == "iabd":
                c_aliases.append("ia")
            elif c_lower == "ia":
                c_aliases.append("iabd")
            elif c_lower == "smr":
                c_aliases.append("smx")
            elif c_lower == "smx":
                c_aliases.append("smr")

            level2_candidates = []
            # 2.0 Prioridad máxima: archivo traducido del idioma solicitado (pedagogia_<ciclo>_<cas|val>.json)
            for ca in c_aliases:
                lang_file = os.path.join(self.base_dir, f"pedagogia_{ca}_{lang_suffix}.json")
                if os.path.exists(lang_file):
                    level2_candidates.append(lang_file)
                    break

            if not level2_candidates:
                for ca in c_aliases:
                    pattern = f"pedagogia_{ca}*.json"
                    for fpath in glob.glob(os.path.join(self.base_dir, pattern)):
                        fname = os.path.basename(fpath)
                        if re.match(rf'^pedagogia_{re.escape(ca)}(?:_\d{{8}}_\d{{6}})?\.json$'.replace('{{8}}', '{8}').replace('{{6}}', '{6}'), fname, re.IGNORECASE):
                            level2_candidates.append(fpath)
                    for search_dir in [self.base_dir, os.path.join(self.base_dir, "old_jsons")]:
                        if not os.path.exists(search_dir):
                            continue
                        for fpath in glob.glob(os.path.join(search_dir, pattern)):
                            fname = os.path.basename(fpath)
                            if re.match(rf'^pedagogia_{re.escape(ca)}(?:_\d{{8}}_\d{{6}}(?:_\d+)?)?\.json$', fname, re.IGNORECASE):
                                level2_candidates.append(fpath)
                        if level2_candidates:
                            break
                    if level2_candidates:
                        break
                if level2_candidates:
                    level2_candidates.sort(key=lambda p: (self._extract_timestamp(p), os.path.getmtime(p)), reverse=True)

            if level2_candidates:
                chosen_file = level2_candidates[0]
                try:
                    with open(chosen_file, "r", encoding="utf-8") as f:
                        file_dict = json.load(f)
                    if isinstance(file_dict, dict):
                        # 2a. Buscar módulo específico dentro del ciclo
                        if clean_code in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict[clean_code])
                            source_desc = f"Nivel 2: Módulo {clean_code} en '{os.path.basename(chosen_file)}'"
                        elif alt_num and alt_num in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict[alt_num])
                            source_desc = f"Nivel 2: Módulo {alt_num} en '{os.path.basename(chosen_file)}'"
                        # 2b. Buscar módulo genérico dentro del ciclo
                        elif "generico" in file_dict or "genérico" in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict.get("generico") or file_dict.get("genérico"))
                            source_desc = f"Nivel 2: Módulo genérico de ciclo en '{os.path.basename(chosen_file)}'"
                        elif "default" in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict["default"])
                            source_desc = f"Nivel 2: Módulo default de ciclo en '{os.path.basename(chosen_file)}'"
                except Exception as e:
                    print(f"[AVISO] Error al leer '{chosen_file}': {e}", file=sys.stderr)

        # ----------------------------------------------------------------------
        # NIVEL 3: Archivo global:
        # pedagogia[_timestamp].json
        # ----------------------------------------------------------------------
        if raw_ped_data is None:
            level3_candidates = []
            for fpath in glob.glob(os.path.join(self.base_dir, "pedagogia*.json")):
                fname = os.path.basename(fpath)
                if re.match(r'^pedagogia(?:_\d{8}_\d{6})?\.json$', fname, re.IGNORECASE):
                    level3_candidates.append(fpath)
            for search_dir in [self.base_dir, os.path.join(self.base_dir, "old_jsons")]:
                if not os.path.exists(search_dir):
                    continue
                for fpath in glob.glob(os.path.join(search_dir, "pedagogia*.json")):
                    fname = os.path.basename(fpath)
                    if re.match(r'^pedagogia(?:_\d{8}_\d{6}(?:_\d+)?)?\.json$', fname, re.IGNORECASE):
                        level3_candidates.append(fpath)
                if level3_candidates:
                    break

            if level3_candidates:
                level3_candidates.sort(key=lambda p: (self._extract_timestamp(p), os.path.getmtime(p)), reverse=True)
                chosen_file = level3_candidates[0]
                try:
                    with open(chosen_file, "r", encoding="utf-8") as f:
                        file_dict = json.load(f)
                    if isinstance(file_dict, dict):
                        if clean_code in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict[clean_code])
                            source_desc = f"Nivel 3: Módulo {clean_code} en global '{os.path.basename(chosen_file)}'"
                        elif "generico" in file_dict or "genérico" in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict.get("generico") or file_dict.get("genérico"))
                            source_desc = f"Nivel 3: Módulo genérico en global '{os.path.basename(chosen_file)}'"
                        elif "default" in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict["default"])
                            source_desc = f"Nivel 3: Módulo default en global '{os.path.basename(chosen_file)}'"
                        elif "unidades" in file_dict or "ra_ponderaciones" in file_dict:
                            raw_ped_data = copy.deepcopy(file_dict)
                            source_desc = f"Nivel 3: Archivo global '{os.path.basename(chosen_file)}'"
                except Exception as e:
                    print(f"[AVISO] Error al leer '{chosen_file}': {e}", file=sys.stderr)

        # Fallback de conveniencia: pedagogia_modulos.json si sigue existiendo
        if raw_ped_data is None:
            legacy_path = os.path.join(self.base_dir, "pedagogia_modulos.json")
            if os.path.exists(legacy_path):
                try:
                    with open(legacy_path, "r", encoding="utf-8") as f:
                        file_dict = json.load(f)
                    if isinstance(file_dict, dict) and clean_code in file_dict:
                        raw_ped_data = copy.deepcopy(file_dict[clean_code])
                        source_desc = f"Legacy: 'pedagogia_modulos.json' ({clean_code})"
                except Exception:
                    pass

        # Si tras la cascada no se encontró nada, se sintetiza andamiaje genérico dinámico
        if raw_ped_data is None:
            source_desc = "Andamiaje sintetizado dinámicamente"

        # Pasar por PedagogicalSanitizer para asegurar integridad y coherencia con mod_data
        sanitized = PedagogicalSanitizer.sanitize_and_repair(clean_code, raw_ped_data, mod_data, ciclo=c_upper)
        return sanitized


# ==============================================================================
# LOCALIZACIÓN Y TRADUCCIÓN BILINGÜE OFICIAL (VALENCIANO / CASTELLANO)
# ==============================================================================

class LanguageLocalizer:
    """
    Subenlace y motor integral de traducción y adaptación bilingüe oficial
    para Formación Profesional en la Comunitat Valenciana (Valenciano / Castellano).
    Traduce de manera contextual denominaciones de módulos, títulos de ciclos,
    niveles, cursos, meses, trimestres, resultados de aprendizaje, criterios de evaluación,
    competencias, metodologías e instrumentos de evaluación.
    """
    MODULE_MAP = {
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
        "1664": {"CAS": "Digitalización aplicada a los sectores productivos", "VAL": "Digitalització aplicada als sectors productius"},
        "1665": {"CAS": "Desarrollo de aplicaciones de servicios y procesos", "VAL": "Desenvolupament d'aplicacions de serveis i processos"},
        "1708": {"CAS": "Sostenibilidad aplicada al sistema productivo", "VAL": "Sostenibilitat aplicada al sistema productiu"},
        "1801": {"CAS": "Sostenibilidad aplicada a los sectores productivos", "VAL": "Sostenibilitat aplicada als sectors productius"},
        "0369": {"CAS": "Implantación de sistemas operativos", "VAL": "Implantació de sistemes operatius"},
        "0370": {"CAS": "Planificación y administración de redes", "VAL": "Planificació i administració de xarxes"},
        "0371": {"CAS": "Gestión de bases de datos", "VAL": "Gestió de bases de dades"},
        "0372": {"CAS": "Seguridad y alta disponibilidad", "VAL": "Seguretat i alta disponibilitat"},
        "0374": {"CAS": "Administración de sistemas operativos", "VAL": "Administració de sistemes operatius"},
        "0375": {"CAS": "Servicios de red e Internet", "VAL": "Serveis de xarxa i Internet"},
        "0376": {"CAS": "Implantación de aplicaciones web", "VAL": "Implantació d'aplicacions web"},
        "0377": {"CAS": "Administración de sistemas gestores de bases de datos", "VAL": "Administració de sistemes gestors de bases de dades"},
        "0378": {"CAS": "Proyecto de administración de sistemas informáticos en red", "VAL": "Projecte d'administració de sistemes informàtics en xarxa"}
    }

    CYCLE_MAP = {
        "DAM": {
            "CAS": "Ciclo Formativo de Grado Superior en Desarrollo de Aplicaciones Multiplataforma",
            "VAL": "Cicle Formatiu de Grau Superior en Desenvolupament d'Aplicacions Multiplataforma"
        },
        "DAW": {
            "CAS": "Ciclo Formativo de Grado Superior en Desarrollo de Aplicaciones Web",
            "VAL": "Cicle Formatiu de Grau Superior en Desenvolupament d'Aplicacions Web"
        },
        "SMX": {
            "CAS": "Ciclo Formativo de Grado Medio en Sistemas Microinformáticos y Redes",
            "VAL": "Cicle Formatiu de Grau Mitjà en Sistemes Microinformàtics i Xarxes"
        },
        "SMR": {
            "CAS": "Ciclo Formativo de Grado Medio en Sistemas Microinformáticos y Redes",
            "VAL": "Cicle Formatiu de Grau Mitjà en Sistemes Microinformàtics i Xarxes"
        },
        "IABD": {
            "CAS": "Curso de Especialización en Inteligencia Artificial y Big Data",
            "VAL": "Curs d'Especialització en Intel·ligència Artificial i Big Data"
        },
        "IA": {
            "CAS": "Curso de Especialización en Inteligencia Artificial y Big Data",
            "VAL": "Curs d'Especialització en Intel·ligència Artificial i Big Data"
        },
        "ASIR": {
            "CAS": "Ciclo Formativo de Grado Superior en Administración de Sistemas Informáticos en Red",
            "VAL": "Cicle Formatiu de Grau Superior en Administració de Sistemes Informàtics en Xarxa"
        }
    }

    LEVEL_MAP = {
        "Grado Superior": {"CAS": "Grado Superior", "VAL": "Grau Superior"},
        "Grado Medio": {"CAS": "Grado Medio", "VAL": "Grau Mitjà"},
        "Curso de Especialización": {"CAS": "Curso de Especialización", "VAL": "Curs d'Especialització"},
        "Grado Básico": {"CAS": "Grado Básico", "VAL": "Grau Bàsic"}
    }

    MONTH_MAP = {
        "Septiembre": {"CAS": "Septiembre", "VAL": "Setembre"},
        "Octubre": {"CAS": "Octubre", "VAL": "Octubre"},
        "Noviembre": {"CAS": "Noviembre", "VAL": "Novembre"},
        "Diciembre": {"CAS": "Diciembre", "VAL": "Desembre"},
        "Enero": {"CAS": "Enero", "VAL": "Gener"},
        "Febrero": {"CAS": "Febrero", "VAL": "Febrer"},
        "Marzo": {"CAS": "Marzo", "VAL": "Març"},
        "Abril": {"CAS": "Abril", "VAL": "Abril"},
        "Mayo": {"CAS": "Mayo", "VAL": "Maig"},
        "Junio": {"CAS": "Junio", "VAL": "Juny"}
    }

    PHRASES_CAS_TO_VAL = [
        ("Se han reconocido", "S'han reconegut"),
        ("Se ha reconocido", "S'ha reconegut"),
        ("Se han identificado", "S'han identificat"),
        ("Se ha identificado", "S'ha identificat"),
        ("Se han analizado", "S'han analitzat"),
        ("Se ha analizado", "S'ha analitzat"),
        ("Se han clasificado", "S'han classificat"),
        ("Se ha clasificado", "S'ha classificat"),
        ("Se han seleccionado", "S'han seleccionat"),
        ("Se ha seleccionado", "S'ha seleccionat"),
        ("Se han aplicado", "S'han aplicat"),
        ("Se ha aplicado", "S'ha aplicat"),
        ("Se han determinado", "S'han determinat"),
        ("Se ha determinado", "S'ha determinat"),
        ("Se han configurado", "S'han configurat"),
        ("Se ha configurado", "S'ha configurat"),
        ("Se han verificado", "S'han verificat"),
        ("Se ha verificado", "S'ha verificat"),
        ("Se han evaluado", "S'han avaluat"),
        ("Se ha evaluado", "S'ha avaluat"),
        ("Se han elaborado", "S'han elaborat"),
        ("Se ha elaborado", "S'ha elaborat"),
        ("Se han ejecutado", "S'han executat"),
        ("Se ha ejecutado", "S'ha executat"),
        ("Se han establecido", "S'han establit"),
        ("Se ha establecido", "S'ha establit"),
        ("Se han realizado", "S'han realitzat"),
        ("Se ha realizado", "S'ha realitzat"),
        ("Se han utilizado", "S'han utilitzat"),
        ("Se ha utilizado", "S'ha utilitzat"),
        ("Se han empleado", "S'han emprat"),
        ("Se ha empleado", "S'ha emprat"),
        ("Se han definido", "S'han definit"),
        ("Se ha definido", "S'ha definit"),
        ("Se han comprobado", "S'han comprovat"),
        ("Se ha comprobado", "S'ha comprovat"),
        ("Se han documentado", "S'han documentat"),
        ("Se ha documentado", "S'ha documentat"),
        ("Se han integrado", "S'han integrat"),
        ("Se ha integrado", "S'ha integrat"),
        ("Se han diseñado", "S'han dissenyat"),
        ("Se ha diseñado", "S'ha dissenyat"),
        ("Se han implementado", "S'han implementat"),
        ("Se ha implementado", "S'ha implementat"),
        ("Se han creado", "S'han creat"),
        ("Se ha creado", "S'ha creat"),
        ("Se han descrito", "S'han descrit"),
        ("Se ha descrito", "S'ha descrit"),
        ("Se han justificado", "S'han justificat"),
        ("Se ha justificado", "S'ha justificat"),
        ("Se han valorado", "S'han valorat"),
        ("Se ha valorado", "S'ha valorat"),
        ("Se han relacionado", "S'han relacionat"),
        ("Se ha relacionado", "S'ha relacionat"),
        ("Se han gestionado", "S'han gestionat"),
        ("Se ha gestionado", "S'ha gestionat"),
        ("Se han instalado", "S'han instal·lat"),
        ("Se ha instalado", "S'ha instal·lat"),
        ("Se han optimizado", "S'han optimitzat"),
        ("Se ha optimizado", "S'ha optimitzat"),
        ("Se han administrado", "S'han administrat"),
        ("Se ha administrado", "S'ha administrat"),
        ("sistemas informáticos", "sistemes informàtics"),
        ("sistema informático", "sistema informàtic"),
        ("sistemas operativos", "sistemes operatius"),
        ("sistema operativo", "sistema operatiu"),
        ("bases de datos", "bases de dades"),
        ("base de datos", "base de dades"),
        ("entornos de desarrollo", "entorns de desenvolupament"),
        ("entorno de desarrollo", "entorn de desenvolupament"),
        ("dispositivos móviles", "dispositius mòbils"),
        ("dispositivo móvil", "dispositiu mòbil"),
        ("servicios y procesos", "serveis i processos"),
        ("servicios en red", "serveis en xarxa"),
        ("redes locales", "xarxes locals"),
        ("red local", "xarxa local"),
        ("seguridad informática", "seguretat informàtica"),
        ("aplicaciones web", "aplicacions web"),
        ("aplicación web", "aplicació web"),
        ("aprendizaje automático", "aprenentatge automàtic"),
        ("inteligencia artificial", "intel·ligència artificial"),
        ("de los componentes", "dels components"),
        ("de las características", "de les característiques"),
        ("en el conjunto del", "en el conjunt del"),
        ("desarrollan en el", "desenvolupen en el"),
        ("desarrolla en el", "desenvolupa en el"),
        ("de interconexión", "d'interconnexió"),
        ("de memorias", "de memòries"),
        ("de memoria", "de memòria"),
        ("tipos de", "tipus de"),
        ("tipo de", "tipus de"),
        ("sus mecanismos", "els seus mecanismes"),
        ("sus componentes", "els seus components"),
        ("sus características", "les seues característiques"),
        ("sus prestaciones", "les seues prestacions"),
        ("sus elementos", "els seus elements"),
        ("sus funciones", "les seues funcions"),
        ("sus tipos", "els seus tipus"),
        ("sus requisitos", "els seus requisits"),
        ("sus posibilidades", "les seues possibilitats"),
        ("la función que", "la funció que"),
        ("las funciones que", "les funcions que"),
        ("señalando sus", "assenyalant les seues"),
        ("identificando sus", "identificant les seues"),
        ("planificando el proceso", "planificant el procés"),
        ("interpretando documentación", "interpretant documentació"),
        ("documentación técnica", "documentació tècnica"),
        ("elementos funcionales", "elements funcionals"),
        ("elementos físicos", "elements físics"),
        ("a través de", "a través de"),
        ("teniendo en cuenta", "tenint en compte"),
        ("en función de", "en funció de"),
        ("con el fin de", "a fi de"),
        ("de acuerdo con", "d'acord amb"),
        ("así como", "així com"),
        ("al alumnado", "a l'alumnat"),
        ("del alumnado", "de l'alumnat"),
        ("el alumnado", "l'alumnat"),
        ("del módulo", "del mòdul"),
        ("del ciclo", "del cicle"),
        ("al título", "al títol"),
        ("del título", "del títol"),
        ("Prueba de evaluación práctica / proyecto", "Prova d'avaluació pràctica / projecte"),
        ("Prueba de evaluación teórico-conceptual", "Prova d'avaluació teoricoconceptual"),
        ("Pruebas de evaluación teórico-prácticas y proyectos", "Proves d'avaluació teoricopràctiques i projectes"),
        ("Cuestionario técnico conceptual", "Qüestionari tècnic conceptual"),
        ("Proyecto práctico", "Projecte pràctic"),
        ("Todos los CE", "Tots els CE")
    ]

    WORDS_CAS_TO_VAL = {
        "componentes": "components",
        "componente": "component",
        "características": "característiques",
        "característica": "característica",
        "funciones": "funcions",
        "función": "funció",
        "técnica": "tècnica",
        "técnicas": "tècniques",
        "técnico": "tècnic",
        "técnicos": "tècnics",
        "físico": "físic",
        "física": "física",
        "físicos": "físics",
        "físicas": "físiques",
        "lógico": "lògic",
        "lógica": "lògica",
        "lógicos": "lògics",
        "lógicas": "lògiques",
        "básico": "bàsic",
        "básica": "bàsica",
        "básicos": "bàsics",
        "básicas": "bàsiques",
        "específico": "específic",
        "específica": "específica",
        "específicos": "específics",
        "específicas": "específiques",
        "identificando": "identificant",
        "señalando": "assenyalant",
        "analizando": "analitzant",
        "clasificando": "classificant",
        "reconociendo": "reconeixent",
        "desarrollando": "desenvolupant",
        "diseñando": "dissenyant",
        "implementando": "implementant",
        "verificando": "verificant",
        "evaluando": "avaluant",
        "utilizando": "utilitzant",
        "empleando": "emprant",
        "aplicando": "aplicant",
        "instalando": "instal·lant",
        "configurando": "configurant",
        "administrando": "administrant",
        "gestionando": "gestionant",
        "manteniendo": "mantenint",
        "optimizando": "optimitzant",
        "herramientas": "ferramentes",
        "herramienta": "ferramenta",
        "usuarios": "usuaris",
        "usuario": "usuari",
        "requisitos": "requisits",
        "requisito": "requisit",
        "parámetros": "paràmetres",
        "parámetro": "paràmetre",
        "criterios": "criteris",
        "criterio": "criteri",
        "evaluación": "avaluació",
        "calificación": "qualificació",
        "alumnado": "alumnat",
        "profesorado": "professorat",
        "metodología": "metodologia",
        "competencias": "competències",
        "competencia": "competència",
        "contenidos": "continguts",
        "contenido": "contingut",
        "actividades": "activitats",
        "actividad": "activitat",
        "tareas": "tasques",
        "tarea": "tasca",
        "pruebas": "proves",
        "prueba": "prova",
        "proyectos": "projectes",
        "proyecto": "projecte",
        "estrategias": "estratègies",
        "estrategia": "estratègia",
        "lenguajes": "llenguatges",
        "lenguaje": "llenguatge",
        "código": "codi",
        "recursos": "recursos",
        "espacios": "espais",
        "aula": "aula",
        "taller": "taller",
        "laboratorio": "laboratori",
        "trimestre": "trimestre",
        "horas": "hores",
        "créditos": "crèdits",
        "título": "títol",
        "módulo": "mòdul",
        "módulos": "mòduls",
        "ciclo": "cicle",
        "ciclos": "cicles",
        "familia": "família",
        "orientaciones": "orientacions",
        "pedagógicas": "pedagògiques",
        "pedagógica": "pedagògica",
        "profesional": "professional",
        "profesionales": "professionals",
        "laboral": "laboral",
        "laborales": "laborals",
        "didáctica": "didàctica",
        "didácticas": "didàctiques",
        "didáctico": "didàctic",
        "didácticos": "didàctics",
        "académico": "acadèmic",
        "académica": "acadèmica",
        "aplicaciones": "aplicacions",
        "aplicación": "aplicació",
        "limitaciones": "limitacions",
        "limitación": "limitació",
        "ejecución": "execució",
        "ejecuciones": "execucions",
        "entornos": "entorns",
        "entorno": "entorn",
        "configuraciones": "configuracions",
        "configuración": "configuració",
        "perfiles": "perfils",
        "perfil": "perfil",
        "existentes": "existents",
        "existente": "existent",
        "modificaciones": "modificacions",
        "modificación": "modificació",
        "emuladores": "emuladors",
        "emulador": "emulador",
        "funcionamiento": "funcionament",
        "librerías": "llibreries",
        "librería": "llibreria",
        "necesaria": "necessària",
        "necesarias": "necessàries",
        "necesario": "necessari",
        "necesarios": "necessaris",
        "ventanas": "finestres",
        "ventana": "finestra",
        "menús": "menús",
        "menú": "menú",
        "alertas": "alertes",
        "alerta": "alerta",
        "controles": "controls",
        "control": "control",
        "inalámbricos": "sense fils",
        "inalámbrico": "sense fils",
        "conexiones": "connexions",
        "conexión": "connexió",
        "comunicaciones": "comunicacions",
        "comunicación": "comunicació",
        "almacenes": "magatzems",
        "almacén": "magatzem",
        "almacenamiento": "emmagatzematge",
        "empaquetado": "empaquetat",
        "desplegado": "desplegat",
        "desarrolladas": "desenvolupades",
        "desarrollado": "desenvolupat",
        "desarrollados": "desenvolupats",
        "desarrolla": "desenvolupa",
        "permisos": "permisos",
        "requeridos": "requerits",
        "requerido": "requerit",
        "requerida": "requerida",
        "requeridas": "requerides",
        "programas": "programes",
        "programa": "programa",
        "conversión": "conversió",
        "formato": "format",
        "formatos": "formats",
        "creación": "creació",
        "reproducir": "reproduir",
        "juegos": "jocs",
        "juego": "joc",
        "motores": "motors",
        "motor": "motor",
        "objetos": "objectes",
        "objeto": "objecte",
        "escenas": "escenes",
        "escena": "escena",
        "superficie": "superfície",
        "propiedades": "propietats",
        "propiedad": "propietat",
        "iluminación": "il·luminació",
        "diseño": "disseny",
        "duración": "duració",
        "hora": "hora",
        "análisis": "anàlisi",
        "utilización": "utilització",
        "procedimientos": "procediments",
        "procedimiento": "procediment",
        "desarrollo": "desenvolupament",
        "desarrollos": "desenvolupaments",
        "capacidades": "capacitats",
        "capacidad": "capacitat",
        "dispositivos": "dispositius",
        "dispositivo": "dispositiu",
        "elementos": "elements",
        "elemento": "element",
        "clases": "classes",
        "clase": "classe",
        "relación": "relació",
        "relaciones": "relacions",
        "estructura": "estructura",
        "estructuras": "estructures",
        "diferentes": "diferents",
        "diferente": "diferent",
        "bloques": "blocs",
        "bloque": "bloc",
        "gráfica": "gràfica",
        "gráficas": "gràfiques",
        "gráfico": "gràfic",
        "gráficos": "gràfics",
        "representación": "representació",
        "representaciones": "representacions",
        "funcionalidades": "funcionalitats",
        "funcionalidad": "funcionalitat",
        "funcionales": "funcionals",
        "funcional": "funcional",
        "utilizado": "utilitzat",
        "utilizada": "utilitzada",
        "utilizados": "utilitzats",
        "utilizadas": "utilitzades",
        "configurado": "configurat",
        "configurada": "configurada",
        "configurados": "configurats",
        "configuradas": "configurades",
        "instalado": "instal·lat",
        "instalada": "instal·lada",
        "instalados": "instal·lats",
        "instaladas": "instal·lades",
        "clasifican": "classifiquen",
        "establecen": "establixen",
        "plantea": "planteja",
        "trabajo": "treball",
        "trabajos": "treballs",
        "tecnologías": "tecnologies",
        "tecnología": "tecnologia",
        "comprobar": "comprovar",
        "comprobación": "comprovació"
    }

    WORDS_VAL_TO_CAS = {
        "dinàmica": "dinámica",
        "dinàmiques": "dinámicas",
        "oberta": "abierta",
        "obertes": "abiertas",
        "fonaments": "fundamentos",
        "fonament": "fundamento",
        "teòrica": "teórica",
        "teòriques": "teóricas",
        "teòric": "teórico",
        "teòrics": "teóricos",
        "pràctica": "práctica",
        "pràctiques": "prácticas",
        "pràctic": "práctico",
        "pràctics": "prácticos",
        "exposicions": "exposiciones",
        "exposició": "exposición",
        "combinació": "combinación",
        "combinacions": "combinaciones",
        "programari": "software",
        "maquinari": "hardware",
        "introducció": "introducción",
        "màquines": "máquinas",
        "màquina": "máquina",
        "virtuals": "virtuales",
        "virtual": "virtual",
        "gestió": "gestión",
        "administració": "administración",
        "programació": "programación",
        "desenvolupament": "desarrollo",
        "disseny": "diseño",
        "interfícies": "interfaces",
        "interfície": "interfaz",
        "xarxes": "redes",
        "xarxa": "red",
        "seguretat": "seguridad",
        "serveis": "servicios",
        "servei": "servicio",
        "processos": "procesos",
        "procés": "proceso",
        "sistemes": "sistemas",
        "sistema": "sistema",
        "operatius": "operativos",
        "operatiu": "operativo",
        "monolloc": "monopuesto",
        "ofimàtiques": "ofimáticas",
        "ofimàtica": "ofimática",
        "emprenedora": "emprendedora",
        "emprenedor": "emprendedor",
        "centres": "centros",
        "centre": "centro",
        "treball": "trabajo",
        "intel·ligència": "inteligencia",
        "automàtic": "automático",
        "automàtica": "automática",
        "aplicat": "aplicado",
        "aplicada": "aplicada",
        "aplicats": "aplicados",
        "aplicades": "aplicadas",
        "dades": "datos",
        "marques": "marcas",
        "informació": "información",
        "entorns": "entornos",
        "entorn": "entorno",
        "multimèdia": "multimedia",
        "mòbils": "móviles",
        "mòbil": "móvil",
        "muntatge": "montaje",
        "manteniment": "mantenimiento",
        "equips": "equipos",
        "equip": "equipo",
        "qualificació": "calificación",
        "avaluació": "evaluación",
        "criteris": "criterios",
        "criteri": "criterio",
        "ponderació": "ponderación",
        "continguts": "contenidos",
        "contingut": "contenido",
        "competències": "competencias",
        "competència": "competencia",
        "alumnat": "alumnado",
        "professorat": "profesorado",
        "activitats": "actividades",
        "activitat": "actividad",
        "tasques": "tareas",
        "tasca": "tarea",
        "proves": "pruebas",
        "prova": "prueba",
        "projectes": "proyectos",
        "projecte": "proyecto",
        "ferramentes": "herramientas",
        "ferramenta": "herramienta",
        "recursos": "recursos",
        "espais": "espacios",
        "aula": "aula",
        "laboratori": "laboratorio"
    }

    VERBS_RA_CAS_TO_VAL = {
        "Evalúa": "Avalua",
        "Evalua": "Avalua",
        "Instala": "Instal·la",
        "Configura": "Configura",
        "Administra": "Administra",
        "Gestiona": "Gestiona",
        "Desarrolla": "Desenvolupa",
        "Diseña": "Dissenya",
        "Implementa": "Implementa",
        "Verifica": "Verifica",
        "Reconoce": "Reconeix",
        "Identifica": "Identifica",
        "Clasifica": "Classifica",
        "Selecciona": "Selecciona",
        "Aplica": "Aplica",
        "Determina": "Determina",
        "Elabora": "Elabora",
        "Ejecuta": "Executa",
        "Establece": "Establix",
        "Realiza": "Realitza",
        "Utiliza": "Utilitza",
        "Emplea": "Empra",
        "Define": "Definix",
        "Comprueba": "Comprova",
        "Documenta": "Documenta",
        "Integra": "Integra",
        "Optimiza": "Optimitza",
        "Planifica": "Planifica"
    }

    CONNECTORS_CAS_TO_VAL = [
        (" y ", " i "),
        (" e ", " i "),
        (" con ", " amb "),
        (" para ", " per a "),
        (" según ", " segons "),
        (" mediante ", " mitjançant "),
        (" durante ", " durant "),
        (" de los ", " dels "),
        (" de las ", " de les "),
        (" a los ", " als "),
        (" a las ", " a les "),
        (" en los ", " en els "),
        (" en las ", " en les "),
        (" los ", " els "),
        (" las ", " les "),
        (" sus ", " els seus "),
        (" estos ", " estos "),
        (" estas ", " estes "),
        (" este ", " este "),
        (" esta ", " esta ")
    ]

    CONNECTORS_VAL_TO_CAS = [
        (" i ", " y "),
        (" amb ", " con "),
        (" per a ", " para "),
        (" segons ", " según "),
        (" mitjançant ", " mediante "),
        (" durant ", " durante "),
        (" dels ", " de los "),
        (" de les ", " de las "),
        (" als ", " a los "),
        (" a les ", " a las "),
        (" en els ", " en los "),
        (" en les ", " en las "),
        (" els ", " los "),
        (" les ", " las ")
    ]

    @classmethod
    def translate_to_valencian(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        res = text

        # 1. Phrases
        for p_src, p_dst in cls.PHRASES_CAS_TO_VAL:
            res = re.sub(r'(?i)\b' + re.escape(p_src) + r'\b', p_dst, res)

        # 2. RA initial verbs
        for v_src, v_dst in cls.VERBS_RA_CAS_TO_VAL.items():
            res = re.sub(r'(?m)^\s*' + re.escape(v_src) + r'\b', v_dst, res)

        # 3. Words
        for w_src, w_dst in cls.WORDS_CAS_TO_VAL.items():
            res = re.sub(r'(?i)\b' + re.escape(w_src) + r'\b', w_dst, res)

        # 4. Connectors
        for c_src, c_dst in cls.CONNECTORS_CAS_TO_VAL:
            res = re.sub(re.escape(c_src), c_dst, res, flags=re.IGNORECASE)

        # 5. Elisions
        res = re.sub(r'\bde ([aeiouhAEIOUHàèéíòóúÀÈÉÍÒÓÚ])', r"d'\1", res)
        res = re.sub(r'\bDe ([aeiouhAEIOUHàèéíòóúÀÈÉÍÒÓÚ])', r"D'\1", res)
        res = re.sub(r'\bel ([aeiouhAEIOUHàèéíòóúÀÈÉÍÒÓÚ])', r"l'\1", res)
        res = re.sub(r'\bEl ([aeiouhAEIOUHàèéíòóúÀÈÉÍÒÓÚ])', r"L'\1", res)
        res = re.sub(r'\bse ([aeiouhAEIOUHàèéíòóúÀÈÉÍÒÓÚ])', r"s'\1", res)
        res = re.sub(r'\bSe ([aeiouhAEIOUHàèéíòóúÀÈÉÍÒÓÚ])', r"S'\1", res)

        return res

    @classmethod
    def translate_to_spanish(cls, text: str) -> str:
        if not text or not isinstance(text, str):
            return text
        res = text
        # Invert phrases
        for p_cas, p_val in cls.PHRASES_CAS_TO_VAL:
            res = re.sub(r'(?i)\b' + re.escape(p_val) + r'\b', p_cas, res)
        for v_cas, v_val in cls.VERBS_RA_CAS_TO_VAL.items():
            res = re.sub(r'(?m)^\s*' + re.escape(v_val) + r'\b', v_cas, res)
        for w_val, w_cas in cls.WORDS_VAL_TO_CAS.items():
            res = re.sub(r'(?i)\b' + re.escape(w_val) + r'\b', w_cas, res)
        for w_cas, w_val in cls.WORDS_CAS_TO_VAL.items():
            res = re.sub(r'(?i)\b' + re.escape(w_val) + r'\b', w_cas, res)
        for c_val, c_cas in cls.CONNECTORS_VAL_TO_CAS:
            res = re.sub(re.escape(c_val), c_cas, res, flags=re.IGNORECASE)
        # Invert elisions
        res = re.sub(r"\bd'([aeiouhAEIOUH])", r"de \1", res, flags=re.IGNORECASE)
        res = re.sub(r"\bl'([aeiouhAEIOUH])", r"el \1", res, flags=re.IGNORECASE)
        res = re.sub(r"\bs'([aeiouhAEIOUH])", r"se \1", res, flags=re.IGNORECASE)
        return res

    @classmethod
    def localize_text(cls, text: str, to_lang: str) -> str:
        if not text:
            return ""
        return text

    @classmethod
    def localize_module_name(cls, name: str, code: str = "", to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        clean_code = str(code).zfill(4) if code else ""
        if clean_code in cls.MODULE_MAP:
            return cls.MODULE_MAP[clean_code][tag]
        for c, names in cls.MODULE_MAP.items():
            if names["CAS"].lower() == name.lower() or names["VAL"].lower() == name.lower():
                return names[tag]
        return cls.localize_text(name, tag)

    @classmethod
    def localize_cycle_title(cls, title: str, cycle_code: str = "", to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        c_up = str(cycle_code).upper()
        if c_up in cls.CYCLE_MAP:
            return cls.CYCLE_MAP[c_up][tag]
        return cls.localize_text(title, tag)

    @classmethod
    def localize_level(cls, level: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        for k, v in cls.LEVEL_MAP.items():
            if k.lower() in level.lower() or v["VAL"].lower() in level.lower():
                return v[tag]
        return cls.localize_text(level, tag)

    @classmethod
    def localize_course(cls, course_str: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        c_digits = re.findall(r'\d', str(course_str))
        num = c_digits[0] if c_digits else "1"
        if tag == "VAL":
            return f"{num}r" if num == "1" else f"{num}n"
        else:
            return f"{num}º"

    @classmethod
    def localize_trimestre(cls, trim_str: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        c_digits = re.findall(r'\d', str(trim_str))
        num = c_digits[0] if c_digits else "1"
        if tag == "VAL":
            suffix = "r" if num in ("1", "3") else "n"
            return f"{num}{suffix} Trimestre"
        else:
            suffix = "er" if num in ("1", "3") else "º"
            return f"{num}{suffix} Trimestre"

    @classmethod
    def localize_month(cls, month_str: str, to_lang: str = "CAS") -> str:
        if not month_str:
            return ""
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        for m_cas, data in cls.MONTH_MAP.items():
            if m_cas.lower() == month_str.lower() or data["VAL"].lower() == month_str.lower():
                return data[tag]
        return month_str

    @classmethod
    def localize_spaces(cls, spaces_str: str, to_lang: str = "CAS") -> str:
        if not spaces_str:
            return ""
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            res = spaces_str.replace("Aula polivalente", "Aula polivalent")
            res = res.replace("Laboratorio de informática", "Laboratori d'informàtica")
            res = res.replace("Taller de montaje", "Taller de muntatge")
            return res
        else:
            res = spaces_str.replace("Aula polivalent", "Aula polivalente")
            res = res.replace("Laboratori d'informàtica", "Laboratorio de informática")
            res = res.replace("Taller de muntatge", "Taller de montaje")
            return res

    @classmethod
    def localize_instrument_name(cls, name: str, to_lang: str = "CAS") -> str:
        if not name:
            return ""
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        return cls.localize_text(name, tag)

    @classmethod
    def localize_familia(cls, fam: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            return fam.replace("Informática y Comunicaciones", "Informàtica i Comunicacions")
        else:
            return fam.replace("Informàtica i Comunicacions", "Informática y Comunicaciones")

    @classmethod
    def localize_profesor(cls, profesor: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            return profesor.replace("Profesorado del Departamento de Informática", "Professorat del Departament d'Informàtica")
        else:
            return profesor.replace("Professorat del Departament d'Informàtica", "Profesorado del Departamento de Informática")

    @classmethod
    def localize_acreditacion(cls, text: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            res = text.replace(
                "Módulo profesional de carácter complementario / transversal; no acredita directamente Unidades de Competencia del Catálogo Nacional (CNCP).",
                "Mòdul professional de caràcter complementari / transversal; no acredita directament Unitats de Competència del Catàleg Nacional (CNCP)."
            )
            return cls.localize_text(res, tag)
        else:
            res = text.replace(
                "Mòdul professional de caràcter complementari / transversal; no acredita directament Unitats de Competència del Catàleg Nacional (CNCP).",
                "Módulo profesional de carácter complementario / transversal; no acredita directamente Unidades de Competencia del Catálogo Nacional (CNCP)."
            )
            return cls.localize_text(res, tag)

    @classmethod
    def localize_sin_uc_label(cls, text: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            return "Sense acreditació directa d'Unitats de Competència"
        return "Sin acreditación directa de Unidades de Competencia"

    @classmethod
    def localize_sin_ifc_label(cls, text: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            return "Mòdul formatiu transversal / complementari"
        return "Módulo formativo transversal / complementario"

    @classmethod
    def localize_cualif_default(cls, text: str, to_lang: str = "CAS") -> str:
        tag = "VAL" if str(to_lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            return "Qualificació de referència del Catàleg Nacional"
        return "Cualificación de referencia del Catálogo Nacional"



class FodtTemplateEngine:
    """
    Carga la plantilla oficial en formato Flat XML ODF (plantilla.fodt),
    normaliza automáticamente etiquetas fragmentadas por LibreOffice Writer,
    clona dinámicamente las filas de las tablas predefinidas rellenando los datos curriculares/pedagógicos
    y exporta el archivo OpenDocument final (.odt).
    """
    def __init__(self, template_path: str = "plantilla.fodt"):
        self.template_path = template_path
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Plantilla no encontrada: '{template_path}'")

    def _get_template_for_language(self, idioma: str) -> str:
        tag = "VAL" if str(idioma).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        if tag == "VAL":
            if "_val.fodt" in self.template_path.lower():
                return self.template_path
            dirname = os.path.dirname(self.template_path)
            basename = os.path.basename(self.template_path)
            candidate = os.path.join(dirname, basename.replace(".fodt", "_val.fodt")) if dirname else basename.replace(".fodt", "_val.fodt")
            if os.path.exists(candidate):
                return candidate
            candidate_val = os.path.join(dirname, "plantilla_val.fodt") if dirname else "plantilla_val.fodt"
            if os.path.exists(candidate_val):
                return candidate_val
            return self.template_path
        else:
            if "_val.fodt" in self.template_path.lower():
                candidate = self.template_path.replace("_val.fodt", ".fodt")
                if os.path.exists(candidate):
                    return candidate
            return self.template_path

    @staticmethod
    def _normalize_xml_placeholders(xml_str: str) -> str:
        """
        Limpia etiquetas XML internas generadas por LibreOffice Writer dentro de los placeholders.
        Por ejemplo: '{{<text:span text:style-name="T1">nombre_</text:span>modulo}}' -> '{{nombre_modulo}}'
        """
        return re.sub(
            r'\{\{([^{}]+)\}\}',
            lambda m: '{{' + re.sub(r'<[^>]+>', '', m.group(1)).strip() + '}}',
            xml_str
        )

    def render_and_save(
        self,
        output_odt_path: str,
        mod_data: Dict[str, Any],
        cycle_data: Dict[str, Any],
        ped_info: Dict[str, Any],
        context_meta: Optional[Dict[str, Any]] = None,
        idioma: str = "CAS"
    ):
        tag = "VAL" if str(idioma).upper() in ("VAL", "VALENCIANO", "VALENCIÀ") else "CAS"
        context_meta = context_meta or {}
        meta_defaults = DEFAULT_CONFIG["metadata"]
        acred_defaults = DEFAULT_CONFIG["acreditacion"]
        ped_defaults = DEFAULT_CONFIG["pedagogia"]

        ns_map = {
            'office': 'urn:oasis:names:tc:opendocument:xmlns:office:1.0',
            'style': 'urn:oasis:names:tc:opendocument:xmlns:style:1.0',
            'text': 'urn:oasis:names:tc:opendocument:xmlns:text:1.0',
            'table': 'urn:oasis:names:tc:opendocument:xmlns:table:1.0',
            'draw': 'urn:oasis:names:tc:opendocument:xmlns:drawing:1.0',
            'fo': 'urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0',
            'svg': 'urn:oasis:names:tc:opendocument:xmlns:svg-compatible:1.0',
            'xlink': 'http://www.w3.org/1999/xlink',
            'meta': 'urn:oasis:names:tc:opendocument:xmlns:meta:1.0',
            'dc': 'http://purl.org/dc/elements/1.1/',
        }
        for prefix, uri in ns_map.items():
            ET.register_namespace(prefix, uri)

        chosen_template = self._get_template_for_language(tag)
        with open(chosen_template, "r", encoding="utf-8") as f:
            raw_template = f.read()

        normalized_template = self._normalize_xml_placeholders(raw_template)
        root = ET.fromstring(normalized_template)
        body = root.find('.//office:body/office:text', ns_map)

        mod_code = str(mod_data.get("codigo", "")).zfill(4)
        raw_mod_name = str(mod_data.get("nombre", ""))
        mod_name = LanguageLocalizer.localize_module_name(raw_mod_name, code=mod_code, to_lang=tag)

        ciclo_code = context_meta.get("ciclo", cycle_data.get("ciclo", "")).upper()
        raw_ciclo_title = cycle_data.get("titulo", f"Ciclo Formativo {ciclo_code}")
        ciclo_title = LanguageLocalizer.localize_cycle_title(raw_ciclo_title, cycle_code=ciclo_code, to_lang=tag)

        raw_familia = cycle_data.get("familia_profesional", meta_defaults["familia_profesional"])
        familia = LanguageLocalizer.localize_familia(raw_familia, to_lang=tag)

        raw_curso = str(mod_data.get("curso_orientativo", meta_defaults["curso_orientativo"]))
        curso = LanguageLocalizer.localize_course(raw_curso, to_lang=tag)

        ects = str(mod_data.get("creditos_ects", meta_defaults["creditos_ects"]))

        raw_profesor = context_meta.get("profesor", meta_defaults["profesor"])
        profesor = LanguageLocalizer.localize_profesor(raw_profesor, to_lang=tag)

        centro = context_meta.get("centro", meta_defaults["centro"])
        curso_acad = context_meta.get("curso_academico", meta_defaults["curso_academico"])

        raw_normativa = cycle_data.get("normativa_referencia", meta_defaults["normativa_referencia"])
        normativa = LanguageLocalizer.localize_text(raw_normativa, to_lang=tag)

        raw_nivel = cycle_data.get("nivel", meta_defaults["nivel"])
        nivel = LanguageLocalizer.localize_level(raw_nivel, to_lang=tag)

        codigo_ciclo = str(cycle_data.get("codigo_ciclo", "")).strip()
        horas = str(mod_data.get("horas", "")).strip()

        raw_orientaciones = str(mod_data.get("orientaciones_pedagogicas", "")).strip()
        orientaciones = LanguageLocalizer.localize_text(raw_orientaciones, to_lang=tag) if raw_orientaciones else ""

        ras = mod_data.get("resultados_aprendizaje", [])
        mod_ucs = mod_data.get("unidades_competencia", [])
        all_ucs = cycle_data.get("unidades_competencia", {})
        cualif_list = cycle_data.get("cualificaciones_profesionales", [])
        all_comps = cycle_data.get("competencias_profesionales_personales_sociales", {})
        mod_comps = mod_data.get("competencias_titulo", [])

        if mod_ucs:
            acred_list = []
            for uc in mod_ucs:
                desc = all_ucs.get(uc, "")
                desc_loc = LanguageLocalizer.localize_text(desc, to_lang=tag) if desc else ""
                acred_list.append(f"{uc} ({desc_loc})" if desc_loc else uc)
            acreditacion_text = "; ".join(acred_list) + "."
        else:
            acreditacion_text = LanguageLocalizer.localize_acreditacion(acred_defaults["sin_uc_text"], to_lang=tag)

        # --- 1. CLONAR FILAS DE TABLA 3: UNIDADES DE COMPETENCIA (Table_36848684) ---
        t_ucs = self._find_table(body, 'Table_36848684', ns_map)
        if t_ucs is not None:
            rows = t_ucs.findall('.//table:table-row', ns_map)
            if len(rows) > 1:
                tmpl_row = rows[1]
                t_ucs.remove(tmpl_row)
                if mod_ucs:
                    for uc in mod_ucs:
                        uc_desc = all_ucs.get(uc, "")
                        uc_desc_loc = LanguageLocalizer.localize_text(uc_desc, to_lang=tag) if uc_desc else ""
                        cualifs = [f"{c.get('codigo')}: {LanguageLocalizer.localize_text(c.get('denominacion', ''), to_lang=tag)}" for c in cualif_list if uc in c.get('unidades_competencia', [])]
                        cualif_str = " / ".join(cualifs) if cualifs else LanguageLocalizer.localize_cualif_default(acred_defaults["cualif_default"], to_lang=tag)
                        new_r = copy.deepcopy(tmpl_row)
                        self._replace_in_element(new_r, {
                            "{{uc}}": f"{uc}: {uc_desc_loc}" if uc_desc_loc else uc,
                            "{{ifc}}": cualif_str
                        })
                        t_ucs.append(new_r)
                else:
                    new_r = copy.deepcopy(tmpl_row)
                    self._replace_in_element(new_r, {
                        "{{uc}}": LanguageLocalizer.localize_sin_uc_label(acred_defaults["sin_uc_label"], to_lang=tag),
                        "{{ifc}}": LanguageLocalizer.localize_sin_ifc_label(acred_defaults["sin_ifc_label"], to_lang=tag)
                    })
                    t_ucs.append(new_r)

        # --- 2. REPETIR PÁRRAFOS DE COMPETENCIAS DEL TÍTULO (3.1) ---
        p_comp_tmpl = None
        for p in body.findall('.//text:p', ns_map):
            if "{{letra_competencia}}" in "".join(p.itertext()):
                p_comp_tmpl = p
                break
        if p_comp_tmpl is not None:
            parent = body
            idx_p = list(parent).index(p_comp_tmpl)
            parent.remove(p_comp_tmpl)
            insert_idx = idx_p
            comps_to_show = mod_comps if mod_comps else list(all_comps.keys())[:3]
            for letra in comps_to_show:
                raw_desc = all_comps.get(letra, ped_defaults["competencia_desc_default"])
                desc = LanguageLocalizer.localize_text(raw_desc, to_lang=tag)
                new_p = copy.deepcopy(p_comp_tmpl)
                new_p.text = f"{letra}) {desc}"
                for sub in list(new_p): new_p.remove(sub)
                parent.insert(insert_idx, new_p)
                insert_idx += 1

        # --- 2b. EXPANDIR RESULTADOS DE APRENDIZAJE Y CRITERIOS DE EVALUACIÓN (2.3) ---
        p_ra_ce_tmpl = None
        for p in body.findall('.//text:p', ns_map):
            if "{{ra_ce_list}}" in "".join(p.itertext()):
                p_ra_ce_tmpl = p
                break

        if p_ra_ce_tmpl is not None:
            ra_style = p_ra_ce_tmpl.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name', 'P46')
            auto_styles_el = root.find('.//office:automatic-styles', ns_map)
            if auto_styles_el is not None:
                has_sub = any(
                    s.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name') == 'P_SubItem'
                    for s in auto_styles_el.findall('style:style', ns_map)
                )
                if not has_sub:
                    sub_s = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:style:1.0}style', {
                        '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name': 'P_SubItem',
                        '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}family': 'paragraph',
                        '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}parent-style-name': 'Standard'
                    })
                    ET.SubElement(sub_s, '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}paragraph-properties', {
                        '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}margin-left': '1.1cm',
                        '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}margin-top': '0.02cm',
                        '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}margin-bottom': '0.08cm',
                        '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}contextual-spacing': 'false',
                        '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}text-indent': '-0.35cm',
                        '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}auto-text-indent': 'false'
                    })
                    ET.SubElement(sub_s, '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}text-properties', {
                        '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}color': '#172033',
                        '{urn:oasis:names:tc:opendocument:xmlns:style:1.0}font-name': 'Segoe UI1',
                        '{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}font-size': '9.8pt'
                    })
                    auto_styles_el.append(sub_s)

            parent = body
            idx_p = list(parent).index(p_ra_ce_tmpl)
            parent.remove(p_ra_ce_tmpl)
            insert_idx = idx_p

            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                r_desc = LanguageLocalizer.localize_text(ra.get("descripcion", "").strip(), to_lang=tag)

                # Nivel 1: • RA1. Título oficial del RA1
                p_ra = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p', {
                    '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': ra_style
                })
                p_ra.text = "• "
                span_ra = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}span', {
                    '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': 'Strong_20_Emphasis'
                })
                span_ra.text = f"RA{r_num}. "
                span_ra.tail = r_desc
                p_ra.append(span_ra)
                parent.insert(insert_idx, p_ra)
                insert_idx += 1

                # Nivel 2: • RA1.a. Criterio de evaluación...
                ces = ra.get("criterios_evaluacion", [])
                for ce in ces:
                    ce_cod = ce.get("codigo", f"RA{r_num}.{ce.get('letra', '')}")
                    ce_desc = LanguageLocalizer.localize_text(ce.get("descripcion", "").strip(), to_lang=tag)
                    p_ce = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p', {
                        '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': 'P_SubItem'
                    })
                    p_ce.text = "• "
                    span_ce = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}span', {
                        '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': 'Strong_20_Emphasis'
                    })
                    span_ce.text = f"{ce_cod}. "
                    span_ce.tail = ce_desc
                    p_ce.append(span_ce)
                    parent.insert(insert_idx, p_ce)
                    insert_idx += 1

        # --- 2c. EXPANDIR CONTENIDOS ASOCIADOS A LOS RAs (2.4) ---
        p_cont_tmpl = None
        for p in body.findall('.//text:p', ns_map):
            if "{{ra_contenidos_list}}" in "".join(p.itertext()):
                p_cont_tmpl = p
                break

        if p_cont_tmpl is not None:
            cont_style = p_cont_tmpl.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name', 'P46')
            parent = body
            idx_p = list(parent).index(p_cont_tmpl)
            parent.remove(p_cont_tmpl)
            insert_idx = idx_p

            contenidos_data = mod_data.get("contenidos", [])
            c_counter = 1

            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                r_desc = LanguageLocalizer.localize_text(ra.get("descripcion", "").strip(), to_lang=tag)

                # Buscar bloque correspondiente
                matched_block = None
                if contenidos_data:
                    for b in contenidos_data:
                        if b.get("ra") == r_num or b.get("codigo_ra") == f"RA{r_num}":
                            matched_block = b
                            break
                    if not matched_block and idx - 1 < len(contenidos_data):
                        matched_block = contenidos_data[idx - 1]

                if matched_block:
                    raw_b_title = matched_block.get("titulo", f"Contenidos del RA{r_num}").strip()
                    b_title = LanguageLocalizer.localize_text(raw_b_title, to_lang=tag)
                    items = matched_block.get("items", [])
                else:
                    ra_cont = ra.get("contenidos", {})
                    raw_b_title = ra_cont.get("titulo", r_desc).strip()
                    b_title = LanguageLocalizer.localize_text(raw_b_title, to_lang=tag)
                    items = ra_cont.get("items", [])

                if not items:
                    fallback_item = f"Continguts i procediments associats a: {r_desc}" if tag == "VAL" else f"Contenidos y procedimientos asociados a: {r_desc}"
                    items = [fallback_item]

                # Nivel 1: • RA1 — [título]
                p_ra_c = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p', {
                    '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': cont_style
                })
                p_ra_c.text = "• "
                span_ra_c = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}span', {
                    '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': 'Strong_20_Emphasis'
                })
                span_ra_c.text = f"RA{r_num} — "
                span_ra_c.tail = b_title
                p_ra_c.append(span_ra_c)
                parent.insert(insert_idx, p_ra_c)
                insert_idx += 1

                # Nivel 2: • C1. ...
                for item in items:
                    clean_item = item.strip()
                    if not clean_item:
                        continue
                    clean_item_loc = LanguageLocalizer.localize_text(clean_item, to_lang=tag)
                    p_item = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p', {
                        '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': 'P_SubItem'
                    })
                    p_item.text = "• "
                    span_item = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}span', {
                        '{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name': 'Strong_20_Emphasis'
                    })
                    span_item.text = f"C{c_counter}. "
                    span_item.tail = clean_item_loc
                    p_item.append(span_item)
                    parent.insert(insert_idx, p_item)
                    insert_idx += 1
                    c_counter += 1

        # --- 3. CLONAR FILAS DE TABLA 4: RAs Y COMPETENCIAS VINCULADAS (Table_49111049) ---
        t_ra_comp = self._find_table(body, 'Table_49111049', ns_map)
        if t_ra_comp is not None:
            rows = t_ra_comp.findall('.//table:table-row', ns_map)
            if len(rows) > 1:
                tmpl_row = rows[1]
                t_ra_comp.remove(tmpl_row)
                for idx, ra in enumerate(ras, start=1):
                    r_num = ra.get("numero", idx)
                    r_desc = LanguageLocalizer.localize_text(ra.get("descripcion", ""), to_lang=tag)
                    if mod_comps:
                        offset = (idx - 1) % len(mod_comps)
                        c_assigned = [mod_comps[offset], mod_comps[(offset + 1) % len(mod_comps)]]
                        if len(mod_comps) >= 4 and idx % 2 == 0:
                            c_assigned.append(mod_comps[(offset + 2) % len(mod_comps)])
                    else:
                        c_assigned = list(all_comps.keys())[:2]
                    comps_str = ", ".join([f"{c}" for c in sorted(list(set(c_assigned)))])
                    new_r = copy.deepcopy(tmpl_row)
                    self._replace_in_element(new_r, {
                        "{{ra}}": f"RA{r_num}: {r_desc}",
                        "{{competencias}}": comps_str
                    })
                    t_ra_comp.append(new_r)

        # --- 4. CLONAR FILAS DE TABLA 5: SECUENCIACIÓN DE RAs / UNIDADES (Tabla1) ---
        t_units = self._find_table(body, 'Tabla1', ns_map)
        if t_units is not None:
            rows = t_units.findall('.//table:table-row', ns_map)
            if len(rows) > 1:
                tmpl_row = rows[1]
                t_units.remove(tmpl_row)

                tmpl_text = "".join(tmpl_row.itertext())
                tmpl_xml = ET.tostring(tmpl_row, encoding='utf-8').decode('utf-8')
                is_ra_sequencing = ('{{ra}}' in tmpl_text or '{{ra_num}}' in tmpl_text or '{{ra}}' in tmpl_xml) and '{{UP}}' not in tmpl_text

                if is_ra_sequencing:
                    total_mod_hours = int(mod_data.get("horas") or 0)
                    if total_mod_hours == 0:
                        total_mod_hours = int(mod_data.get("creditos_ects", 8) * 25)
                    num_ras = len(ras)
                    units_data = ped_info.get("unidades", [])
                    ra_weights = ped_info.get("ra_ponderaciones", {})

                    for idx, ra in enumerate(ras, start=1):
                        r_num = ra.get("numero", idx)
                        r_code = ra.get("codigo") or f"RA{r_num}"
                        r_desc = LanguageLocalizer.localize_text(ra.get("descripcion", "").strip(), to_lang=tag)

                        # Buscar unidades asociadas a este RA
                        matching_units = []
                        for u in units_data:
                            u_ras = u.get("ras", [])
                            if isinstance(u_ras, (int, str)):
                                u_ras = [u_ras]
                            if r_num in u_ras or str(r_num) in [str(x) for x in u_ras]:
                                matching_units.append(u)

                        if matching_units:
                            ra_hours = 0.0
                            trims = []
                            inicios = []
                            fines = []
                            for u in matching_units:
                                u_h = float(u.get("horas") or 0)
                                u_ras_list = u.get("ras") or [r_num]
                                n_shared = len(u_ras_list) if isinstance(u_ras_list, list) and len(u_ras_list) > 0 else 1
                                ra_hours += u_h / n_shared

                                t = str(u.get("trimestre", "")).strip()
                                if t and t not in trims:
                                    trims.append(t)
                                ini = str(u.get("inicio", "")).strip()
                                if ini and ini not in inicios:
                                    inicios.append(ini)
                                fn = str(u.get("fin", "")).strip()
                                if fn and fn not in fines:
                                    fines.append(fn)

                            dur_str = f"{int(round(ra_hours))} h" if ra_hours > 0 else ""
                            trim_str = " - ".join([LanguageLocalizer.localize_trimestre(t, to_lang=tag) for t in trims]) if trims else ""
                            ini_str = LanguageLocalizer.localize_month(inicios[0], to_lang=tag) if inicios else ""
                            fin_str = LanguageLocalizer.localize_month(fines[-1], to_lang=tag) if fines else ""
                        else:
                            # Fallback proporcional si no hay unidades específicas
                            if str(r_num) in ra_weights:
                                w = float(ra_weights[str(r_num)])
                                ra_h = round(total_mod_hours * (w / 100.0))
                            else:
                                ra_h = round(total_mod_hours / max(1, num_ras))

                            dur_str = f"{int(ra_h)} h" if ra_h > 0 else ""
                            if idx <= max(1, (num_ras + 2) // 3):
                                trim_str = LanguageLocalizer.localize_trimestre("1er Trimestre", to_lang=tag)
                                ini_str = LanguageLocalizer.localize_month("Septiembre", to_lang=tag)
                                fin_str = LanguageLocalizer.localize_month("Diciembre", to_lang=tag)
                            elif idx <= max(2, (2 * num_ras + 1) // 3):
                                trim_str = LanguageLocalizer.localize_trimestre("2º Trimestre", to_lang=tag)
                                ini_str = LanguageLocalizer.localize_month("Enero", to_lang=tag)
                                fin_str = LanguageLocalizer.localize_month("Marzo", to_lang=tag)
                            else:
                                trim_str = LanguageLocalizer.localize_trimestre("3er Trimestre", to_lang=tag)
                                ini_str = LanguageLocalizer.localize_month("Abril", to_lang=tag)
                                fin_str = LanguageLocalizer.localize_month("Junio", to_lang=tag)

                        new_r = copy.deepcopy(tmpl_row)
                        ra_full_text = f"{r_code}: {r_desc}" if r_desc else r_code
                        self._replace_in_element(new_r, {
                            "{{ra}}": ra_full_text,
                            "{{ra_completo}}": ra_full_text,
                            "{{ra_num}}": r_code,
                            "{{ra_codigo}}": r_code,
                            "{{ra_descripcion}}": r_desc,
                            "{{duracion}}": dur_str,
                            "{{trimestre}}": trim_str,
                            "{{inicio}}": ini_str,
                            "{{fin}}": fin_str
                        })
                        t_units.append(new_r)
                else:
                    units_data = ped_info.get("unidades", [])
                    for u in units_data:
                        u_code = u.get("codigo", "")
                        raw_u_name = u.get("nombre", "")
                        u_name = LanguageLocalizer.localize_text(raw_u_name, to_lang=tag)
                        u_title = f"{u_code}: {u_name}" if u_code else u_name
                        u_ras = ", ".join([f"RA{r}" for r in u.get("ras", [])])
                        u_hours = f"{u.get('horas', '')} h" if u.get('horas') else ""
                        u_trim = LanguageLocalizer.localize_trimestre(str(u.get("trimestre", "")), to_lang=tag)
                        u_ini = LanguageLocalizer.localize_month(str(u.get("inicio", "")), to_lang=tag) if u.get("inicio") else ""
                        u_fin = LanguageLocalizer.localize_month(str(u.get("fin", "")), to_lang=tag) if u.get("fin") else ""

                        new_r = copy.deepcopy(tmpl_row)
                        self._replace_in_element(new_r, {
                            "{{UP}}": u_title,
                            "{{ras}}": u_ras,
                            "{{duracion}}": u_hours,
                            "{{trimestre}}": u_trim,
                            "{{inicio}}": u_ini,
                            "{{fin}}": u_fin
                        })
                        t_units.append(new_r)

        # --- 5. CLONAR FILAS DE TABLA 6: PONDERACIÓN DE RAs (Tabla_Evaluacion_RA) ---
        t_eval_ra = self._find_table(body, 'Tabla_Evaluacion_RA', ns_map)
        if t_eval_ra is not None:
            rows = t_eval_ra.findall('.//table:table-row', ns_map)
            if len(rows) >= 3:
                tmpl_row = rows[1]
                tot_row = rows[2]
                t_eval_ra.remove(tmpl_row)
                t_eval_ra.remove(tot_row)
                
                ra_weights = ped_info.get("ra_ponderaciones", {})
                for idx, ra in enumerate(ras, start=1):
                    r_num = ra.get("numero", idx)
                    r_desc = LanguageLocalizer.localize_text(ra.get("descripcion", ""), to_lang=tag)
                    r_w = float(ra_weights.get(str(r_num), round(100.0 / max(1, len(ras)), 1)))
                    
                    new_r = copy.deepcopy(tmpl_row)
                    self._replace_in_element(new_r, {
                        "{{ra}}": f"RA{r_num}: {r_desc}",
                        "{{ra_num}}": f"RA{r_num}",
                        "{{ra_descripcion}}": r_desc,
                        "{{ra_peso}}": f"{r_w:.1f}%",
                        "{{ra_requisito}}": ""
                    })
                    t_eval_ra.append(new_r)
                t_eval_ra.append(tot_row)

        # --- 6. CLONAR FILAS DE TABLA 7: INSTRUMENTOS POR RA (Tabla_Evaluacion_Instrumentos) ---
        t_eval_inst = self._find_table(body, 'Tabla_Evaluacion_Instrumentos', ns_map)
        if t_eval_inst is not None:
            rows = t_eval_inst.findall('.//table:table-row', ns_map)
            if len(rows) > 1:
                tmpl_row = rows[1]
                t_eval_inst.remove(tmpl_row)
                
                ra_weights = ped_info.get("ra_ponderaciones", {})
                instruments_data = ped_info.get("instrumentos", {})
                
                for idx, ra in enumerate(ras, start=1):
                    r_num = ra.get("numero", idx)
                    ra_w = float(ra_weights.get(str(r_num), round(100.0 / max(1, len(ras)), 1)))
                    inst_list = instruments_data.get(str(r_num), [])
                    ces = [c.get("letra", "") for c in ra.get("criterios_evaluacion", [])]
                    all_ces_label = "Tots els CE" if tag == "VAL" else "Todos los CE"
                    ces_str = ", ".join(ces) if ces else all_ces_label
                    
                    if not inst_list:
                        new_r = copy.deepcopy(tmpl_row)
                        default_inst_name = LanguageLocalizer.localize_instrument_name(ped_defaults["evaluacion"]["instrumento_unico_nombre"], to_lang=tag)
                        self._replace_in_element(new_r, {
                            "{{inst_ra}}": f"RA{r_num}",
                            "{{cod_ra}}": f"RA{r_num}",
                            "{{ra_num}}": f"RA{r_num}",
                            "{{ra_codigo}}": f"RA{r_num}",
                            "{{ra}}": f"RA{r_num}",
                            "{{inst_nombre}}": default_inst_name,
                            "{{inst_peso_ra}}": "100.0%",
                            "{{inst_contribucion}}": f"{ra_w:.2f}%",
                            "{{inst_ces}}": ces_str
                        })
                        t_eval_inst.append(new_r)
                    else:
                        for i_idx, inst in enumerate(inst_list):
                            inst_w = float(inst.get("peso_ra", 100))
                            contrib = (ra_w * inst_w) / 100.0
                            inst_name = LanguageLocalizer.localize_instrument_name(inst.get("nombre", ""), to_lang=tag)
                            new_r = copy.deepcopy(tmpl_row)
                            self._replace_in_element(new_r, {
                                "{{inst_ra}}": f"RA{r_num}" if i_idx == 0 else "",
                                "{{cod_ra}}": f"RA{r_num}" if i_idx == 0 else "",
                                "{{ra_num}}": f"RA{r_num}" if i_idx == 0 else "",
                                "{{ra_codigo}}": f"RA{r_num}" if i_idx == 0 else "",
                                "{{ra}}": f"RA{r_num}" if i_idx == 0 else "",
                                "{{inst_nombre}}": inst_name,
                                "{{inst_peso_ra}}": f"{inst_w:.1f}%",
                                "{{inst_contribucion}}": f"{contrib:.2f}%",
                                "{{inst_ces}}": ces_str
                            })
                            t_eval_inst.append(new_r)

        # --- 7. EXPANDIR PÁRRAFOS DE CONTEXTUALIZACIÓN (1.2) CON SALTOS DE LÍNEA Y ESTILOS ---
        p_context_tmpl = None
        for p in body.findall('.//text:p', ns_map):
            if "{{contextualizacion_modulo}}" in "".join(p.itertext()):
                p_context_tmpl = p
                break

        if p_context_tmpl is not None:
            raw_body_style = p_context_tmpl.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name', 'Standard')

            def is_safe_text_style(s_name: str) -> bool:
                if not s_name:
                    return False
                for s_elem in root.findall('.//style:style', ns_map):
                    if s_elem.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:style:1.0}name') == s_name:
                        pp = s_elem.find('.//style:paragraph-properties', ns_map)
                        if pp is not None and pp.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:xsl-fo-compatible:1.0}break-before') == 'page':
                            return False
                return True

            body_style = raw_body_style if is_safe_text_style(raw_body_style) else 'Standard'

            bullet_style = None
            for p in body.findall('.//text:p', ns_map):
                t_check = "".join(p.itertext()).strip()
                if t_check.startswith(('•', '−', '-')) and p != p_context_tmpl:
                    cand = p.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name')
                    if cand and is_safe_text_style(cand):
                        bullet_style = cand
                        break
            if not bullet_style:
                bullet_style = body_style

            parent = body
            idx_p = list(parent).index(p_context_tmpl)
            parent.remove(p_context_tmpl)
            insert_idx = idx_p

            if orientaciones:
                raw_paras = [p.strip() for p in orientaciones.split("\n") if p.strip()]
            else:
                if tag == "VAL":
                    raw_paras = [
                        f"La formació del mòdul professional de {mod_name} capacita a l'alumnat per a exercir amb solvència les funcions tècniques, organitzatives i operatives associades al perfil laboral del títol, garantint la qualitat, seguretat i compliment dels estàndards del sector professional."
                    ]
                else:
                    raw_paras = [
                        ped_defaults["contextualizacion_template"].format(mod_name=mod_name)
                    ]

            for raw_para in raw_paras:
                clean_p = raw_para.strip()
                if not clean_p:
                    continue
                is_bullet = False
                if clean_p.startswith(("−", "-", "•", "*", "–", "·")):
                    is_bullet = True
                    clean_p = clean_p.lstrip("−-•*–· ").strip()
                elif re.match(r'^[a-zñ]\)\s+', clean_p):
                    is_bullet = True

                new_p = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p')
                if is_bullet:
                    if bullet_style:
                        new_p.attrib['{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name'] = bullet_style
                    new_p.text = f"• {clean_p}"
                else:
                    if body_style:
                        new_p.attrib['{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name'] = body_style
                    new_p.text = clean_p

                parent.insert(insert_idx, new_p)
                insert_idx += 1

        # --- 8. EXPANDIR PÁRRAFOS DE RECURSOS ESPECÍFICOS (6.1) CON VIÑETAS INDIVIDUALES ---
        p_rec_tmpl = None
        for p in body.findall('.//text:p', ns_map):
            if "{{recursos_especificos}}" in "".join(p.itertext()):
                p_rec_tmpl = p
                break

        if p_rec_tmpl is not None:
            parent = body
            idx_p = list(parent).index(p_rec_tmpl)
            parent.remove(p_rec_tmpl)
            insert_idx = idx_p

            sw_list = ped_info.get("recursos_software", [])
            hw_list = ped_info.get("recursos_hardware", [])

            rec_items = []
            sw_prefix = "• Programari tècnic:" if tag == "VAL" else "• Software técnico:"
            hw_prefix = "• Maquinari i instrumental:" if tag == "VAL" else "• Hardware e instrumental:"

            for sw in sw_list:
                sw_loc = LanguageLocalizer.localize_text(sw, to_lang=tag)
                rec_items.append(f"{sw_prefix} {sw_loc}")
            for hw in hw_list:
                hw_loc = LanguageLocalizer.localize_text(hw, to_lang=tag)
                rec_items.append(f"{hw_prefix} {hw_loc}")

            if not rec_items:
                if tag == "VAL":
                    rec_items = [
                        "• Programari tècnic: Plataforma d'aprenentatge i ferramentes de gestió.",
                        "• Maquinari i instrumental: Ordinador amb accés a internet."
                    ]
                else:
                    rec_items = list(ped_defaults["recursos_especificos_fallback"])

            for item in rec_items:
                new_p = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p')
                if bullet_style:
                    new_p.attrib['{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name'] = bullet_style
                new_p.text = item
                parent.insert(insert_idx, new_p)
                insert_idx += 1

        siglas = get_module_initials(mod_data=mod_data, mod_code=mod_code, mod_name=raw_mod_name)

        raw_metodologia = ped_info.get("metodologia", "")
        if raw_metodologia:
            metodologia = LanguageLocalizer.localize_text(raw_metodologia, to_lang=tag)
        else:
            if tag == "VAL":
                metodologia = (
                    f"El mòdul de {mod_name} es desenvolupa combinant sessions d'exposició inductiva amb "
                    f"treball pràctic intensiu en el laboratori informàtic. Es prioritza l'Aprenentatge Basat en Projectes (ABP), "
                    f"la resolució sistemàtica de problemes reals i l'aprenentatge cooperatiu, integrant bones pràctiques professionals."
                )
            else:
                metodologia = ped_defaults["metodologia_template"].format(mod_name=mod_name)

        raw_espacios = ped_info.get("espacios", "")
        if isinstance(raw_espacios, list):
            espacios_str = ", ".join(raw_espacios)
        else:
            espacios_str = str(raw_espacios)
        espacios = LanguageLocalizer.localize_spaces(espacios_str, to_lang=tag)

        raw_formula = ped_info.get("formula_evaluacion", "")
        if raw_formula:
            if tag == "VAL":
                formula = raw_formula.replace("Módulo =", "Mòdul =").replace("Módulo=", "Mòdul=")
            else:
                formula = raw_formula.replace("Mòdul =", "Módulo =").replace("Mòdul=", "Módulo=")
            formula = LanguageLocalizer.localize_text(formula, to_lang=tag)
        else:
            formula = "Mòdul = 100% (Avaluació contínua)" if tag == "VAL" else "Módulo = 100% (Evaluación continua)"

        global_vars = {
            "{{modulo}}": f"{mod_code} - {mod_name}",
            "{{codigo_modulo}}": mod_code,
            "{{modulo_codigo}}": mod_code,
            "{{nombre_modulo}}": mod_name,
            "{{modulo_nombre}}": mod_name,
            "{{siglas}}": siglas,
            "{{siglas_modulo}}": siglas,
            "{{modulo_siglas}}": siglas,
            "{{modulo_header}}": f"{mod_code} - {mod_name[:26]}",
            "{{ciclo}}": ciclo_title,
            "{{ciclo_corto}}": ciclo_code,
            "{{codigo_ciclo}}": codigo_ciclo,
            "{{familia}}": familia,
            "{{curso}}": curso,
            "{{horas}}": horas if horas else "—",
            "{{ects}}": ects,
            "{{profesor}}": profesor,
            "{{centro}}": centro,
            "{{curso_academico}}": curso_acad,
            "{{normativa_referencia}}": normativa,
            "{{nivel}}": nivel,
            "{{contextualizacion_modulo}}": "",
            "{{acreditacion}}": acreditacion_text,
            "{{metodologia_especifica}}": metodologia,
            "{{recursos_especificos}}": "",
            "{{espacios_especificos}}": espacios,
            "{{formula_evaluacion}}": formula
        }

        self._replace_in_element(root, global_vars)

        os.makedirs(os.path.dirname(os.path.abspath(output_odt_path)), exist_ok=True)
        self._package_fodt_to_odt(root, output_odt_path, ns_map)

    def _find_table(self, body, name: str, ns_map: dict):
        for t in body.findall('.//table:table', ns_map):
            if t.attrib.get('{urn:oasis:names:tc:opendocument:xmlns:table:1.0}name') == name:
                return t
        return None

    def _replace_in_element(self, element, var_map: dict):
        if element.text:
            for k, v in var_map.items():
                if k in element.text:
                    element.text = element.text.replace(k, v)
        if element.tail:
            for k, v in var_map.items():
                if k in element.tail:
                    element.tail = element.tail.replace(k, v)
        for child in element:
            self._replace_in_element(child, var_map)

    def _package_fodt_to_odt(self, root, odt_path: str, ns_map: dict):
        font_decls = root.find('.//office:font-face-decls', ns_map)
        styles = root.find('.//office:styles', ns_map)
        auto_styles = root.find('.//office:automatic-styles', ns_map)
        master_styles = root.find('.//office:master-styles', ns_map)
        body = root.find('.//office:body', ns_map)
        
        content_root = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:office:1.0}document-content', {
            '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}version': '1.2'
        })
        if font_decls is not None: content_root.append(copy.deepcopy(font_decls))
        if auto_styles is not None: content_root.append(copy.deepcopy(auto_styles))
        if body is not None: content_root.append(copy.deepcopy(body))
        content_xml = ET.tostring(content_root, encoding='utf-8', xml_declaration=True)
        
        styles_root = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:office:1.0}document-styles', {
            '{urn:oasis:names:tc:opendocument:xmlns:office:1.0}version': '1.2'
        })
        if font_decls is not None: styles_root.append(copy.deepcopy(font_decls))
        if styles is not None: styles_root.append(copy.deepcopy(styles))
        if auto_styles is not None: styles_root.append(copy.deepcopy(auto_styles))
        if master_styles is not None: styles_root.append(copy.deepcopy(master_styles))
        styles_xml = ET.tostring(styles_root, encoding='utf-8', xml_declaration=True)
        
        manifest_xml = (
            '<?xml version="1.0" encoding="UTF-8"?>\n'
            '<manifest:manifest xmlns:manifest="urn:oasis:names:tc:opendocument:xmlns:manifest:1.0" manifest:version="1.2">\n'
            ' <manifest:file-entry manifest:full-path="/" manifest:version="1.2" manifest:media-type="application/vnd.oasis.opendocument.text"/>\n'
            ' <manifest:file-entry manifest:full-path="content.xml" manifest:media-type="text/xml"/>\n'
            ' <manifest:file-entry manifest:full-path="styles.xml" manifest:media-type="text/xml"/>\n'
            '</manifest:manifest>'
        )
        
        os.makedirs(os.path.dirname(os.path.abspath(odt_path)), exist_ok=True)
        with zipfile.ZipFile(odt_path, 'w') as z:
            z.writestr('mimetype', 'application/vnd.oasis.opendocument.text', compress_type=zipfile.ZIP_STORED)
            z.writestr('META-INF/manifest.xml', manifest_xml, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr('content.xml', content_xml, compress_type=zipfile.ZIP_DEFLATED)
            z.writestr('styles.xml', styles_xml, compress_type=zipfile.ZIP_DEFLATED)


class SystematicProgramacionGenerator:
    """
    Genera sistemáticamente las programaciones didácticas a partir de plantilla.fodt / plantilla_val.fodt
    para todos los módulos de todos los ciclos formativos en valenciano y castellano.
    """
    def __init__(self, base_dir: str = ".", template_path: Optional[str] = None):
        self.base_dir = base_dir
        self.repo = CurriculumRepository(base_dir)
        self.ped_provider = PedagogicalDataProvider(base_dir)
        tmpl = template_path if template_path else os.path.join(base_dir, DEFAULT_CONFIG["metadata"]["template_path"])
        self.engine = FodtTemplateEngine(tmpl)

    def generate_all(
        self,
        output_dir: Optional[str] = None,
        curso_academico: Optional[str] = None,
        idiomas: Optional[List[str]] = None
    ) -> List[Tuple[str, str, str]]:
        output_dir = output_dir or DEFAULT_CONFIG["metadata"]["output_dir"]
        curso_academico = curso_academico or DEFAULT_CONFIG["metadata"]["curso_academico"]
        idiomas = idiomas or ["CAS", "VAL"]
        generated = []
        for ciclo_code in self.repo.get_all_cycles().keys():
            res = self.generate_cycle(ciclo_code, output_dir=output_dir, curso_academico=curso_academico, idiomas=idiomas)
            generated.extend(res)
        return generated

    def generate_cycle(
        self,
        ciclo_code: str,
        output_dir: Optional[str] = None,
        curso_academico: Optional[str] = None,
        idiomas: Optional[List[str]] = None
    ) -> List[Tuple[str, str, str]]:
        output_dir = output_dir or DEFAULT_CONFIG["metadata"]["output_dir"]
        curso_academico = curso_academico or DEFAULT_CONFIG["metadata"]["curso_academico"]
        idiomas = idiomas or ["CAS", "VAL"]
        generated = []
        base_cycle = self.repo.get_cycle_data(ciclo_code, idioma="CAS")
        if not base_cycle:
            print(f"[WARN] Ciclo no encontrado en el repositorio: {ciclo_code}", file=sys.stderr)
            return generated

        canonical_code = base_cycle.get("ciclo", ciclo_code).upper()
        if canonical_code == "SMR":
            canonical_code = "SMX"
        elif canonical_code == "IA":
            canonical_code = "IABD"

        c_dir = os.path.join(output_dir, canonical_code)
        os.makedirs(c_dir, exist_ok=True)

        context_meta = {
            "ciclo": canonical_code,
            "profesor": DEFAULT_CONFIG["metadata"]["profesor"],
            "centro": DEFAULT_CONFIG["metadata"]["centro"],
            "curso_academico": curso_academico
        }

        for lang in idiomas:
            lang_tag = "VAL" if str(lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ", "CA", "CAT") else "CAS"
            cycle_data = self.repo.get_cycle_data(canonical_code, idioma=lang_tag) or base_cycle

            for mod in cycle_data.get("modulos", []):
                mod_code = str(mod.get("codigo", "")).zfill(4)
                mod_name = mod.get("nombre", "")
                mod_curso = mod.get("curso_orientativo", DEFAULT_CONFIG["metadata"]["curso_orientativo"])

                ped_info = self.ped_provider.get_pedagogical_data(mod_code, mod, ciclo=canonical_code, idioma=lang_tag)

                filename = get_pd_filename(
                    ciclo=canonical_code,
                    curso=mod_curso,
                    mod_code=mod_code,
                    mod_name=mod_name,
                    mod_data=mod,
                    curso_academico=curso_academico,
                    idioma=lang_tag
                )
                odt_path = os.path.join(c_dir, filename)

                self.engine.render_and_save(odt_path, mod, cycle_data, ped_info, context_meta, idioma=lang_tag)
                generated.append((canonical_code, f"{mod_code}_{lang_tag}", odt_path))

        return generated

    def generate_single_module(
        self,
        identifier: str,
        ciclo: Optional[str] = None,
        output_filepath: Optional[str] = None,
        curso_academico: Optional[str] = None,
        idiomas: Optional[List[str]] = None
    ) -> List[str]:
        curso_academico = curso_academico or DEFAULT_CONFIG["metadata"]["curso_academico"]
        idiomas = idiomas or ["CAS", "VAL"]
        base_result = self.repo.get_module(ciclo, identifier, idioma="CAS")
        if not base_result:
            raise ValueError(f"No se encontró el módulo '{identifier}' en el repositorio de currículos.")

        generated_paths = []
        for lang in idiomas:
            lang_tag = "VAL" if str(lang).upper() in ("VAL", "VALENCIANO", "VALENCIÀ", "CA", "CAT") else "CAS"
            result = self.repo.get_module(ciclo, identifier, idioma=lang_tag) or base_result
            mod_data, cycle_data = result
            c_code = cycle_data.get("ciclo", "FP").upper()
            mod_code = str(mod_data.get("codigo", "")).zfill(4)
            mod_name = mod_data.get("nombre", "")
            mod_curso = mod_data.get("curso_orientativo", DEFAULT_CONFIG["metadata"]["curso_orientativo"])

            ped_info = self.ped_provider.get_pedagogical_data(mod_code, mod_data, ciclo=c_code, idioma=lang_tag)
            context_meta = {
                "ciclo": c_code,
                "profesor": DEFAULT_CONFIG["metadata"]["profesor"],
                "centro": DEFAULT_CONFIG["metadata"]["centro"],
                "curso_academico": curso_academico
            }

            if output_filepath:
                base_name, ext = os.path.splitext(output_filepath)
                clean_base = re.sub(r'_(CAS|VAL)$', '', base_name, flags=re.IGNORECASE)
                if len(idiomas) > 1:
                    odt_path = f"{clean_base}_{lang_tag}.odt"
                else:
                    if not clean_base.endswith(f"_{lang_tag}"):
                        odt_path = f"{clean_base}_{lang_tag}.odt"
                    else:
                        odt_path = f"{clean_base}.odt"
            else:
                c_dir = os.path.join(DEFAULT_CONFIG["metadata"]["output_dir"], c_code)
                os.makedirs(c_dir, exist_ok=True)
                filename = get_pd_filename(
                    ciclo=c_code,
                    curso=mod_curso,
                    mod_code=mod_code,
                    mod_name=mod_name,
                    mod_data=mod_data,
                    curso_academico=curso_academico,
                    idioma=lang_tag
                )
                odt_path = os.path.join(c_dir, filename)

            self.engine.render_and_save(odt_path, mod_data, cycle_data, ped_info, context_meta, idioma=lang_tag)
            generated_paths.append(odt_path)

        return generated_paths


# ==============================================================================
# PUNTO DE ENTRADA CLI INTEGRADO (3 FUNCIONALIDADES EN 1 SCRIPT)
# ==============================================================================

def main():
    default_meta = DEFAULT_CONFIG["metadata"]

    parser = argparse.ArgumentParser(
        description="Sistema integral de Programaciones Didácticas FP (Parseo XML + Pedagogía JSON + Generación ODT)."
    )

    # GRUPO 1: Parseo y validación de currículos XML (Parte 1)
    parser.add_argument(
        "--parse-xml",
        type=str,
        default=None,
        help="[Parte 1] Parsea un archivo oficial XML del BOE y genera curriculum_<ciclo>.json."
    )

    # GRUPO 2: Generación de andamiaje pedagógico (Parte 2)
    parser.add_argument(
        "--generar-pedagogia",
        action="store_true",
        help="[Parte 2] Genera el andamiaje pedagógico JSON para el ciclo especificado (--ciclo) o todos (--all)."
    )

    # GRUPO 3: Generación de programaciones didácticas ODT (Parte 3)
    parser.add_argument(
        "--all",
        action="store_true",
        help="[Parte 3 / Parte 2] Aplica la acción a TODOS los ciclos disponibles."
    )
    parser.add_argument(
        "--ciclo",
        type=str,
        default=None,
        help="Código del ciclo formativo (ej. DAM, DAW, SMX, ASIR)."
    )
    parser.add_argument(
        "--modulo",
        type=str,
        default=None,
        help="[Parte 3] Genera un módulo específico por código numérico o nombre (ej. 0221, 0489)."
    )
    parser.add_argument(
        "--idioma", "--lang",
        choices=["ambos", "cas", "val", "all"],
        default="ambos",
        help="Idioma de las programaciones didácticas a generar: 'ambos' (por defecto: genera _CAS y _VAL), 'cas' (castellano), 'val' (valenciano)."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Ruta de archivo de salida personalizada (.odt o .json según la acción)."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=default_meta["output_dir"],
        help=f"Directorio raíz de salida para documentos .odt (por defecto: '{default_meta['output_dir']}')."
    )
    parser.add_argument(
        "--curso-academico", "--curso-escolar",
        type=str,
        default=default_meta["curso_academico"],
        help=f"Curso escolar / académico de las programaciones (por defecto: '{default_meta['curso_academico']}')."
    )
    parser.add_argument(
        "--plantilla", "--template",
        type=str,
        default=None,
        help=f"Ruta a la plantilla ODF (.fodt) base a utilizar (por defecto: '{default_meta['template_path']}')."
    )

    args = parser.parse_args()


    # --- ACCIÓN 1: PARSEAR XML DEL BOE ---
    if args.parse_xml:
        run_parse_curriculum(args.parse_xml, ciclo=args.ciclo, output_path=args.output)
        return

    # --- ACCIÓN 2: GENERAR ANDAMIAJE PEDAGÓGICO JSON ---
    if args.generar_pedagogia:
        if args.all:
            run_generate_all_pedagogy(".")
            return
        elif args.ciclo:
            c_code = args.ciclo.strip().lower()
            curr_path = f"curriculum_{c_code}.json"
            run_generate_cycle_pedagogy(curr_path, output_path=args.output)
            return
        else:
            print("[ERROR] Debe especificar --ciclo <CODIGO> o --all junto con --generar-pedagogia.", file=sys.stderr)
            sys.exit(1)

    # --- ACCIÓN 3: GENERAR PROGRAMACIONES DIDÁCTICAS ODT ---
    systematic_gen = SystematicProgramacionGenerator(".", template_path=args.plantilla)

    if args.idioma in ("ambos", "all"):
        target_idiomas = ["CAS", "VAL"]
    elif args.idioma == "val":
        target_idiomas = ["VAL"]
    else:
        target_idiomas = ["CAS"]

    if args.all:
        print(f"[*] Iniciando generación sistemática en formato ODT para TODOS los ciclos (idiomas: {', '.join(target_idiomas)})...")
        results = systematic_gen.generate_all(output_dir=args.output_dir, curso_academico=args.curso_academico, idiomas=target_idiomas)
        print(f"[OK] Generación completada con éxito. Total de programaciones didácticas ODT generadas: {len(results)}")
        for ciclo, mod, odt_path in results:
            print(f"     - [{ciclo}] Módulo {mod} -> {odt_path}")
        return

    if args.ciclo and not args.modulo:
        print(f"[*] Generando programaciones ODT para el ciclo {args.ciclo.upper()} (idiomas: {', '.join(target_idiomas)})...")
        results = systematic_gen.generate_cycle(args.ciclo.upper(), output_dir=args.output_dir, curso_academico=args.curso_academico, idiomas=target_idiomas)
        print(f"[OK] Generados {len(results)} módulos ODT para {args.ciclo.upper()}.")
        for ciclo, mod, odt_path in results:
            print(f"     - Módulo {mod} -> {odt_path}")
        return

    if args.modulo:
        print(f"[*] Generando programación ODT para el módulo {args.modulo} (idiomas: {', '.join(target_idiomas)})...")
        odt_files = systematic_gen.generate_single_module(
            args.modulo,
            ciclo=args.ciclo,
            output_filepath=args.output,
            curso_academico=args.curso_academico,
            idiomas=target_idiomas
        )
        for odt_file in odt_files:
            print(f"[OK] Módulo generado exitosamente en OpenDocument (.odt): {odt_file}")
        return

    parser.print_help()


if __name__ == '__main__':
    main()

