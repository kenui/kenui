// Utilidades de texto e números para a interface.

export const normalizar = (s) => String(s ?? '').normalize('NFD').replace(/[̀-ͯ]/g, '').toLowerCase().trim();

export const numero = (n) => String(n).replace('.', ',');

const FRACOES = [[0.25, '1/4'], [0.33, '1/3'], [0.5, '1/2'], [0.66, '2/3'], [0.67, '2/3'], [0.75, '3/4']];

// 1.5 -> "1 e 1/2"; 0.33 -> "1/3"; 2 -> "2"
export function fracao(q) {
  const inteiro = Math.floor(q + 1e-9);
  const resto = Math.round((q - inteiro) * 100) / 100;
  if (resto === 0) return String(inteiro);
  const f = FRACOES.find(([v]) => Math.abs(v - resto) < 0.02);
  if (f) return inteiro ? `${inteiro} e ${f[1]}` : f[1];
  return numero(Math.round(q * 10) / 10);
}

export const plural = (n, um, varios) => `${n} ${n === 1 ? um : varios}`;
