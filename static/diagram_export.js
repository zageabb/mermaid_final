/* Download the unmodified Mermaid render, not the pan/zoom canvas. */
(function () {
  'use strict';

  function prepareSvg(markup) {
    if (!markup || !markup.trim()) {
      throw new Error('The diagram has not rendered yet.');
    }
    const parsed = new DOMParser().parseFromString(markup, 'image/svg+xml');
    const root = parsed.documentElement;
    if (root.localName !== 'svg' || parsed.querySelector('parsererror')) {
      throw new Error('Unable to prepare the rendered SVG.');
    }
    const viewBox = (root.getAttribute('viewBox') || '')
      .trim().split(/[\s,]+/).map(Number);
    const viewWidth = viewBox.length === 4 && viewBox[2] > 0 ? viewBox[2] : 0;
    const viewHeight = viewBox.length === 4 && viewBox[3] > 0 ? viewBox[3] : 0;
    const width = viewWidth || parseFloat(root.getAttribute('width')) || 1200;
    const height = viewHeight || parseFloat(root.getAttribute('height')) || 800;
    if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) {
      throw new Error('The diagram has invalid dimensions.');
    }
    root.setAttribute('xmlns', 'http://www.w3.org/2000/svg');
    root.setAttribute('xmlns:xlink', 'http://www.w3.org/1999/xlink');
    root.setAttribute('width', String(width));
    root.setAttribute('height', String(height));
    // Mermaid may use max-width on the root, which otherwise clips PNG rendering.
    root.style.removeProperty('max-width');
    root.style.removeProperty('width');
    root.style.removeProperty('height');
    return {
      markup: new XMLSerializer().serializeToString(root),
      width,
      height
    };
  }

  function downloadBlob(blob, name) {
    const url = URL.createObjectURL(blob);
    const anchor = document.createElement('a');
    anchor.href = url;
    anchor.download = name;
    document.body.appendChild(anchor);
    anchor.click();
    anchor.remove();
    window.setTimeout(() => URL.revokeObjectURL(url), 10000);
  }

  async function download(markup, format, filename) {
    const diagram = prepareSvg(markup);
    const stem = (filename || 'diagram')
      .replace(/\.mmd$/i, '')
      .replace(/[\\/:*?"<>|\x00-\x1f]/g, '_')
      .trim() || 'diagram';

    if (format === 'svg') {
      downloadBlob(new Blob([diagram.markup], { type: 'image/svg+xml;charset=utf-8' }), stem + '.svg');
      return;
    }
    if (format !== 'png') {
      throw new Error('Unsupported export format: ' + format);
    }

    // Render at up to 2x for sharp images, with a pixel limit for large charts.
    const scale = Math.min(2, 16000 / Math.max(diagram.width, diagram.height),
      Math.sqrt(40000000 / (diagram.width * diagram.height)));
    const pixelWidth = Math.max(1, Math.round(diagram.width * scale));
    const pixelHeight = Math.max(1, Math.round(diagram.height * scale));
    const svgUrl = URL.createObjectURL(new Blob([diagram.markup], { type: 'image/svg+xml;charset=utf-8' }));
    try {
      const picture = new Image();
      await new Promise((resolve, reject) => {
        picture.onload = resolve;
        picture.onerror = () => reject(new Error('Browser could not rasterise this SVG; try SVG export instead.'));
        picture.src = svgUrl;
      });
      const canvas = document.createElement('canvas');
      canvas.width = pixelWidth;
      canvas.height = pixelHeight;
      const context = canvas.getContext('2d');
      if (!context) throw new Error('Canvas rendering is not available in this browser.');
      context.fillStyle = '#fff';
      context.fillRect(0, 0, pixelWidth, pixelHeight);
      context.drawImage(picture, 0, 0, pixelWidth, pixelHeight);
      const png = await new Promise((resolve, reject) => {
        try {
          canvas.toBlob(blob => blob ? resolve(blob) : reject(new Error('Could not encode PNG.')),
            'image/png');
        } catch (error) { reject(error); }
      });
      downloadBlob(png, stem + '.png');
    } finally {
      URL.revokeObjectURL(svgUrl);
    }
  }

  window.DiagramExport = { download };
})();
