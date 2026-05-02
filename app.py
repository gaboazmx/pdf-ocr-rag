"""
=============================================================
PDF OCR → Markdown  |  Sistema RAG Jurídico
Gabriel Aranda Zamacona — Despacho Legal
=============================================================
Convierte PDFs escaneados (imágenes) a Markdown limpio
usando OCR (Tesseract) listo para indexar en el corpus RAG.
=============================================================
"""

import os
import uuid
import time
import threading
from datetime import datetime
from pathlib import Path

from flask import Flask, request, jsonify, send_file, render_template, abort
from werkzeug.utils import secure_filename
import pytesseract
from pdf2image import convert_from_path
from PIL import Image

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 100 * 1024 * 1024  # 100 MB max

# ── CARPETAS ──────────────────────────────────────────────────────
UPLOAD_DIR = Path("/tmp/ocr_uploads")
OUTPUT_DIR = Path("/tmp/ocr_outputs")
UPLOAD_DIR.mkdir(exist_ok=True)
OUTPUT_DIR.mkdir(exist_ok=True)

# ── CATEGORÍAS DEL CORPUS RAG (24) ───────────────────────────────
CATEGORIAS = [
    ("0 Casos",                    "0 Casos — Expedientes propios"),
    ("001 Reformas",               "001 Reformas — DOF"),
    ("01 Contencioso",             "01 Contencioso Administrativo — LFPCA / TFJA"),
    ("01-1 IMSS",                  "01-1 IMSS — LSS, circulares"),
    ("01-2 INFONAVIT",             "01-2 INFONAVIT — LIV, reglamentos"),
    ("01-3 STPS",                  "01-3 STPS — LFT, normas oficiales"),
    ("03 Seguridad Social",        "03 Seguridad Social — LFSS, jurisprudencia"),
    ("03-1 Pensiones",             "03-1 Pensiones — IMSS / ISSSTE"),
    ("04 Derecho Laboral",         "04 Derecho Laboral — LFT, jurisprudencia"),
    ("04-1 REPSE",                 "04-1 REPSE y Subcontratación"),
    ("04-2 Compliance Laboral",    "04-2 Compliance Laboral"),
    ("05 CFF",                     "05 CFF — Código Fiscal"),
    ("05-1 Compliance Tributario", "05-1 Compliance Tributario — ISO/UNE"),
    ("05-2 RMF",                   "05-2 RMF — Resolución Miscelánea Fiscal"),
    ("06 Corporativo",             "06 Derecho Corporativo — LGSM, contratos"),
    ("07 Capacitacion",            "07 Capacitación — Materiales y libros"),
    ("08 Fiscalizacion",           "08 Fiscalización Algorítmica"),
    ("X Doctrina",                 "X Doctrina y Libros — Monografías"),
    ("X-1 Normas Compliance",      "X-1 Normas Compliance — ISO 37001/37301"),
    ("Y Precedentes",              "Y Precedentes — Tesis SCJN / TCC"),
    ("Z Legislacion",              "Z Legislación — Leyes, códigos, CPEUM"),
    ("Z-1 Renta",                  "Z-1 Renta — ISR, LISR"),
    ("ZZ Valores Economicos",      "ZZ Valores Económicos Anuales"),
    ("Metodologia Riesgos",        "Metodología de Riesgos"),
]

# ── DICCIONARIO DE TAREAS EN PROGRESO ─────────────────────────────
tareas: dict[str, dict] = {}
tareas_lock = threading.Lock()


# ── LIMPIEZA AUTOMÁTICA (archivos > 1 hora) ───────────────────────
def limpiar_archivos_viejos():
    limite = time.time() - 3600
    for carpeta in (UPLOAD_DIR, OUTPUT_DIR):
        for archivo in carpeta.iterdir():
            if archivo.is_file() and archivo.stat().st_mtime < limite:
                try:
                    archivo.unlink()
                except Exception:
                    pass


# ── OCR EN HILO SEPARADO ──────────────────────────────────────────
def procesar_ocr(task_id: str, pdf_path: Path, categoria: str,
                 idioma: str, dpi: int):
    """Ejecuta OCR y genera el archivo Markdown.

    Estrategia de memoria: convierte UNA página a la vez escribiendo
    en disco (output_folder), hace OCR y libera la imagen de inmediato.
    Esto mantiene el uso de RAM bajo ~100 MB incluso en PDFs de 300 páginas.
    """
    import tempfile
    import gc

    with tareas_lock:
        tareas[task_id]["estado"] = "procesando"
        tareas[task_id]["progreso"] = 5

    try:
        # 1. Contar páginas primero (sin cargar imágenes)
        with tareas_lock:
            tareas[task_id]["mensaje"] = "Contando páginas..."
            tareas[task_id]["progreso"] = 8

        import fitz  # PyMuPDF — solo para contar páginas
        doc = fitz.open(str(pdf_path))
        total = doc.page_count
        doc.close()

        with tareas_lock:
            tareas[task_id]["total_paginas"] = total
            tareas[task_id]["mensaje"] = f"Iniciando OCR en {total} páginas..."
            tareas[task_id]["progreso"] = 10

        # 2. OCR página por página — una a la vez para ahorrar RAM
        textos = []
        lang_code = _idioma_code(idioma)

        with tempfile.TemporaryDirectory() as tmpdir:
            for i in range(1, total + 1):
                with tareas_lock:
                    tareas[task_id]["pagina_actual"] = i
                    tareas[task_id]["progreso"] = 10 + int(80 * i / total)
                    tareas[task_id]["mensaje"] = f"OCR: página {i}/{total}"

                # Convertir SOLO esta página a imagen (en disco)
                imgs = convert_from_path(
                    str(pdf_path),
                    dpi=dpi,
                    fmt="jpeg",
                    first_page=i,
                    last_page=i,
                    output_folder=tmpdir,
                    thread_count=1,
                    use_pdftocairo=True,
                )
                if not imgs:
                    textos.append("")
                    continue

                img = imgs[0].convert("L")  # escala de grises
                texto = pytesseract.image_to_string(img, lang=lang_code)
                textos.append(texto.strip())

                # Liberar memoria inmediatamente
                del img, imgs
                gc.collect()

        # 3. Construir Markdown con metadata YAML
        with tareas_lock:
            tareas[task_id]["progreso"] = 93
            tareas[task_id]["mensaje"] = "Generando Markdown..."

        nombre_base = pdf_path.stem
        fecha = datetime.now().strftime("%Y-%m-%d")

        md_lines = [
            "---",
            f"fuente: {nombre_base}",
            f"categoria: {categoria}",
            f"paginas: {total}",
            f"idioma_ocr: {idioma}",
            f"dpi: {dpi}",
            f"fecha: {fecha}",
            f"metodo: ocr-tesseract",
            "---",
            "",
        ]

        for i, texto in enumerate(textos, 1):
            if texto:
                md_lines.append(f"## Página {i}")
                md_lines.append("")
                # Detectar encabezados jurídicos básicos
                for linea in texto.split("\n"):
                    linea_stripped = linea.strip()
                    md_lines.append(_convertir_linea(linea_stripped))
                md_lines.append("")

        contenido_md = "\n".join(md_lines)

        # 4. Guardar .md
        out_name = _nombre_limpio(nombre_base) + ".md"
        out_path = OUTPUT_DIR / f"{task_id}_{out_name}"
        out_path.write_text(contenido_md, encoding="utf-8")

        with tareas_lock:
            tareas[task_id]["estado"] = "listo"
            tareas[task_id]["progreso"] = 100
            tareas[task_id]["mensaje"] = "¡Listo!"
            tareas[task_id]["archivo_md"] = out_path.name
            tareas[task_id]["nombre_descarga"] = out_name
            tareas[task_id]["caracteres"] = len(contenido_md)

    except Exception as e:
        with tareas_lock:
            tareas[task_id]["estado"] = "error"
            tareas[task_id]["mensaje"] = f"Error: {str(e)}"

    finally:
        # Borrar el PDF temporal
        try:
            pdf_path.unlink(missing_ok=True)
        except Exception:
            pass


def _idioma_code(idioma: str) -> str:
    mapa = {
        "español": "spa",
        "inglés": "eng",
        "español + inglés": "spa+eng",
        "francés": "fra",
        "portugués": "por",
    }
    return mapa.get(idioma, "spa+eng")


def _convertir_linea(linea: str) -> str:
    """Convierte encabezados jurídicos reconocidos a Markdown."""
    prefijos = [
        ("ARTÍCULO ", "### "),
        ("Artículo ", "### "),
        ("ARTICULO ", "### "),
        ("FRACCIÓN ", "#### "),
        ("Fracción ", "#### "),
        ("CAPÍTULO ", "## "),
        ("Capítulo ", "## "),
        ("TÍTULO ", "# "),
        ("Título ", "# "),
        ("SECCIÓN ", "## "),
        ("Sección ", "## "),
    ]
    for prefijo, md_head in prefijos:
        if linea.startswith(prefijo):
            return f"{md_head}{linea}"
    return linea


def _nombre_limpio(nombre: str) -> str:
    """Convierte nombre a snake_case seguro para filesystem."""
    import re
    nombre = nombre.replace(" ", "_")
    nombre = re.sub(r"[^\w\-]", "", nombre)
    return nombre[:80]  # máximo 80 chars


# ── RUTAS FLASK ───────────────────────────────────────────────────

@app.route("/")
def index():
    return render_template("index.html", categorias=CATEGORIAS)


@app.route("/upload", methods=["POST"])
def upload():
    limpiar_archivos_viejos()

    if "pdf" not in request.files:
        return jsonify({"error": "No se recibió ningún archivo PDF"}), 400

    f = request.files["pdf"]
    if not f.filename:
        return jsonify({"error": "Nombre de archivo vacío"}), 400

    ext = Path(f.filename).suffix.lower()
    if ext != ".pdf":
        return jsonify({"error": "Solo se aceptan archivos PDF"}), 400

    categoria  = request.form.get("categoria", "Z Legislacion")
    idioma     = request.form.get("idioma", "español + inglés")
    dpi        = int(request.form.get("dpi", 300))
    if dpi not in (150, 200, 300, 400):
        dpi = 300

    task_id  = str(uuid.uuid4())
    filename = secure_filename(f.filename)
    pdf_path = UPLOAD_DIR / f"{task_id}_{filename}"
    f.save(str(pdf_path))

    with tareas_lock:
        tareas[task_id] = {
            "estado":         "encolado",
            "progreso":       0,
            "mensaje":        "En cola...",
            "pagina_actual":  0,
            "total_paginas":  0,
            "archivo_md":     None,
            "nombre_descarga": None,
            "caracteres":     0,
        }

    hilo = threading.Thread(
        target=procesar_ocr,
        args=(task_id, pdf_path, categoria, idioma, dpi),
        daemon=True,
    )
    hilo.start()

    return jsonify({"task_id": task_id})


@app.route("/status/<task_id>")
def status(task_id: str):
    with tareas_lock:
        tarea = tareas.get(task_id)
    if not tarea:
        abort(404)
    return jsonify(tarea)


@app.route("/download/<task_id>")
def download(task_id: str):
    with tareas_lock:
        tarea = tareas.get(task_id)
    if not tarea or tarea.get("estado") != "listo":
        abort(404)

    out_path = OUTPUT_DIR / tarea["archivo_md"]
    if not out_path.exists():
        abort(404)

    return send_file(
        str(out_path),
        as_attachment=True,
        download_name=tarea["nombre_descarga"],
        mimetype="text/markdown",
    )


@app.route("/ping")
def ping():
    return jsonify({"ok": True, "ts": datetime.now().isoformat()})


# ── MAIN ──────────────────────────────────────────────────────────
if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port, debug=False)
