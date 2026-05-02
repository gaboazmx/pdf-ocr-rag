# PDF OCR → Markdown | RAG Jurídico

**Convierte PDFs escaneados a Markdown limpio usando OCR (Tesseract), listo para indexar en el corpus RAG jurídico.**

🔗 **App en vivo:** https://pdf-ocr-rag.onrender.com *(se actualiza tras el deploy)*

---

## ¿Para qué sirve?

Complementa a [pdf2md](https://gaboazmx.github.io/pdf2md/) para los PDFs que **no tienen texto seleccionable** (escaneados, fotografiados, fotocopiados).

| App | Tipo de PDF | Tecnología |
|-----|-------------|-----------|
| [pdf2md](https://gaboazmx.github.io/pdf2md/) | Con texto seleccionable | PDF.js (navegador) |
| **Esta app** | Escaneados / imagen | Tesseract OCR (servidor) |

El flujo completo:
```
PDF escaneado  →  [esta app]  →  .md  →  corpus\categoria\  →  python indexar.py  →  RAG consultable
```

---

## Características

- **Drag & drop** de PDF escaneado
- **OCR con Tesseract** — Español + Inglés incluidos
- **Selector de idioma** — Español, Inglés, Francés, Portugués
- **DPI configurable** — 150 / 200 / 300 / 400 dpi
- **24 categorías del corpus RAG** preconfiguradas
- **Metadatos YAML** automáticos (fuente, categoría, páginas, fecha, método)
- **Detección de encabezados jurídicos** — ARTÍCULO, CAPÍTULO, TÍTULO → Markdown
- **Barra de progreso** en tiempo real página por página
- **Descarga .md** directa

---

## Tecnología

- **Backend**: Flask + Gunicorn
- **OCR**: pytesseract + Tesseract OCR (instalado en el contenedor Docker)
- **PDF → imágenes**: pdf2image + Poppler
- **Deploy**: Docker en Render.com (plan gratuito)

---

## Deploy en Render

1. Fork este repositorio
2. Ve a [render.com](https://render.com) → New → Web Service
3. Conecta el repositorio GitHub
4. Render detecta el `render.yaml` automáticamente
5. Deploy → esperar ~5 min (Tesseract tarda en instalar)
6. URL disponible en el dashboard de Render

---

## Limitaciones

- PDFs de hasta **100 MB**
- Calidad del OCR depende de la resolución y limpieza del original
- El plan gratuito de Render puede tener latencia en el primer request (cold start ~30 seg)
- Los archivos se eliminan del servidor después de **1 hora**

---

## Integración con el Sistema RAG

1. Descargar el `.md` generado
2. Copiar a la carpeta de corpus:
   ```
   C:\Users\gabri\Dropbox\gabriel_rag\corpus\[categoria]\
   ```
3. Indexar:
   ```powershell
   cd C:\Users\gabri\Dropbox\gabriel_rag
   python indexar.py --cat "[categoria]"
   ```

---

## Autor

**Gabriel Aranda Zamacona**  
Abogado Corporativo · Litigante Contencioso Administrativo Federal · Estratega Legal con IA

*Despacho Gabriel Aranda Zamacona — Mayo 2026*
