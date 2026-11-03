// Gera os ícones do app (tela inicial do Android e do iPhone) a partir de um desenho SVG.
// Uso: node scripts/gerar-icones.mjs
import { createRequire } from 'node:module';
import { join } from 'node:path';
import { RAIZ } from './lib/fontes.mjs';

const desenho = (margem) => `
<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 512 512">
  <rect width="512" height="512" fill="#7B1E2C"/>
  <g transform="translate(256 270) scale(${1 - margem}) translate(-256 -270)">
    <ellipse cx="256" cy="360" rx="190" ry="62" fill="#5E1621"/>
    <ellipse cx="256" cy="350" rx="190" ry="62" fill="#FBF3E8"/>
    <ellipse cx="256" cy="346" rx="142" ry="44" fill="#F1E3CF"/>
    <path d="M136 342 L136 252 Q138 186 214 180 L298 180 Q374 186 376 252 L376 342 Q256 368 136 342Z" fill="#C3935B"/>
    <path d="M142 236 Q150 160 256 154 Q362 160 370 236 Q256 262 142 236Z" fill="#E5BC77"/>
    <path d="M190 206 l36 -18 M246 200 l36 -18 M302 206 l30 -16" stroke="#F4D9A3" stroke-width="12" stroke-linecap="round"/>
    <path d="M330 150 C352 100 410 92 430 110 C412 150 364 168 330 150Z" fill="#1FA855"/>
    <path d="M336 146 C366 128 392 116 420 112" stroke="#BFF0CF" stroke-width="6" fill="none" stroke-linecap="round"/>
  </g>
</svg>`;

const { chromium } = createRequire(import.meta.url)('playwright');
const navegador = await chromium.launch();
const pagina = await navegador.newPage();
const gerar = async (arquivo, tamanho, margem) => {
  await pagina.setViewportSize({ width: tamanho, height: tamanho });
  await pagina.setContent(`<style>body{margin:0}svg{width:${tamanho}px;height:${tamanho}px;display:block}</style>${desenho(margem)}`);
  await pagina.screenshot({ path: join(RAIZ, 'public', 'icones', arquivo) });
};
await gerar('icone-192.png', 192, 0);
await gerar('icone-512.png', 512, 0);
await gerar('icone-mascara-512.png', 512, 0.22);
await gerar('apple-touch-icon.png', 180, 0.08);
await navegador.close();
console.log('Ícones gravados em public/icones/');
