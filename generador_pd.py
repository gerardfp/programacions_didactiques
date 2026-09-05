#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
generador_pd.py
===============
Sistema universal y sistemático de generación de Programaciones Didácticas oficiales
para Formación Profesional (SMX, DAM, DAW y nuevos ciclos BOE) basado en plantilla nativa
OpenDocument (plantilla.fodt).

Características principales:
1. Plantilla ODF nativa (plantilla.fodt): Editable y personalizable directamente en LibreOffice Writer
   (estilos, logos, paleta de colores, tipografías, encabezados).
2. Motor de plantillas XML (FodtTemplateEngine): Rellena automáticamente los placeholders y clona las filas
   de las tablas predefinidas (UCs, competencias vinculadas, secuenciación de unidades, ponderación de RAs e instrumentos).
   Si algún dato opcional no existe (ej. fechas de inicio/fin), deja la celda en blanco sin alterar la tabla.
3. Tablas de evaluación especializadas:
   - Tabla 9.1: Ponderación de cada Resultado de Aprendizaje en el módulo (%) en 2 columnas limpias.
   - Tabla 9.2: Instrumentos de evaluación por RA, su peso interno y su contribución efectiva a la nota final.
4. Exportación exclusiva en formato oficial OpenDocument comprimido (.odt).
5. Descubrimiento automático de currículos XML oficiales del BOE y fallback pedagógico sistemático.
"""

import os
import sys
import re
import json
import glob
import copy
import zipfile
import argparse
import unicodedata
import xml.etree.ElementTree as ET
from typing import Dict, Any, List, Optional, Tuple

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


# ==============================================================================
# PARSER DE CURRÍCULOS BOE XML
# ==============================================================================

class BoeCurriculumXmlParser:
    """
    Parsea decretos de currículo en formato XML oficial del BOE.
    Extrae sistemáticamente competencias, cualificaciones, UCs y módulos profesionales.
    """
    @classmethod
    def parse_file(cls, xml_path: str) -> Dict[str, Any]:
        tree = ET.parse(xml_path)
        root = tree.getroot()
        
        texto_elem = root.find('.//texto')
        if texto_elem is None:
            texto_elem = root
            
        p_texts = []
        for p in texto_elem.iter('p'):
            t = "".join(p.itertext()).strip()
            if t:
                p_texts.append(t)
                
        full_text = "\n".join(p_texts)
        titulo_decreto = ""
        for p in p_texts[:10]:
            if "Real Decreto" in p or "Orden" in p:
                titulo_decreto = p
                break
        if not titulo_decreto:
            titulo_decreto = os.path.basename(xml_path)
            
        if "1691/2007" in full_text or "Sistemas Microinformáticos" in full_text:
            return cls._parse_smx(root, p_texts, titulo_decreto)
        elif "453/2010" in full_text or "Desarrollo de Aplicaciones Multiplataforma" in full_text:
            return cls._parse_dam_daw(root, p_texts, titulo_decreto)
        else:
            return cls._parse_generic(root, p_texts, titulo_decreto, xml_path)

    @classmethod
    def _parse_smx(cls, root, p_texts: list, titulo_decreto: str) -> dict:
        competencias = {}
        for p in p_texts:
            m = re.match(r'^([a-v])\)\s+(.+)', p)
            if m:
                letra = m.group(1)
                desc = m.group(2).strip()
                if letra not in competencias:
                    competencias[letra] = desc
                    
        cualificaciones = [
            {
                "codigo": "IFC078_2",
                "denominacion": "Sistemas microinformáticos",
                "unidades_competencia": ["UC0219_2", "UC0220_2", "UC0221_2", "UC0222_2"]
            },
            {
                "codigo": "IFC298_2",
                "denominacion": "Montaje y reparación de sistemas microinformáticos",
                "unidades_competencia": ["UC0953_2", "UC0219_2", "UC0954_2"]
            },
            {
                "codigo": "IFC299_2",
                "denominacion": "Operación de redes departamentales",
                "unidades_competencia": ["UC0220_2", "UC0955_2", "UC0956_2"]
            },
            {
                "codigo": "IFC300_2",
                "denominacion": "Operación de sistemas informáticos",
                "unidades_competencia": ["UC0219_2", "UC0957_2", "UC0958_2", "UC0959_2"]
            }
        ]
        
        all_ucs = {
            "UC0219_2": "Instalar y configurar el software base en sistemas microinformáticos.",
            "UC0220_2": "Instalar, configurar y verificar los elementos de la red local según procedimientos establecidos.",
            "UC0221_2": "Instalar, configurar y mantener paquetes informáticos de propósito general y aplicaciones específicas.",
            "UC0222_2": "Facilitar al usuario la utilización de paquetes informáticos de propósito general y aplicaciones específicas.",
            "UC0953_2": "Montar equipos microinformáticos.",
            "UC0954_2": "Reparar y ampliar equipamiento microinformático.",
            "UC0955_2": "Monitorizar los procesos de comunicaciones de la red local.",
            "UC0956_2": "Realizar los procesos de conexión entre redes privadas y redes públicas.",
            "UC0957_2": "Mantenimiento del subsistema físico en sistemas informáticos.",
            "UC0958_2": "Mantenimiento del subsistema lógico en sistemas informáticos.",
            "UC0959_2": "Mantenimiento de la seguridad en sistemas informáticos."
        }
        
        acreditaciones = {
            "0221": ["UC0953_2", "UC0954_2"],
            "0222": ["UC0958_2"],
            "0223": ["UC0221_2", "UC0222_2"],
            "0224": ["UC0219_2", "UC0957_2"],
            "0225": ["UC0955_2"],
            "0226": ["UC0959_2"],
            "0227": ["UC0956_2"]
        }
        
        anexo1_idx = 0
        for idx, p in enumerate(p_texts):
            if p.strip().upper() == 'ANEXO I':
                anexo1_idx = idx
                break
                
        mod_starts = []
        for idx in range(anexo1_idx, len(p_texts)):
            p = p_texts[idx]
            if 'Módulo Profesional:' in p or 'Modulo Profesional:' in p:
                mod_starts.append(idx)
        mod_starts.append(len(p_texts))
        
        modules = []
        for i in range(len(mod_starts)-1):
            s_idx = mod_starts[i]
            e_idx = mod_starts[i+1]
            m_lines = p_texts[s_idx:e_idx]
            
            header_line = m_lines[0]
            m_name = re.sub(r'^M[oó]dulo\s+Profesional:\s*', '', header_line, flags=re.IGNORECASE).strip()
            
            m_code = ""
            for l in m_lines[:5]:
                code_m = re.search(r'C[oó]digo:\s*(\d{4})', l)
                if code_m:
                    m_code = code_m.group(1)
                    break
                    
            ras = []
            in_ras = False
            current_ra = None
            orientaciones = []
            in_orientaciones = False
            
            for l in m_lines:
                if 'Resultados de aprendizaje y criterios de evaluación' in l:
                    in_ras = True
                    continue
                if 'Orientaciones pedagógicas' in l:
                    in_ras = False
                    in_orientaciones = True
                    continue
                if in_orientaciones:
                    orientaciones.append(l)
                    continue
                if in_ras:
                    ra_m = re.match(r'^(\d+)\.\s*(.+)', l)
                    if ra_m and not l.startswith('Criterios'):
                        if current_ra:
                            ras.append(current_ra)
                        current_ra = {
                            "numero": int(ra_m.group(1)),
                            "descripcion": ra_m.group(2).strip(),
                            "criterios_evaluacion": []
                        }
                        continue
                    if current_ra:
                        ces_matches = re.findall(r'([a-zñ])\)\s*([^a-zñ\)]+)', l)
                        for letter, ce_desc in ces_matches:
                            current_ra["criterios_evaluacion"].append({
                                "letra": letter,
                                "descripcion": ce_desc.strip()
                            })
            if current_ra:
                ras.append(current_ra)
                
            orientaciones_text = "\n\n".join([o.strip() for o in orientaciones if o.strip()])
            
            mod_comps = []
            comp_matches = re.findall(r'competencia[s]?\s+([a-zñ](?:\s*,\s*[a-zñ])*(?:\s*y\s*[a-zñ])?)', orientaciones_text, re.IGNORECASE)
            for cm in comp_matches:
                found_letters = re.findall(r'([a-zñ])', cm)
                for fl in found_letters:
                    if fl in competencias and fl not in mod_comps:
                        mod_comps.append(fl)
            if not mod_comps:
                mod_comps = list(competencias.keys())[:3]
                
            mod_ucs = acreditaciones.get(m_code, [])
            curso = "1º" if m_code in ["0221", "0222", "0223", "0225", "0229"] else "2º"
            hours_map = {
                "0221": 220, "0222": 130, "0223": 230, "0224": 140, "0225": 225,
                "0226": 105, "0227": 140, "0228": 125, "0229": 90, "0230": 65, "0231": 380
            }
            mod_hours = hours_map.get(m_code, 100)
            ects = round(mod_hours / 25)
            
            if m_code == "0231" and len(ras) > 10:
                ras = ras[:5]
                
            modules.append({
                "codigo": m_code,
                "nombre": m_name,
                "curso_orientativo": curso,
                "horas": mod_hours,
                "creditos_ects": ects,
                "unidades_competencia": mod_ucs,
                "competencias_titulo": sorted(mod_comps),
                "orientaciones_pedagogicas": orientaciones_text,
                "resultados_aprendizaje": ras
            })
            
        return {
            "ciclo": "SMX",
            "codigo_ciclo": "IFC201",
            "titulo": "Técnico en Sistemas Microinformáticos y Redes",
            "familia_profesional": "Informática y Comunicaciones",
            "nivel": "Grado Medio",
            "normativa_referencia": "Real Decreto 1691/2007, de 14 de diciembre",
            "competencias_profesionales_personales_sociales": competencias,
            "cualificaciones_profesionales": cualificaciones,
            "unidades_competencia": all_ucs,
            "correspondencia_unidades_competencia": acreditaciones,
            "modulos": modules
        }

    @classmethod
    def _parse_dam_daw(cls, root, p_texts: list, titulo_decreto: str) -> dict:
        result = {}
        for c in ["DAM", "DAW"]:
            j_path = f"curriculum_{c.lower()}.json"
            if os.path.exists(j_path):
                with open(j_path, "r", encoding="utf-8") as f:
                    result[c] = json.load(f)
        return result

    @classmethod
    def _parse_generic(cls, root, p_texts: list, titulo_decreto: str, xml_path: str) -> dict:
        cycle_key = os.path.splitext(os.path.basename(xml_path))[0].upper()
        competencias = {}
        for p in p_texts:
            m = re.match(r'^([a-zñ])\)\s+(.+)', p)
            if m:
                letra = m.group(1)
                desc = m.group(2).strip()
                if letra not in competencias:
                    competencias[letra] = desc
                    
        anexo1_idx = 0
        for idx, p in enumerate(p_texts):
            if 'ANEXO I' in p.strip().upper():
                anexo1_idx = idx
                break
                
        mod_starts = []
        for idx in range(anexo1_idx, len(p_texts)):
            p = p_texts[idx]
            if 'Módulo Profesional:' in p or 'Modulo Profesional:' in p:
                mod_starts.append(idx)
        mod_starts.append(len(p_texts))
        
        modules = []
        for i in range(len(mod_starts)-1):
            s_idx = mod_starts[i]
            e_idx = mod_starts[i+1]
            m_lines = p_texts[s_idx:e_idx]
            
            header_line = m_lines[0]
            m_name = re.sub(r'^M[oó]dulo\s+Profesional:\s*', '', header_line, flags=re.IGNORECASE).strip()
            
            m_code = ""
            for l in m_lines[:5]:
                code_m = re.search(r'C[oó]digo:\s*(\d{3,4})', l)
                if code_m:
                    m_code = code_m.group(1).zfill(4)
                    break
            if not m_code:
                m_code = str(i + 1).zfill(4)
                    
            ras = []
            in_ras = False
            current_ra = None
            orientaciones = []
            in_orientaciones = False
            
            for l in m_lines:
                if 'Resultados de aprendizaje y criterios de evaluación' in l or 'Resultados de aprendizaje' in l:
                    in_ras = True
                    continue
                if 'Orientaciones pedagógicas' in l:
                    in_ras = False
                    in_orientaciones = True
                    continue
                if in_orientaciones:
                    orientaciones.append(l)
                    continue
                if in_ras:
                    ra_m = re.match(r'^(\d+)\.\s*(.+)', l)
                    if ra_m and not l.startswith('Criterios'):
                        if current_ra:
                            ras.append(current_ra)
                        current_ra = {
                            "numero": int(ra_m.group(1)),
                            "descripcion": ra_m.group(2).strip(),
                            "criterios_evaluacion": []
                        }
                        continue
                    if current_ra:
                        ces_matches = re.findall(r'([a-zñ])\)\s*([^a-zñ\)]+)', l)
                        for letter, ce_desc in ces_matches:
                            current_ra["criterios_evaluacion"].append({
                                "letra": letter,
                                "descripcion": ce_desc.strip()
                            })
            if current_ra:
                ras.append(current_ra)
                
            orientaciones_text = "\n\n".join([o.strip() for o in orientaciones if o.strip()])
            mod_comps = list(competencias.keys())[:3]
            curso = "1º" if (i % 2 == 0) else "2º"
            mod_hours = 160
            ects = round(mod_hours / 25)
            
            modules.append({
                "codigo": m_code,
                "nombre": m_name,
                "curso_orientativo": curso,
                "horas": mod_hours,
                "creditos_ects": ects,
                "unidades_competencia": [],
                "competencias_titulo": sorted(mod_comps),
                "orientaciones_pedagogicas": orientaciones_text,
                "resultados_aprendizaje": ras
            })

        return {
            "ciclo": cycle_key,
            "codigo_ciclo": f"GEN_{cycle_key}",
            "titulo": f"Ciclo Formativo {cycle_key}",
            "familia_profesional": "Formación Profesional",
            "nivel": "Grado Superior",
            "normativa_referencia": titulo_decreto,
            "competencias_profesionales_personales_sociales": competencias,
            "cualificaciones_profesionales": [],
            "unidades_competencia": {},
            "correspondencia_unidades_competencia": {},
            "modulos": modules
        }


# ==============================================================================
# REPOSITORIO DE CURRÍCULOS
# ==============================================================================

class CurriculumRepository:
    """
    Descubre y gestiona los currículos de todos los ciclos formativos.
    Busca tanto archivos JSON directos (curriculum_*.json) como XMLs oficiales del BOE
    en curriculums_originals/.
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.curriculums: Dict[str, Dict[str, Any]] = {}
        self._load()

    def _load(self):
        # 1. Cargar todos los curriculum_*.json existentes en el directorio
        json_pattern = os.path.join(self.base_dir, "curriculum_*.json")
        for j_file in glob.glob(json_pattern):
            try:
                m = re.search(r'curriculum_([a-zA-Z0-9_]+)\.json', os.path.basename(j_file), re.IGNORECASE)
                default_code = m.group(1).upper() if m else ""
                with open(j_file, "r", encoding="utf-8") as f:
                    data = json.load(f)
                    ciclo_code = data.get("ciclo", default_code).upper()
                    if ciclo_code:
                        data["ciclo"] = ciclo_code
                        self.curriculums[ciclo_code] = data
            except Exception as e:
                print(f"[WARN] No se pudo cargar {j_file}: {e}", file=sys.stderr)

        # 2. Descubrir XMLs en curriculums_originals/
        xml_dir = os.path.join(self.base_dir, "curriculums_originals")
        if os.path.exists(xml_dir):
            for x_file in glob.glob(os.path.join(xml_dir, "*.xml")):
                base_name = os.path.splitext(os.path.basename(x_file))[0].upper()
                if base_name not in self.curriculums and base_name != "DAM_DAW":
                    try:
                        parsed = BoeCurriculumXmlParser.parse_file(x_file)
                        if isinstance(parsed, dict) and "ciclo" in parsed:
                            c_code = parsed["ciclo"].upper()
                            self.curriculums[c_code] = parsed
                            out_j = os.path.join(self.base_dir, f"curriculum_{c_code.lower()}.json")
                            with open(out_j, "w", encoding="utf-8") as f:
                                json.dump(parsed, f, ensure_ascii=False, indent=2)
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


# ==============================================================================
# PROVEEDOR DE DATOS PEDAGÓGICOS (JSON + FALLBACK AUTOMÁTICO)
# ==============================================================================

class PedagogicalDataProvider:
    """
    Suministra la información pedagógica de cada módulo (unidades didácticas,
    ponderaciones de RAs, fórmulas de evaluación, instrumentos, metodología y recursos).
    Si un módulo está en pedagogia_modulos.json, extrae sus datos precisos.
    Si es un módulo nuevo o sin definir, genera sistemáticamente una estructura coherente y completa.
    """
    def __init__(self, filepath: str = "pedagogia_modulos.json"):
        self.data: Dict[str, Any] = {}
        if os.path.exists(filepath):
            try:
                with open(filepath, "r", encoding="utf-8") as f:
                    self.data = json.load(f)
            except Exception as e:
                print(f"[WARN] No se pudo leer {filepath}: {e}", file=sys.stderr)

    def get_pedagogical_data(self, mod_code: str, mod_data: Dict[str, Any]) -> Dict[str, Any]:
        clean_code = str(mod_code).strip().zfill(4)
        if clean_code in self.data:
            return copy.deepcopy(self.data[clean_code])
            
        return self._generate_fallback(clean_code, mod_data)

    def _generate_fallback(self, code: str, mod_data: Dict[str, Any]) -> Dict[str, Any]:
        ras = mod_data.get("resultados_aprendizaje", [])
        num_ras = len(ras)
        total_hours = mod_data.get("horas") or (mod_data.get("creditos_ects", 8) * 25)
        
        # 1. Unidades didácticas vinculadas a RAs
        unidades = []
        if num_ras == 0:
            unidades = [
                {"codigo": "UD 1", "nombre": "Fundamentos y principios teóricos", "ras": [1], "horas": total_hours // 2, "trimestre": "1er Trimestre", "inicio": "", "fin": ""},
                {"codigo": "UD 2", "nombre": "Aplicaciones avanzadas y proyectos", "ras": [1], "horas": total_hours - (total_hours // 2), "trimestre": "2º Trimestre", "inicio": "", "fin": ""}
            ]
        else:
            hours_per_ra = max(10, total_hours // num_ras)
            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                desc = ra.get("descripcion", "")
                short_title = desc[:55].rstrip(",.:; ") + "..." if len(desc) > 55 else desc
                
                if idx <= max(1, (num_ras + 2) // 3):
                    trim = "1er Trimestre"
                elif idx <= max(2, (2 * num_ras + 1) // 3):
                    trim = "2º Trimestre"
                else:
                    trim = "3er Trimestre"
                    
                u_hours = hours_per_ra if idx < num_ras else (total_hours - hours_per_ra * (num_ras - 1))
                unidades.append({
                    "codigo": f"UD {idx}",
                    "nombre": f"{short_title}",
                    "ras": [r_num],
                    "horas": u_hours,
                    "trimestre": trim,
                    "inicio": "",
                    "fin": ""
                })
                
        # 2. Ponderaciones balanceadas que suman exactamente 100.0%
        ra_ponderaciones = {}
        if num_ras > 0:
            base_w = round(100.0 / num_ras, 1)
            cur_sum = 0.0
            for idx, ra in enumerate(ras, start=1):
                r_num = ra.get("numero", idx)
                if idx == num_ras:
                    w = round(100.0 - cur_sum, 1)
                else:
                    w = base_w
                    cur_sum += w
                ra_ponderaciones[str(r_num)] = w
        else:
            ra_ponderaciones["1"] = 100.0
            
        # 3. Fórmula LaTeX
        formula_terms = [f"{w/100:.2f} · RA_{r}" for r, w in ra_ponderaciones.items()]
        formula = f"Módulo = {' + '.join(formula_terms)}"
        
        # 4. Instrumentos de evaluación balanceados (60% práctica / 40% teórica)
        instrumentos = {}
        for r_str in ra_ponderaciones.keys():
            instrumentos[r_str] = [
                {"nombre": "Prácticas de laboratorio y supuestos técnicos aplicados", "peso_ra": 60.0},
                {"nombre": "Pruebas objetivas y supuestos teórico-prácticos", "peso_ra": 40.0}
            ]
            
        mod_name = mod_data.get("nombre", "")
        metodologia = (
            f"El módulo de {mod_name} se desarrolla combinando sesiones de exposición inductiva con "
            f"trabajo práctico intensivo en el laboratorio informático. Se prioriza el Aprendizaje Basado en Proyectos (ABP), "
            f"la resolución sistemática de problemas reales y el aprendizaje cooperativo, integrando buenas prácticas profesionales."
        )
        
        recursos_sw = [
            "Sistemas operativos GNU/Linux y Microsoft Windows",
            "Entornos de desarrollo integrados (IDE) y utilidades de configuración",
            "Plataforma de virtualización (VirtualBox, VMware, Docker)",
            "Herramientas ofimáticas y plataformas de gestión del aprendizaje (Moodle)"
        ]
        
        recursos_hw = [
            "Ordenadores de desarrollo en red con conexión a Internet de banda ancha",
            "Dispositivos de almacenamiento externo y sistemas de copia de seguridad",
            "Proyector interactivo y puesto informático para el docente"
        ]
        
        espacios = (
            "Aula polivalente y aula de informática equipada con ordenadores conectados en red local y "
            "acceso directo a Internet, con configuración técnica adecuada a los requerimientos del módulo."
        )
        
        return {
            "unidades": unidades,
            "ra_ponderaciones": ra_ponderaciones,
            "formula_evaluacion": formula,
            "instrumentos": instrumentos,
            "metodologia": metodologia,
            "recursos_software": recursos_sw,
            "recursos_hardware": recursos_hw,
            "espacios": espacios
        }


# ==============================================================================
# MOTOR DE PLANTILLAS ODF NATIVO (plantilla.fodt -> .fodt y .odt)
# ==============================================================================

class FodtTemplateEngine:
    """
    Carga la plantilla oficial en formato Flat XML ODF (plantilla.fodt),
    clona dinámicamente las filas de las tablas predefinidas rellenando los datos curriculares/pedagógicos
    (dejando en blanco las celdas sin datos) y exporta los archivos .fodt y .odt.
    """
    def __init__(self, template_path: str = "plantilla.fodt"):
        self.template_path = template_path
        if not os.path.exists(template_path):
            raise FileNotFoundError(f"Plantilla no encontrada: '{template_path}'")

    def render_and_save(
        self,
        output_odt_path: str,
        mod_data: Dict[str, Any],
        cycle_data: Dict[str, Any],
        ped_info: Dict[str, Any],
        context_meta: Optional[Dict[str, Any]] = None
    ):
        context_meta = context_meta or {}

        # Mapeo de namespaces ODF
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

        tree = ET.parse(self.template_path)
        root = tree.getroot()
        body = root.find('.//office:body/office:text', ns_map)

        mod_code = str(mod_data.get("codigo", "")).zfill(4)
        mod_name = str(mod_data.get("nombre", ""))
        ciclo_code = context_meta.get("ciclo", cycle_data.get("ciclo", "")).upper()
        ciclo_title = cycle_data.get("titulo", f"Ciclo Formativo {ciclo_code}")
        familia = cycle_data.get("familia_profesional", "Informática y Comunicaciones")
        curso = str(mod_data.get("curso_orientativo", "1º"))
        ects = str(mod_data.get("creditos_ects", 8))
        profesor = context_meta.get("profesor", "Profesorado del Departamento de Informática")
        centro = context_meta.get("centro", "IES Benigasló")
        curso_acad = context_meta.get("curso_academico", "2026 / 2027")
        normativa = cycle_data.get("normativa_referencia", "Normativa de referencia oficial del título")
        nivel = cycle_data.get("nivel", "Grado Superior")
        codigo_ciclo = str(cycle_data.get("codigo_ciclo", "")).strip()
        horas = str(mod_data.get("horas", "")).strip()

        orientaciones = str(mod_data.get("orientaciones_pedagogicas", "")).strip()

        ras = mod_data.get("resultados_aprendizaje", [])
        mod_ucs = mod_data.get("unidades_competencia", [])
        all_ucs = cycle_data.get("unidades_competencia", {})
        cualif_list = cycle_data.get("cualificaciones_profesionales", [])
        all_comps = cycle_data.get("competencias_profesionales_personales_sociales", {})
        mod_comps = mod_data.get("competencias_titulo", [])

        # Texto de acreditación oficial
        if mod_ucs:
            acred_list = []
            for uc in mod_ucs:
                desc = all_ucs.get(uc, "")
                acred_list.append(f"{uc} ({desc})" if desc else uc)
            acreditacion_text = "; ".join(acred_list) + "."
        else:
            acreditacion_text = "Módulo profesional de carácter complementario / transversal; no acredita directamente Unidades de Competencia del Catálogo Nacional (CNCP)."

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
                        cualif_str = " / ".join(cualifs) if cualifs else "Cualificación de referencia del Catálogo Nacional"
                        new_r = copy.deepcopy(tmpl_row)
                        self._replace_in_element(new_r, {
                            "{{uc}}": f"{uc}: {uc_desc}" if uc_desc else uc,
                            "{{ifc}}": cualif_str
                        })
                        t_ucs.append(new_r)
                else:
                    new_r = copy.deepcopy(tmpl_row)
                    self._replace_in_element(new_r, {
                        "{{uc}}": "Sin acreditación directa de Unidades de Competencia",
                        "{{ifc}}": "Módulo formativo transversal / complementario"
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
                desc = all_comps.get(letra, "Descripción de la competencia en el currículo oficial")
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
                            "{{inst_nombre}}": "Pruebas teórico-prácticas y proyectos de laboratorio",
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
            parent = body
            idx_p = list(parent).index(p_context_tmpl)
            parent.remove(p_context_tmpl)
            insert_idx = idx_p

            if orientaciones:
                raw_paras = [p.strip() for p in orientaciones.split("\n") if p.strip()]
            else:
                raw_paras = [
                    f"La formación del módulo profesional de {mod_name} capacita al alumnado para desempeñar con "
                    f"solvencia las funciones técnicas, organizativas y operativas asociadas al perfil laboral del título, "
                    f"garantizando la calidad, seguridad y cumplimiento de los estándares del sector profesional."
                ]

            for raw_para in raw_paras:
                clean_p = raw_para.strip()
                is_bullet = False
                if clean_p.startswith(("−", "-", "•", "*", "–", "·")):
                    is_bullet = True
                    clean_p = clean_p.lstrip("−-•*–· ").strip()
                elif re.match(r'^[a-zñ]\)\s+', clean_p):
                    is_bullet = True

                new_p = ET.Element('{urn:oasis:names:tc:opendocument:xmlns:text:1.0}p')
                if is_bullet:
                    new_p.attrib['{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name'] = 'P20'
                    new_p.text = f"• {clean_p}"
                else:
                    new_p.attrib['{urn:oasis:names:tc:opendocument:xmlns:text:1.0}style-name'] = 'P14'
                    new_p.text = clean_p

                parent.insert(insert_idx, new_p)
                insert_idx += 1

        # --- 8. REEMPLAZO GLOBAL DE PLACEHOLDERS EN TODO EL DOCUMENTO ---
        sw_list = [f"• Software técnico: {sw}" for sw in ped_info.get("recursos_software", [])]
        hw_list = [f"• Hardware e instrumental: {hw}" for hw in ped_info.get("recursos_hardware", [])]
        recursos_text = "\n".join(sw_list + hw_list)
        
        if f"({ciclo_code})" in ciclo_title:
            ciclo_full_title = ciclo_title
        else:
            ciclo_full_title = f"{ciclo_title} ({ciclo_code})"
        if codigo_ciclo and codigo_ciclo not in ciclo_full_title:
            ciclo_full_title += f" (Código: {codigo_ciclo})"

        global_vars = {
            "{{modulo}}": f"{mod_code} - {mod_name}",
            "{{codigo_modulo}}": mod_code,
            "{{nombre_modulo}}": mod_name,
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
            "{{recursos_especificos}}": recursos_text,
            "{{espacios_especificos}}": ped_info.get("espacios", ""),
            "{{formula_evaluacion}}": ped_info.get("formula_evaluacion", "")
        }

        self._replace_in_element(root, global_vars)

        # Empaquetar exclusivamente archivo .odt
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


# ==============================================================================
# NOMENCLATURA ESTÁNDAR Y GENERADOR DE SIGLAS DE MÓDULOS
# ==============================================================================

KNOWN_MODULE_INITIALS = {
    # DAM
    "0483": "SI",       # Sistemas informáticos
    "0484": "BD",       # Bases de datos
    "0485": "PROG",     # Programación
    "0373": "LMSGI",    # Lenguajes de marcas y sistemas de gestión de información
    "0487": "ED",       # Entornos de desarrollo
    "0486": "AD",       # Acceso a datos
    "0488": "DI",       # Desarrollo de interfaces
    "0489": "PMYDM",    # Programación multimedia y dispositivos móviles
    "0490": "PSP",      # Programación de servicios y procesos
    "0491": "SGE",      # Sistemas de gestión empresarial
    "0492": "PROY",     # Proyecto DAM

    # DAW
    "0612": "DWEC",     # Desarrollo web en entorno cliente
    "0613": "DWES",     # Desarrollo web en entorno servidor
    "0614": "DAW",      # Despliegue de aplicaciones web
    "0615": "DIW",      # Diseño de interfaces web
    "0616": "PROY",     # Proyecto DAW

    # SMX
    "0221": "MME",      # Montaje y mantenimiento de equipos
    "0222": "SOM",      # Sistemas operativos monopuesto
    "0223": "AO",       # Aplicaciones ofimáticas
    "0224": "SOR",      # Sistemas operativos en red
    "0225": "RL",       # Redes locales
    "0226": "SI",       # Seguridad informática
    "0227": "SER",      # Servicios en red
    "0228": "AW",       # Aplicaciones web
    "0229": "FOL",      # Formación y orientación laboral
    "0230": "EIE",      # Empresa e iniciativa emprendedora
    "0231": "FCT",      # Formación en centros de trabajo
}

def get_module_initials(mod_code: str, mod_name: str) -> str:
    clean_code = str(mod_code).zfill(4)
    if clean_code in KNOWN_MODULE_INITIALS:
        return KNOWN_MODULE_INITIALS[clean_code]
        
    words = re.findall(r'[a-zA-Z0-9áéíóúÁÉÍÓÚñÑüÜ]+', mod_name)
    stopwords = {'de', 'del', 'en', 'la', 'el', 'los', 'las', 'a', 'para', 'por', 'sobre', 'con'}
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
    curso_academico: str = "2026 / 2027"
) -> str:
    """
    Genera el nombre estándar de archivo:
    PD_{curso_escolar}_{ciclo}{curso}_{codigo}_{iniciales}.odt
    Ejemplo: PD_26-27_DAM2_0489_PMYDM.odt
    """
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

    # 4. Iniciales del módulo
    initials = get_module_initials(code_str, mod_name)

    return f"PD_{curso_esc}_{ciclo_curso}_{code_str}_{initials}.odt"


# ==============================================================================
# ORQUESTADOR SISTEMÁTICO DE GENERACIÓN
# ==============================================================================

class SystematicProgramacionGenerator:
    """
    Genera sistemáticamente las programaciones didácticas a partir de plantilla.fodt
    para todos los módulos de todos los ciclos formativos.
    """
    def __init__(self, base_dir: str = "."):
        self.base_dir = base_dir
        self.repo = CurriculumRepository(base_dir)
        self.ped_provider = PedagogicalDataProvider(os.path.join(base_dir, "pedagogia_modulos.json"))
        self.engine = FodtTemplateEngine(os.path.join(base_dir, "plantilla.fodt"))

    def generate_all(
        self,
        output_dir: str = "programaciones",
        curso_academico: str = "2026 / 2027"
    ) -> List[Tuple[str, str, str]]:
        generated = []
        for ciclo_code in self.repo.get_all_cycles().keys():
            res = self.generate_cycle(ciclo_code, output_dir=output_dir, curso_academico=curso_academico)
            generated.extend(res)
        return generated

    def generate_cycle(
        self,
        ciclo_code: str,
        output_dir: str = "programaciones",
        curso_academico: str = "2026 / 2027"
    ) -> List[Tuple[str, str, str]]:
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
            mod_curso = mod.get("curso_orientativo", "1º")

            filename = get_pd_filename(
                ciclo=ciclo_code,
                curso=mod_curso,
                mod_code=mod_code,
                mod_name=mod_name,
                curso_academico=curso_academico
            )
            odt_path = os.path.join(c_dir, filename)

            ped_info = self.ped_provider.get_pedagogical_data(mod_code, mod)
            context_meta = {
                "ciclo": ciclo_code.upper(),
                "profesor": "Profesorado del Departamento de Informática",
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
        curso_academico: str = "2026 / 2027"
    ) -> str:
        result = self.repo.get_module(ciclo, identifier)
        if not result:
            raise ValueError(f"No se encontró el módulo '{identifier}' en el repositorio de currículos.")
        mod_data, cycle_data = result
        c_code = cycle_data.get("ciclo", "FP").upper()
        mod_code = str(mod_data.get("codigo", "")).zfill(4)
        mod_name = mod_data.get("nombre", "")
        mod_curso = mod_data.get("curso_orientativo", "1º")

        if output_filepath:
            base_name, ext = os.path.splitext(output_filepath)
            odt_path = f"{base_name}.odt" if ext.lower() != ".odt" else output_filepath
        else:
            c_dir = os.path.join("programaciones", c_code)
            os.makedirs(c_dir, exist_ok=True)
            filename = get_pd_filename(
                ciclo=c_code,
                curso=mod_curso,
                mod_code=mod_code,
                mod_name=mod_name,
                curso_academico=curso_academico
            )
            odt_path = os.path.join(c_dir, filename)

        ped_info = self.ped_provider.get_pedagogical_data(mod_code, mod_data)
        context_meta = {
            "ciclo": c_code,
            "profesor": "Profesorado del Departamento de Informática",
            "curso_academico": curso_academico
        }

        self.engine.render_and_save(odt_path, mod_data, cycle_data, ped_info, context_meta)
        return odt_path


# ==============================================================================
# PUNTO DE ENTRADA CLI
# ==============================================================================

def main():
    parser = argparse.ArgumentParser(
        description="Generador sistemático de Programaciones Didácticas FP en formato nativo ODT (.odt)."
    )
    parser.add_argument(
        "--all",
        action="store_true",
        help="Generar sistemáticamente todos los módulos de todos los ciclos formativos disponibles."
    )
    parser.add_argument(
        "--ciclo",
        type=str,
        help="Generar todos los módulos del ciclo formativo especificado (ej. SMX, DAM, DAW)."
    )
    parser.add_argument(
        "--modulo",
        type=str,
        help="Generar un módulo específico por código numérico o nombre (ej. 0221, 0489)."
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="Ruta de archivo .odt de salida personalizada (aplicable junto con --modulo)."
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="programaciones",
        help="Directorio raíz de salida (por defecto: 'programaciones')."
    )
    parser.add_argument(
        "--curso-academico", "--curso-escolar",
        type=str,
        default="2026 / 2027",
        help="Curso escolar / académico de las programaciones (por defecto: '2026 / 2027')."
    )

    args = parser.parse_args()
    systematic_gen = SystematicProgramacionGenerator(".")

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
