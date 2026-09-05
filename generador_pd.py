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
    curso_academico: Optional[str] = None
) -> str:
    """
    Genera el nombre estándar de archivo:
    PD_{curso_escolar}_{ciclo}{curso}_{codigo}_{iniciales}.odt
    Ejemplo: PD_26-27_DAM2_0489_PMYDM.odt
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

    return f"PD_{curso_esc}_{ciclo_curso}_{code_str}_{initials}.odt"


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

            for l in m_lines:
                if re.search(r'Resultados\s+de\s+aprendizaje\s+y\s+criterios\s+de\s+evaluaci[oó]n', l, re.I) or re.search(r'^Resultados\s+de\s+aprendizaje\b', l, re.I):
                    in_ras = True
                    continue
                if re.search(r'Orientaciones\s+pedag[oó]gicas', l, re.I):
                    in_ras = False
                    in_orientaciones = True
                    continue
                if in_orientaciones:
                    if re.search(r'Duraci[oó]n:\s*\d+\s*horas', l, re.I):
                        in_orientaciones = False
                    else:
                        orientaciones.append(l)
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
                "resultados_aprendizaje": ras
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
    for c_file in sorted(base_currs):
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
        self._load()

    def _load(self):
        cycle_files: Dict[str, List[str]] = {}
        json_pattern = os.path.join(self.base_dir, "curriculum_*.json")
        for j_file in glob.glob(json_pattern):
            m = re.search(r'curriculum_([a-zA-Z0-9]+)(?:_\d{8}_\d{6})?\.json', os.path.basename(j_file), re.IGNORECASE)
            m = re.search(r'curriculum_([a-zA-Z0-9]+)(?:_\d{8}_\d{6}(?:_\d+)?)?\.json', os.path.basename(j_file), re.IGNORECASE)
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
            file_list.sort(key=lambda p: os.path.getmtime(p), reverse=True)
            file_list.sort(key=lambda p: (PedagogicalDataProvider._extract_timestamp(p), os.path.getmtime(p)), reverse=True)
            chosen_file = file_list[0]
            try:
                with open(chosen_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    data = CurriculumSanitizer.sanitize_and_repair(data, source_desc=os.path.basename(chosen_file))
                    ciclo_id = data.get("ciclo", c_code).upper()
                    data["ciclo"] = ciclo_id
                    self.curriculums[ciclo_id] = data
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

    def get_cycle_data(self, ciclo: str) -> Optional[Dict[str, Any]]:
        c_upper = ciclo.strip().upper()
        return self.curriculums.get(c_upper)

    def get_module(self, ciclo: Optional[str], identifier: str) -> Optional[Tuple[Dict[str, Any], Dict[str, Any]]]:
        clean_id = str(identifier).strip()
        code_match = re.search(r'\b([0-9]{3,4})\b', clean_id)
        search_code = code_match.group(1).zfill(4) if code_match else None

        search_cycles = []
        if ciclo and ciclo.strip().upper() in self.curriculums:
            search_cycles.append(self.curriculums[ciclo.strip().upper()])
        else:
            search_cycles = list(self.curriculums.values())

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
        ciclo: str = ""
    ) -> Dict[str, Any]:
        clean_code = str(mod_code).strip().zfill(4)
        c_upper = ciclo.strip().upper()
        c_lower = ciclo.strip().lower()

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
        # NIVEL 2: Archivo específico de ciclo:
        # pedagogia_{ciclo}[_timestamp].json
        # ----------------------------------------------------------------------
        if raw_ped_data is None and c_lower:
            pattern = f"pedagogia_{c_lower}*.json"
            level2_candidates = []
            for fpath in glob.glob(os.path.join(self.base_dir, pattern)):
                fname = os.path.basename(fpath)
                if re.match(rf'^pedagogia_{re.escape(c_lower)}(?:_\d{{8}}_\d{{6}})?\.json$'.replace('{{8}}', '{8}').replace('{{6}}', '{6}'), fname, re.IGNORECASE):
                    level2_candidates.append(fpath)
            for search_dir in [self.base_dir, os.path.join(self.base_dir, "old_jsons")]:
                if not os.path.exists(search_dir):
                    continue
                for fpath in glob.glob(os.path.join(search_dir, pattern)):
                    fname = os.path.basename(fpath)
                    if re.match(rf'^pedagogia_{re.escape(c_lower)}(?:_\d{{8}}_\d{{6}}(?:_\d+)?)?\.json$', fname, re.IGNORECASE):
                        level2_candidates.append(fpath)
                if level2_candidates:
                    break

            if level2_candidates:
                level2_candidates.sort(key=lambda p: (self._extract_timestamp(p), os.path.getmtime(p)), reverse=True)
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
        context_meta: Optional[Dict[str, Any]] = None
    ):
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

        with open(self.template_path, "r", encoding="utf-8") as f:
            raw_template = f.read()

        normalized_template = self._normalize_xml_placeholders(raw_template)
        root = ET.fromstring(normalized_template)
        body = root.find('.//office:body/office:text', ns_map)

        mod_code = str(mod_data.get("codigo", "")).zfill(4)
        mod_name = str(mod_data.get("nombre", ""))
        ciclo_code = context_meta.get("ciclo", cycle_data.get("ciclo", "")).upper()
        ciclo_title = cycle_data.get("titulo", f"Ciclo Formativo {ciclo_code}")
        familia = cycle_data.get("familia_profesional", meta_defaults["familia_profesional"])
        curso = str(mod_data.get("curso_orientativo", meta_defaults["curso_orientativo"]))
        ects = str(mod_data.get("creditos_ects", meta_defaults["creditos_ects"]))
        profesor = context_meta.get("profesor", meta_defaults["profesor"])
        centro = context_meta.get("centro", meta_defaults["centro"])
        curso_acad = context_meta.get("curso_academico", meta_defaults["curso_academico"])
        normativa = cycle_data.get("normativa_referencia", meta_defaults["normativa_referencia"])
        nivel = cycle_data.get("nivel", meta_defaults["nivel"])
        codigo_ciclo = str(cycle_data.get("codigo_ciclo", "")).strip()
        horas = str(mod_data.get("horas", "")).strip()

        orientaciones = str(mod_data.get("orientaciones_pedagogicas", "")).strip()

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
                acred_list.append(f"{uc} ({desc})" if desc else uc)
            acreditacion_text = "; ".join(acred_list) + "."
        else:
            acreditacion_text = acred_defaults["sin_uc_text"]

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
                        cualifs = [f"{c.get('codigo')}: {c.get('denominacion')}" for c in cualif_list if uc in c.get('unidades_competencia', [])]
                        cualif_str = " / ".join(cualifs) if cualifs else acred_defaults["cualif_default"]
                        new_r = copy.deepcopy(tmpl_row)
                        self._replace_in_element(new_r, {
                            "{{uc}}": f"{uc}: {uc_desc}" if uc_desc else uc,
                            "{{ifc}}": cualif_str
                        })
                        t_ucs.append(new_r)
                else:
                    new_r = copy.deepcopy(tmpl_row)
                    self._replace_in_element(new_r, {
                        "{{uc}}": acred_defaults["sin_uc_label"],
                        "{{ifc}}": acred_defaults["sin_ifc_label"]
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
                desc = all_comps.get(letra, ped_defaults["competencia_desc_default"])
                new_p = copy.deepcopy(p_comp_tmpl)
                new_p.text = f"{letra}) {desc}"
                for sub in list(new_p): new_p.remove(sub)
                parent.insert(insert_idx, new_p)
                insert_idx += 1

        # --- 3. CLONAR FILAS DE TABLA 4: RAs Y COMPETENCIAS VINCULADAS (Table_49111049) ---
        t_ra_comp = self._find_table(body, 'Table_49111049', ns_map)
        if t_ra_comp is not None:
            rows = t_ra_comp.findall('.//table:table-row', ns_map)
            if len(rows) > 1:
                tmpl_row = rows[1]
                t_ra_comp.remove(tmpl_row)
                for idx, ra in enumerate(ras, start=1):
                    r_num = ra.get("numero", idx)
                    r_desc = ra.get("descripcion", "")
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

        # --- 4. CLONAR FILAS DE TABLA 5: SECUENCIACIÓN DE UNIDADES (Tabla1) ---
        t_units = self._find_table(body, 'Tabla1', ns_map)
        if t_units is not None:
            rows = t_units.findall('.//table:table-row', ns_map)
            if len(rows) > 1:
                tmpl_row = rows[1]
                t_units.remove(tmpl_row)
                units_data = ped_info.get("unidades", [])
                for u in units_data:
                    u_code = u.get("codigo", "")
                    u_name = u.get("nombre", "")
                    u_title = f"{u_code}: {u_name}" if u_code else u_name
                    u_ras = ", ".join([f"RA{r}" for r in u.get("ras", [])])
                    u_hours = f"{u.get('horas', '')} h" if u.get('horas') else ""
                    u_trim = str(u.get("trimestre", ""))
                    u_ini = str(u.get("inicio", "")) if u.get("inicio") else ""
                    u_fin = str(u.get("fin", "")) if u.get("fin") else ""
                    
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
                    r_desc = ra.get("descripcion", "")
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
                    ces_str = ", ".join(ces) if ces else "Todos los CE"
                    
                    if not inst_list:
                        new_r = copy.deepcopy(tmpl_row)
                        self._replace_in_element(new_r, {
                            "{{inst_ra}}": f"RA{r_num}",
                            "{{inst_nombre}}": ped_defaults["evaluacion"]["instrumento_unico_nombre"],
                            "{{inst_peso_ra}}": "100.0%",
                            "{{inst_contribucion}}": f"{ra_w:.2f}%",
                            "{{inst_ces}}": ces_str
                        })
                        t_eval_inst.append(new_r)
                    else:
                        for i_idx, inst in enumerate(inst_list):
                            inst_w = float(inst.get("peso_ra", 100))
                            contrib = (ra_w * inst_w) / 100.0
                            new_r = copy.deepcopy(tmpl_row)
                            self._replace_in_element(new_r, {
                                "{{inst_ra}}": f"RA{r_num}" if i_idx == 0 else "",
                                "{{inst_nombre}}": inst.get("nombre", ""),
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
            for sw in sw_list:
                rec_items.append(f"• Software técnico: {sw}")
            for hw in hw_list:
                rec_items.append(f"• Hardware e instrumental: {hw}")

            if not rec_items:
                rec_items = list(ped_defaults["recursos_especificos_fallback"])

            for item in rec_items:
                new_p = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p')
                if bullet_style:
                    new_p.attrib['{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name'] = bullet_style
                new_p.text = item
                parent.insert(insert_idx, new_p)
                insert_idx += 1

        # --- 9. REEMPLAZO GLOBAL DE PLACEHOLDERS EN TODO EL DOCUMENTO ---
        
        if f"({ciclo_code})" in ciclo_title:
            ciclo_full_title = ciclo_title
        else:
            ciclo_full_title = f"{ciclo_title} ({ciclo_code})"
        if codigo_ciclo and codigo_ciclo not in ciclo_full_title:
            ciclo_full_title += f" (Código: {codigo_ciclo})"

        siglas = get_module_initials(mod_data=mod_data, mod_code=mod_code, mod_name=mod_name)

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
            "{{ciclo}}": ciclo_full_title,
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
            "{{metodologia_especifica}}": ped_info.get("metodologia", ""),
            "{{recursos_especificos}}": "",
            "{{espacios_especificos}}": ", ".join(ped_info["espacios"]) if isinstance(ped_info.get("espacios"), list) else str(ped_info.get("espacios", "")),
            "{{formula_evaluacion}}": ped_info.get("formula_evaluacion", "")
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
    Genera sistemáticamente las programaciones didácticas a partir de plantilla.fodt
    para todos los módulos de todos los ciclos formativos.
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
        curso_academico: Optional[str] = None
    ) -> List[Tuple[str, str, str]]:
        output_dir = output_dir or DEFAULT_CONFIG["metadata"]["output_dir"]
        curso_academico = curso_academico or DEFAULT_CONFIG["metadata"]["curso_academico"]
        generated = []
        for ciclo_code in self.repo.get_all_cycles().keys():
            res = self.generate_cycle(ciclo_code, output_dir=output_dir, curso_academico=curso_academico)
            generated.extend(res)
        return generated

    def generate_cycle(
        self,
        ciclo_code: str,
        output_dir: Optional[str] = None,
        curso_academico: Optional[str] = None
    ) -> List[Tuple[str, str, str]]:
        output_dir = output_dir or DEFAULT_CONFIG["metadata"]["output_dir"]
        curso_academico = curso_academico or DEFAULT_CONFIG["metadata"]["curso_academico"]
        generated = []
        cycle_data = self.repo.get_cycle_data(ciclo_code)
        if not cycle_data:
            print(f"[WARN] Ciclo no encontrado en el repositorio: {ciclo_code}", file=sys.stderr)
            return generated

        c_dir = os.path.join(output_dir, ciclo_code.upper())
        os.makedirs(c_dir, exist_ok=True)

        for mod in cycle_data.get("modulos", []):
            mod_code = str(mod.get("codigo", "")).zfill(4)
            mod_name = mod.get("nombre", "")
            mod_curso = mod.get("curso_orientativo", DEFAULT_CONFIG["metadata"]["curso_orientativo"])

            filename = get_pd_filename(
                ciclo=ciclo_code,
                curso=mod_curso,
                mod_code=mod_code,
                mod_name=mod_name,
                mod_data=mod,
                curso_academico=curso_academico
            )
            odt_path = os.path.join(c_dir, filename)

            ped_info = self.ped_provider.get_pedagogical_data(mod_code, mod, ciclo=ciclo_code)
            context_meta = {
                "ciclo": ciclo_code.upper(),
                "profesor": DEFAULT_CONFIG["metadata"]["profesor"],
                "centro": DEFAULT_CONFIG["metadata"]["centro"],
                "curso_academico": curso_academico
            }

            self.engine.render_and_save(odt_path, mod, cycle_data, ped_info, context_meta)
            generated.append((ciclo_code, mod_code, odt_path))

        return generated

    def generate_single_module(
        self,
        identifier: str,
        ciclo: Optional[str] = None,
        output_filepath: Optional[str] = None,
        curso_academico: Optional[str] = None
    ) -> str:
        curso_academico = curso_academico or DEFAULT_CONFIG["metadata"]["curso_academico"]
        result = self.repo.get_module(ciclo, identifier)
        if not result:
            raise ValueError(f"No se encontró el módulo '{identifier}' en el repositorio de currículos.")
        mod_data, cycle_data = result
        c_code = cycle_data.get("ciclo", "FP").upper()
        mod_code = str(mod_data.get("codigo", "")).zfill(4)
        mod_name = mod_data.get("nombre", "")
        mod_curso = mod_data.get("curso_orientativo", DEFAULT_CONFIG["metadata"]["curso_orientativo"])

        if output_filepath:
            base_name, ext = os.path.splitext(output_filepath)
            odt_path = f"{base_name}.odt" if ext.lower() != ".odt" else output_filepath
        else:
            c_dir = os.path.join(DEFAULT_CONFIG["metadata"]["output_dir"], c_code)
            os.makedirs(c_dir, exist_ok=True)
            filename = get_pd_filename(
                ciclo=c_code,
                curso=mod_curso,
                mod_code=mod_code,
                mod_name=mod_name,
                mod_data=mod_data,
                curso_academico=curso_academico
            )
            odt_path = os.path.join(c_dir, filename)

        ped_info = self.ped_provider.get_pedagogical_data(mod_code, mod_data, ciclo=c_code)
        context_meta = {
            "ciclo": c_code,
            "profesor": DEFAULT_CONFIG["metadata"]["profesor"],
            "centro": DEFAULT_CONFIG["metadata"]["centro"],
            "curso_academico": curso_academico
        }

        self.engine.render_and_save(odt_path, mod_data, cycle_data, ped_info, context_meta)
        return odt_path


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

    if args.all:
        print("[*] Iniciando generación sistemática en formato ODT para TODOS los ciclos...")
        results = systematic_gen.generate_all(output_dir=args.output_dir, curso_academico=args.curso_academico)
        print(f"[OK] Generación completada con éxito. Total de programaciones didácticas ODT generadas: {len(results)}")
        for ciclo, mod, odt_path in results:
            print(f"     - [{ciclo}] Módulo {mod} -> {odt_path}")
        return

    if args.ciclo and not args.modulo:
        print(f"[*] Generando programaciones ODT para el ciclo {args.ciclo.upper()}...")
        results = systematic_gen.generate_cycle(args.ciclo.upper(), output_dir=args.output_dir, curso_academico=args.curso_academico)
        print(f"[OK] Generados {len(results)} módulos ODT para {args.ciclo.upper()}.")
        for ciclo, mod, odt_path in results:
            print(f"     - Módulo {mod} -> {odt_path}")
        return

    if args.modulo:
        print(f"[*] Generando programación ODT para el módulo {args.modulo}...")
        odt_file = systematic_gen.generate_single_module(
            args.modulo,
            ciclo=args.ciclo,
            output_filepath=args.output,
            curso_academico=args.curso_academico
        )
        print(f"[OK] Módulo generado exitosamente en OpenDocument (.odt): {odt_file}")
        return

    parser.print_help()


if __name__ == '__main__':
    main()
