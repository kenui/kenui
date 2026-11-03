// Normaliza texto para busca e comparação: minúsculas, sem acento, espaços simples.
// "Pão de Queijo" -> "pao de queijo"
export function normalizar(texto) {
  return String(texto ?? '')
    .normalize('NFD')
    .replace(/[̀-ͯ]/g, '')
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, ' ')
    .trim();
}

export function slugificar(texto) {
  return normalizar(texto).replace(/ /g, '-');
}

// Arredonda com casas decimais fixas, evitando -0.
export function arredondar(valor, casas = 1) {
  const f = 10 ** casas;
  const r = Math.round(valor * f) / f;
  return Object.is(r, -0) ? 0 : r;
}
