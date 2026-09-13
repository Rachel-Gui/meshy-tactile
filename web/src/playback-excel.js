import { unzipSync, strFromU8 } from 'fflate';

// Read OOXML without executing formulas, macros or external workbook links.
export function excelToCsv(buffer) {
  let expanded = 0;
  const files = unzipSync(new Uint8Array(buffer), { filter(entry) {
    expanded += entry.originalSize;
    if (expanded > 32 * 1024 * 1024) throw new Error('Expanded Excel workbook exceeds 32 MB; use a shorter clip.');
    return /\.(xml|rels)$/.test(entry.name);
  } });
  function xml(path) {
    if (!files[path]) throw new Error(`Invalid Excel workbook: missing ${path}`);
    const doc = new DOMParser().parseFromString(strFromU8(files[path]), 'application/xml');
    if (doc.getElementsByTagName('parsererror').length) throw new Error('Invalid Excel XML');
    return doc;
  }
  const nodes = (root, name) => Array.from(root.getElementsByTagNameNS('*', name));
  const sheets = nodes(xml('xl/workbook.xml'), 'sheet');
  const selected = sheets.find(s => s.getAttribute('name').trim().toLowerCase() === 'signal combined') || (sheets.length === 1 ? sheets[0] : null);
  if (!selected) throw new Error('Choose a workbook with a Signal Combined sheet, or a single sheet containing time and N001… columns.');
  const id = selected.getAttributeNS('http://schemas.openxmlformats.org/officeDocument/2006/relationships', 'id');
  const relationship = nodes(xml('xl/_rels/workbook.xml.rels'), 'Relationship').find(r => r.getAttribute('Id') === id);
  if (!relationship || relationship.getAttribute('TargetMode') === 'External') throw new Error('Invalid worksheet relationship');
  const target = relationship.getAttribute('Target');
  const path = target.startsWith('/') ? target.slice(1) : `xl/${target.replace(/^\.\//, '')}`;
  const strings = files['xl/sharedStrings.xml'] ? nodes(xml('xl/sharedStrings.xml'), 'si').map(si => nodes(si,'t').map(t=>t.textContent).join('')) : [];
  const rows = nodes(xml(path), 'row').map(row => {
    const cells = [];
    for (const cell of nodes(row, 'c')) {
      const ref = cell.getAttribute('r') || '';
      const letters = ref.match(/^[A-Z]+/)?.[0];
      if (!letters) throw new Error('Missing Excel cell address');
      let column = 0; for (const c of letters) column = column * 26 + c.charCodeAt(0) - 64;
      if (column > 512) throw new Error('Excel table has too many columns');
      const value = nodes(cell,'v')[0]?.textContent;
      if (cell.getAttribute('t') === 'e') throw new Error(`Excel error in ${ref}`);
      if (nodes(cell,'f').length && value === undefined) throw new Error(`Recalculate and save Excel before uploading (${ref}).`);
      cells[column - 1] = cell.getAttribute('t') === 's' ? strings[Number(value)] : cell.getAttribute('t') === 'inlineStr' ? nodes(cell,'t').map(t=>t.textContent).join('') : value ?? '';
    }
    return Array.from(cells, value => `"${String(value ?? '').replaceAll('"','""')}"`).join(',');
  });
  return rows.filter(row => row.replace(/[",]/g, '').trim()).join('\n');
}
