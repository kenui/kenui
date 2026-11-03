// Leitor de CSV simples (aspas duplas, vírgula como separador). Sem dependências.
export function lerCsv(texto) {
  const linhas = [];
  let campo = '';
  let linha = [];
  let dentroDeAspas = false;
  for (let i = 0; i < texto.length; i++) {
    const c = texto[i];
    if (dentroDeAspas) {
      if (c === '"') {
        if (texto[i + 1] === '"') { campo += '"'; i++; } else { dentroDeAspas = false; }
      } else {
        campo += c;
      }
    } else if (c === '"') {
      dentroDeAspas = true;
    } else if (c === ',') {
      linha.push(campo); campo = '';
    } else if (c === '\n' || c === '\r') {
      if (c === '\r' && texto[i + 1] === '\n') i++;
      linha.push(campo); campo = '';
      if (linha.length > 1 || linha[0] !== '') linhas.push(linha);
      linha = [];
    } else {
      campo += c;
    }
  }
  if (campo !== '' || linha.length) { linha.push(campo); linhas.push(linha); }
  const [cabecalho, ...resto] = linhas;
  return resto.map((l) => Object.fromEntries(cabecalho.map((h, i) => [h, l[i] ?? ''])));
}
