/*
 * Genera los entregables en Word (docs/word/*.docx) a partir de los archivos Markdown del proyecto.
 * Así el Word y el repositorio dicen siempre lo mismo.
 *
 * Uso (desde la carpeta herramientas):
 *     npm install        (solo la primera vez)
 *     node generar_word.js          (todos)
 *     node generar_word.js 02 03    (solo esos; útil si alguien editó otro Word a mano)
 *
 * Ojo: 01_DECISIONES.docx fue editado a mano por el equipo; regenerarlo reemplaza esos cambios
 * con el contenido de DECISIONES.md.
 */
const fs = require("fs");
const path = require("path");
const {
  Document, Packer, Paragraph, TextRun, HeadingLevel, Table, TableRow, TableCell, WidthType,
  ShadingType, BorderStyle, AlignmentType, ImageRun, ExternalHyperlink, LevelFormat, Footer,
  PageNumber, PageBreak, TableLayoutType,
} = require("docx");
const JSZip = require("jszip");   // viene instalado junto con docx

const RAIZ = path.resolve(__dirname, "..");
const SALIDA = path.join(RAIZ, "docs", "word");
const ANCHO = 9026;                 // A4 con márgenes de 1" (DXA)
const ANCHO_PX = 600;               // ancho máximo de imágenes
const AZUL = "0D6B8A", OSCURO = "0B2E3D", GRIS = "556675";
const FUENTE = "Calibri";

const DOCUMENTOS = [
  { md: "DECISIONES.md", docx: "01_DECISIONES.docx", titulo: "DECISIONES",
    subtitulo: "Qué se decidió ante cada preocupación de la clienta, dónde está en el código y cómo se prueba" },
  { md: "INSTALACION.md", docx: "02_INSTRUCCIONES_DE_USO.docx", titulo: "Instrucciones de uso",
    subtitulo: "Instalación en un equipo nuevo y prueba del sistema en 5 minutos" },
  { md: "docs/MANUAL_USUARIO.md", docx: "03_MANUAL_DE_USUARIO.docx", titulo: "Manual de usuario",
    subtitulo: "Guía paso a paso para recepcionistas, médicos y administración" },
  { md: "docs/DIAGRAMA_ENTIDAD_RELACION.md", docx: "04_DIAGRAMA_ENTIDAD_RELACION.docx", titulo: "Diagrama entidad-relación",
    subtitulo: "Modelo de datos, diccionario y relaciones de la base ClinAgenda" },
];

// ------------------------------------------------------------------ texto en línea
function enLinea(texto, base = {}) {
  // Soporta **negrita**, `código`, [enlace](url) y <br>
  const partes = [];
  const re = /(\*\*[^*]+\*\*|\*[^*\s][^*]*\*|`[^`]+`|\[[^\]]+\]\([^)]+\)|<br\s*\/?>)/g;
  let ultimo = 0, m;
  const plano = (t) => t && partes.push(new TextRun({ text: t, ...base }));
  while ((m = re.exec(texto))) {
    plano(texto.slice(ultimo, m.index));
    const tok = m[0];
    if (tok.startsWith("**")) {
      partes.push(...enLinea(tok.slice(2, -2), { ...base, bold: true }));
    } else if (tok.startsWith("*")) {
      partes.push(...enLinea(tok.slice(1, -1), { ...base, italics: true }));
    } else if (tok.startsWith("`")) {
      partes.push(new TextRun({ text: tok.slice(1, -1), ...base, font: "Consolas", size: (base.size || 22) - 2,
                                color: "8A2D0B", shading: { type: ShadingType.CLEAR, fill: "F1F4F7", color: "auto" } }));
    } else if (tok.startsWith("<br")) {
      partes.push(new TextRun({ text: "", break: 1 }));
    } else {
      const [, txt, url] = tok.match(/\[([^\]]+)\]\(([^)]+)\)/);
      if (/^https?:/.test(url)) {
        partes.push(new ExternalHyperlink({ link: url, children: [new TextRun({ text: txt, ...base, color: AZUL, underline: {} })] }));
      } else {
        partes.push(...enLinea(txt, { ...base, color: AZUL }));   // enlaces internos: solo el texto
      }
    }
    ultimo = m.index + tok.length;
  }
  plano(texto.slice(ultimo));
  return partes;
}

// ------------------------------------------------------------------ imágenes
function tamanoImagen(buf) {
  if (buf[0] === 0x89) return { w: buf.readUInt32BE(16), h: buf.readUInt32BE(20), tipo: "png" };
  let i = 2;                                   // JPEG: buscar marcador SOF
  while (i < buf.length) {
    const marca = buf[i + 1], largo = buf.readUInt16BE(i + 2);
    if (marca >= 0xc0 && marca <= 0xcf && ![0xc4, 0xc8, 0xcc].includes(marca)) {
      return { h: buf.readUInt16BE(i + 5), w: buf.readUInt16BE(i + 7), tipo: "jpg" };
    }
    i += 2 + largo;
  }
  throw new Error("Imagen no reconocida");
}

function imagen(rutaRel, carpetaMd, anchoMax = ANCHO_PX, alt = "") {
  let ruta = path.resolve(carpetaMd, rutaRel);
  if (ruta.endsWith(".svg")) ruta = ruta.replace(/\.svg$/, ".png");   // Word no muestra bien SVG
  const buf = fs.readFileSync(ruta);
  const { w, h, tipo } = tamanoImagen(buf);
  const ancho = Math.min(anchoMax, w), alto = Math.round(h * ancho / w);
  const parrafos = [new Paragraph({ alignment: AlignmentType.CENTER, spacing: { before: 120, after: 60 },
    children: [new ImageRun({ type: tipo, data: buf, transformation: { width: ancho, height: alto },
                              altText: { title: alt, description: alt, name: alt || "imagen" } })] })];
  if (alt) parrafos.push(new Paragraph({ alignment: AlignmentType.CENTER, spacing: { after: 200 },
    children: [new TextRun({ text: alt, italics: true, size: 18, color: GRIS })] }));
  return parrafos;
}

// ------------------------------------------------------------------ tablas
function tabla(filas) {
  const celdas = filas.map((f) => f.replace(/^\||\|$/g, "").split(/(?<!\\)\|/).map((c) => c.trim()));
  const n = celdas[0].length;
  const largo = Array(n).fill(4);
  celdas.forEach((f) => f.forEach((c, i) => { largo[i] = Math.max(largo[i], Math.min(c.replace(/[`*]/g, "").length, 60)); }));
  const total = largo.reduce((a, b) => a + b, 0);
  let anchos = largo.map((l) => Math.max(900, Math.round(ANCHO * l / total)));
  const ajuste = ANCHO - anchos.reduce((a, b) => a + b, 0);
  anchos[anchos.indexOf(Math.max(...anchos))] += ajuste;
  const borde = { style: BorderStyle.SINGLE, size: 4, color: "C3CFDA" };
  return new Table({
    width: { size: ANCHO, type: WidthType.DXA }, columnWidths: anchos, layout: TableLayoutType.FIXED,
    borders: { top: borde, bottom: borde, left: borde, right: borde, insideHorizontal: borde, insideVertical: borde },
    rows: celdas.map((f, r) => new TableRow({
      tableHeader: r === 0,
      children: f.map((c, i) => new TableCell({
        width: { size: anchos[i], type: WidthType.DXA },
        margins: { top: 70, bottom: 70, left: 100, right: 100 },
        shading: r === 0 ? { type: ShadingType.CLEAR, fill: OSCURO, color: "auto" }
               : (r % 2 === 0 ? { type: ShadingType.CLEAR, fill: "F5F8FA", color: "auto" } : undefined),
        children: [new Paragraph({ spacing: { before: 0, after: 0 },
          children: enLinea(c.replace(/\\\|/g, "|"), r === 0 ? { bold: true, color: "FFFFFF", size: 20 } : { size: 20 }) })],
      })),
    })),
  });
}

// ------------------------------------------------------------------ markdown → bloques
function convertir(md, carpetaMd) {
  const lineas = md.replace(/\r/g, "").split("\n");
  const bloques = [];
  let i = 0, primerTitulo = true;
  // En Word todas las listas numeradas comparten contador: cada lista nueva usa su propia "instancia"
  // para volver a empezar en 1. El contenido sangrado (texto, código, tablas) dentro de un paso no corta la lista.
  let instancia = 0, enListaNum = false;
  while (i < lineas.length) {
    const l = lineas[i];
    const esItem = /^(\s*)([-*]|\d+\.) /.test(l);
    const sangrado = /^\s{2,}\S/.test(l);
    if (l.trim() && !esItem && !sangrado) enListaNum = false;
    if (/^\s*```/.test(l)) {                                // bloque de código (puede estar sangrado)
      const sangria = l.match(/^\s*/)[0].length; const lenguaje = l.trim().slice(3).trim(); const cod = [];
      i++;
      while (i < lineas.length && !/^\s*```/.test(lineas[i])) cod.push(lineas[i++].slice(sangria));
      i++;
      if (lenguaje === "mermaid") {
        bloques.push(new Paragraph({ spacing: { after: 120 }, children: [new TextRun({ text:
          "(El código Mermaid de este diagrama está en el repositorio: docs/DIAGRAMA_ENTIDAD_RELACION.md. "
          + "Arriba se muestra la imagen equivalente.)", italics: true, color: GRIS, size: 20 })] }));
        continue;
      }
      cod.forEach((c, k) => bloques.push(new Paragraph({
        spacing: { before: k === 0 ? 80 : 0, after: k === cod.length - 1 ? 160 : 0 },
        shading: { type: ShadingType.CLEAR, fill: "F1F4F7", color: "auto" }, indent: { left: 200, right: 200 },
        children: [new TextRun({ text: c || " ", font: "Consolas", size: 18 })] })));
      continue;
    }
    if (/^#{1,4} /.test(l)) {                               // títulos
      const nivel = l.match(/^#+/)[0].length;
      const texto = l.replace(/^#+ /, "");
      if (nivel === 1 && primerTitulo) { primerTitulo = false; i++; continue; }   // ya está en la portada
      bloques.push(new Paragraph({ heading: [HeadingLevel.HEADING_1, HeadingLevel.HEADING_1, HeadingLevel.HEADING_2,
                                            HeadingLevel.HEADING_3][nivel - 1] || HeadingLevel.HEADING_3,
                                   children: enLinea(texto) }));
      i++; continue;
    }
    if (/^---\s*$/.test(l)) {                               // separador
      bloques.push(new Paragraph({ spacing: { before: 120, after: 120 },
        border: { bottom: { style: BorderStyle.SINGLE, size: 6, color: "DDE4EB", space: 1 } }, children: [] }));
      i++; continue;
    }
    if (/^\s*\|/.test(l)) {                                 // tabla (puede estar sangrada)
      const filas = [];
      while (i < lineas.length && /^\s*\|/.test(lineas[i])) {
        if (!/^\|[\s:|-]+\|$/.test(lineas[i].trim())) filas.push(lineas[i].trim());
        i++;
      }
      bloques.push(tabla(filas), new Paragraph({ spacing: { after: 120 }, children: [] }));
      continue;
    }
    let m = l.match(/^\s*!\[([^\]]*)\]\(([^)]+)\)\s*$/);    // imagen markdown
    if (m) { bloques.push(...imagen(m[2], carpetaMd, ANCHO_PX, m[1])); i++; continue; }
    m = l.match(/<img src="([^"]+)" alt="([^"]*)"(?: width="(\d+)")?/);   // imagen html
    if (m) { bloques.push(...imagen(m[1], carpetaMd, m[3] ? Number(m[3]) : ANCHO_PX, m[2])); i++; continue; }
    if (/^>/.test(l)) {                                     // nota
      const texto = [];
      while (i < lineas.length && /^>/.test(lineas[i])) texto.push(lineas[i++].replace(/^>\s?/, ""));
      bloques.push(new Paragraph({ spacing: { before: 120, after: 160 }, indent: { left: 280 },
        shading: { type: ShadingType.CLEAR, fill: "E6F2F7", color: "auto" },
        border: { left: { style: BorderStyle.SINGLE, size: 18, color: AZUL, space: 8 } },
        children: enLinea(texto.join(" "), { size: 21 }) }));
      continue;
    }
    m = l.match(/^(\s*)([-*]|\d+\.) (.*)$/);                // listas
    if (m) {
      const nivel = Math.min(Math.floor(m[1].length / 2), 2);
      const numerada = /\d+\./.test(m[2]);
      // Se reinicia solo cuando el paso es "1." (así una lista cortada por una imagen sigue en 4, 5...)
      if (numerada && nivel === 0 && (m[2] === "1." || instancia === 0)) instancia++;
      if (numerada && nivel === 0) enListaNum = true;
      if (!numerada && nivel === 0) enListaNum = false;
      bloques.push(new Paragraph({ numbering: numerada ? { reference: "numeros", level: nivel, instance: instancia }
                                                       : { reference: "vinetas", level: nivel },
        spacing: { after: 60 }, children: enLinea(m[3]) }));
      i++; continue;
    }
    if (!l.trim()) { i++; continue; }
    const texto = [l.trim()];                               // párrafo (une líneas seguidas)
    i++;
    while (i < lineas.length && lineas[i].trim() && !/^(#|\s*\||\s*```|>|\s*([-*]|\d+\.) |---|!\[|<img)/.test(lineas[i])) {
      texto.push(lineas[i++].trim());
    }
    bloques.push(new Paragraph({ spacing: { after: 140 }, indent: sangrado && enListaNum ? { left: 360 } : undefined,
                                 children: enLinea(texto.join(" ")) }));
  }
  return bloques;
}

// ------------------------------------------------------------------ portada
function portada(d) {
  const fecha = new Date().toLocaleDateString("es-EC", { day: "numeric", month: "long", year: "numeric" });
  const linea = (texto, opt) => new Paragraph({ alignment: AlignmentType.LEFT, ...opt.p, children: [new TextRun({ text: texto, font: FUENTE, ...opt.r })] });
  return [
    linea("ClinAgenda", { p: { spacing: { before: 2400, after: 120 } }, r: { size: 30, bold: true, color: AZUL } }),
    linea(d.titulo, { p: { spacing: { after: 240 } }, r: { size: 60, bold: true, color: OSCURO } }),
    new Paragraph({ spacing: { after: 600 }, border: { bottom: { style: BorderStyle.SINGLE, size: 12, color: AZUL, space: 6 } },
                    children: [new TextRun({ text: d.subtitulo, size: 26, color: GRIS })] }),
    linea("Sistema de agendamiento de citas para las clínicas Centro, Norte y Sur de la Dra. Paredes", { p: { spacing: { after: 120 } }, r: { size: 22 } }),
    linea("Concurso de Programación ClinAgenda · Seventech", { p: { spacing: { after: 120 } }, r: { size: 22 } }),
    linea("Repositorio: https://github.com/GuadalupeOchoa/ClinAgenda", { p: { spacing: { after: 120 } }, r: { size: 22 } }),
    linea(`Fecha: ${fecha}`, { p: { spacing: { after: 120 } }, r: { size: 22, color: GRIS } }),
    new Paragraph({ children: [new PageBreak()] }),
  ];
}

// ------------------------------------------------------------------ documento
function documento(d) {
  const archivoMd = path.join(RAIZ, d.md);
  const cuerpo = convertir(fs.readFileSync(archivoMd, "utf8"), path.dirname(archivoMd));
  const titulo = (size, color, before, after) => ({ run: { font: FUENTE, size, bold: true, color },
                                                   paragraph: { spacing: { before, after }, keepNext: true, keepLines: true } });
  const vineta = (nivel, sim) => ({ level: nivel, format: LevelFormat.BULLET, text: sim, alignment: AlignmentType.LEFT,
                                   style: { paragraph: { indent: { left: 360 + nivel * 360, hanging: 260 } } } });
  return new Document({
    creator: "Equipo ClinAgenda", title: `ClinAgenda — ${d.titulo}`, description: d.subtitulo,
    styles: {
      default: { document: { run: { font: FUENTE, size: 22 }, paragraph: { spacing: { line: 276 } } } },
      paragraphStyles: [
        { id: "Heading1", name: "Heading 1", basedOn: "Normal", next: "Normal", quickFormat: true, ...titulo(32, OSCURO, 360, 160) },
        { id: "Heading2", name: "Heading 2", basedOn: "Normal", next: "Normal", quickFormat: true, ...titulo(26, AZUL, 280, 120) },
        { id: "Heading3", name: "Heading 3", basedOn: "Normal", next: "Normal", quickFormat: true, ...titulo(23, OSCURO, 200, 80) },
      ],
    },
    numbering: { config: [
      { reference: "vinetas", levels: [vineta(0, "•"), vineta(1, "◦"), vineta(2, "▪")] },
      { reference: "numeros", levels: [0, 1, 2].map((n) => ({ level: n, format: n === 0 ? LevelFormat.DECIMAL : LevelFormat.LOWER_LETTER,
          text: n === 0 ? "%1." : `%${n + 1}.`, alignment: AlignmentType.LEFT,
          style: { paragraph: { indent: { left: 360 + n * 360, hanging: 300 } } } })) },
    ] },
    sections: [{
      properties: { page: { size: { width: 11906, height: 16838 }, margin: { top: 1440, bottom: 1440, left: 1440, right: 1440 } } },
      footers: { default: new Footer({ children: [new Paragraph({ alignment: AlignmentType.RIGHT, children: [
        new TextRun({ text: `ClinAgenda · ${d.titulo} · página `, size: 18, color: GRIS }),
        new TextRun({ children: [PageNumber.CURRENT], size: 18, color: GRIS })] })] }) },
      children: [...portada(d), ...cuerpo],
    }],
  });
}

(async () => {
  fs.mkdirSync(SALIDA, { recursive: true });
  // Opcional: node generar_word.js 02 03  → regenera solo esos documentos (no toca los demás)
  const elegidos = process.argv.slice(2);
  for (const d of DOCUMENTOS.filter((x) => !elegidos.length || elegidos.some((e) => x.docx.startsWith(e)))) {
    // Se quitan las entradas de carpeta del ZIP: Word en la nube (OneDrive/SharePoint) a veces rechaza esos archivos
    const zip = await JSZip.loadAsync(await Packer.toBuffer(documento(d)));
    // (ojo: zip.remove() borraría también el contenido de la carpeta; aquí se quita solo la entrada)
    Object.keys(zip.files).filter((n) => zip.files[n].dir).forEach((n) => { delete zip.files[n]; });
    const buf = await zip.generateAsync({ type: "nodebuffer", compression: "DEFLATE" });
    try {
      fs.writeFileSync(path.join(SALIDA, d.docx), buf);
      console.log(`✔ docs/word/${d.docx}  (${Math.round(buf.length / 1024)} KB)`);
    } catch (e) {
      if (e.code !== "EBUSY" && e.code !== "EPERM") throw e;
      console.log(`✖ docs/word/${d.docx} está abierto en otro programa: ciérrelo y vuelva a ejecutar.`);
      process.exitCode = 1;
    }
  }
})();
