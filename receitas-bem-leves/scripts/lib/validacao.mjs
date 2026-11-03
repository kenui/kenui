// Regras de validação das receitas. Retorna erros (bloqueiam) e avisos (revisar à mão).
import { existsSync, readFileSync } from 'node:fs';
import { join } from 'node:path';
import { RAIZ, ingredientesRepetidos } from './fontes.mjs';
import { calcularNutricao, valoresPor100g } from './nutricao.mjs';
import { normalizar, slugificar } from './texto.mjs';

const escapar = (s) => s.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');

// Procura termos como palavra inteira, com e sem acento, depois de tirar as expressões permitidas.
export function procurarTermos(texto, termos, permitidas = []) {
  let t = ` ${normalizar(texto)} `;
  for (const p of permitidas) t = t.replace(new RegExp(`\\b${escapar(normalizar(p))}\\b`, 'g'), ' ');
  const achados = new Set();
  for (const termo of termos) {
    if (new RegExp(`\\b${escapar(normalizar(termo))}\\b`).test(t)) achados.add(termo);
  }
  return [...achados];
}

function textosDaReceita(r) {
  const textos = [r.nome, r.descricao, r.porcao?.descricao, r.rendimento?.unidade];
  for (const i of r.ingredientes ?? []) textos.push(i.texto, i.alternativa?.texto, i.alternativa?.observacao);
  for (const p of r.preparo ?? []) textos.push(p.texto, p.aviso);
  for (const d of r.dicas ?? []) textos.push(d.texto);
  return textos.filter(Boolean).join(' \n ');
}

const ehNumeroPositivo = (v) => typeof v === 'number' && Number.isFinite(v) && v > 0;

export function validarReceita(r, { ingredientes, regras }) {
  const erros = [];
  const avisos = [];
  const erro = (m) => erros.push(m);

  // Identificação
  if (!/^rbl-\d{4}$/.test(r.id ?? '')) erro('id deve ter o formato rbl-0000');
  if (!r.nome?.trim()) erro('nome vazio');
  if (r.slug !== slugificar(r.nome ?? '')) erro(`slug deve ser "${slugificar(r.nome ?? '')}"`);
  if (!r.descricao?.trim()) erro('descrição vazia');
  if (!regras.categorias[r.categoria]) erro(`categoria inválida: ${r.categoria}`);
  for (const d of r.destaques ?? []) if (!regras.destaques[d]) erro(`destaque inválido: ${d}`);
  const refeicoes = r.refeicoes_do_plano ?? [];
  if (!refeicoes.length) erro('refeicoes_do_plano vazio');
  for (const x of refeicoes) if (!regras.refeicoes_do_plano.includes(x)) erro(`refeição do plano inválida: ${x}`);

  // Tempo, rendimento e porção
  const t = r.tempo ?? {};
  if (!(t.preparo_min >= 0) || !(t.cozimento_min >= 0) || !ehNumeroPositivo(t.total_min)) erro('tempo incompleto');
  else if (t.total_min < t.preparo_min + t.cozimento_min + (t.descanso_min ?? 0)) erro('tempo total menor que preparo + cozimento + descanso');
  const rapida = t.total_min <= 15;
  if (rapida !== (r.destaques ?? []).includes('rapidas_15min')) {
    erro(rapida ? 'receita de até 15 min sem o destaque rapidas_15min' : 'destaque rapidas_15min em receita com mais de 15 min');
  }
  if (!Number.isInteger(r.porcoes) || r.porcoes < 1) erro('porcoes deve ser um número inteiro maior que zero');
  if (!r.porcao?.descricao?.trim()) erro('descrição da porção vazia');
  if (!ehNumeroPositivo(r.rendimento?.quantidade) || !r.rendimento?.unidade) erro('rendimento incompleto');

  // Ingredientes
  const lista = r.ingredientes ?? [];
  if (!lista.length) erro('lista de ingredientes vazia');
  const enfeitesDisponiveis = new Set();
  for (const item of lista) {
    const c = ingredientes[item.ingrediente];
    const rotulo = item.texto || item.ingrediente;
    if (!c) { erro(`ingrediente fora do cadastro: ${item.ingrediente}`); continue; }
    if (c.proibido) erro(`ingrediente proibido: ${c.nome}`);
    if (c.adocante && !regras.adocantes_aceitos.includes(c.adocante)) erro(`adoçante não aceito: ${c.nome}`);
    if (!item.texto?.trim()) erro(`ingrediente sem texto: ${item.ingrediente}`);
    if (!ehNumeroPositivo(item.quantidade)) erro(`quantidade inválida em "${rotulo}"`);
    if (!regras.medidas.includes(item.medida)) erro(`medida inválida em "${rotulo}": ${item.medida}`);
    else if (item.medida !== 'g' && !c.gramas_por_medida?.[item.medida]) erro(`"${rotulo}": ${c.nome} não tem peso para a medida ${item.medida}`);
    if (!c.facil_de_achar && !item.alternativa) erro(`"${rotulo}" é difícil de achar e não tem alternativa`);
    if (item.alternativa) {
      const a = ingredientes[item.alternativa.ingrediente];
      if (!a) erro(`alternativa fora do cadastro: ${item.alternativa.ingrediente}`);
      else if (a.proibido) erro(`alternativa proibida: ${a.nome}`);
      if (!item.alternativa.texto?.trim()) erro(`alternativa sem texto em "${rotulo}"`);
    }
    if (c.enfeite) enfeitesDisponiveis.add(c.enfeite);
  }
  // O mesmo ingrediente pode aparecer na massa e na calda, mas não duas vezes no mesmo grupo.
  const chaves = lista.map((i) => `${i.grupo ?? ''}|${i.ingrediente}`);
  const repetidos = chaves.filter((k, n) => chaves.indexOf(k) !== n).map((k) => k.split('|')[1]);
  if (repetidos.length) erro(`ingrediente repetido no mesmo grupo: ${[...new Set(repetidos)].join(', ')}`);

  // Preparo
  const passos = r.preparo ?? [];
  if (!passos.length) erro('modo de preparo vazio');
  passos.forEach((p, n) => { if (!p?.texto || p.texto.trim().length < 10) erro(`passo ${n + 1} vazio ou curto demais`); });
  const usaForno = passos.some((p) => /\bforno\b/i.test(p.texto ?? ''));
  if (usaForno && !r.forno) erro('o preparo usa forno mas o campo forno está vazio');
  if (r.forno) {
    const f = regras.forno;
    if (!(r.forno.temperatura_c >= f.temperatura_min_c && r.forno.temperatura_c <= f.temperatura_max_c)) erro(`temperatura de forno fora do normal: ${r.forno.temperatura_c} °C`);
    if (!ehNumeroPositivo(r.forno.tempo_min) || r.forno.tempo_min > f.tempo_max_min) erro(`tempo de forno inválido: ${r.forno.tempo_min}`);
    if (r.forno.tempo_min > t.cozimento_min) erro('tempo de forno maior que o tempo de cozimento');
  }

  // Dicas
  if (!(r.dicas ?? []).some((d) => d.tipo === 'substituicao' && d.texto?.trim())) erro('falta pelo menos uma dica de substituição');

  // Ingredientes e expressões proibidas no texto, e promessas de saúde
  const texto = textosDaReceita(r);
  const proibidos = procurarTermos(texto, regras.termos_proibidos, regras.expressoes_permitidas_com_termo_proibido);
  if (proibidos.length) erro(`texto com termo proibido: ${proibidos.join(', ')}`);
  const saude = procurarTermos(texto, regras.termos_promessa_de_saude, regras.expressoes_permitidas_com_termo_de_saude);
  if (saude.length) erro(`texto com promessa de saúde: ${saude.join(', ')}`);

  // Nutrição
  const { erros: errosNutricao, calculo } = calcularNutricao(r, ingredientes);
  errosNutricao.forEach((m) => erro(`nutrição: ${m}`));
  const pp = r.nutricao?.por_porcao;
  if (!pp || typeof pp.kcal !== 'number' || typeof pp.carboidratos_g !== 'number') {
    erro('nutrição faltando (rode npm run nutricao)');
  } else if (calculo.por_porcao && (pp.kcal !== calculo.por_porcao.kcal || pp.carboidratos_g !== calculo.por_porcao.carboidratos_g)) {
    erro(`nutrição desatualizada: arquivo diz ${pp.kcal} kcal/${pp.carboidratos_g} g, cálculo dá ${calculo.por_porcao.kcal} kcal/${calculo.por_porcao.carboidratos_g} g (rode npm run nutricao)`);
  }
  if (r.nutricao?.aproximado !== true) erro('nutrição precisa estar marcada como aproximada');
  const caminhoCalculo = r.nutricao?.arquivo_calculo ? join(RAIZ, r.nutricao.arquivo_calculo) : null;
  if (!caminhoCalculo || !existsSync(caminhoCalculo)) {
    erro('arquivo de cálculo nutricional não encontrado');
  } else {
    const salvo = JSON.parse(readFileSync(caminhoCalculo, 'utf8'));
    if (JSON.stringify(salvo.por_porcao) !== JSON.stringify(calculo.por_porcao)) erro('arquivo de cálculo nutricional desatualizado');
  }

  // Etiquetas
  if (r.etiquetas?.sem_acucar_adicionado !== true) erro('etiqueta sem_acucar_adicionado precisa ser true');
  if (calculo.por_porcao) {
    const deveSerLowCarb = calculo.por_porcao.carboidratos_g <= regras.low_carb_max_carboidratos_g;
    if (r.etiquetas?.low_carb !== deveSerLowCarb) {
      erro(`etiqueta low carb errada: porção tem ${calculo.por_porcao.carboidratos_g} g de carboidrato, então low_carb deve ser ${deveSerLowCarb}`);
    }
  }

  // Ilustração
  const il = r.ilustracao ?? {};
  const listas = regras.ilustracao;
  if (!listas.pratos_base.includes(il.prato_base)) erro(`prato_base inválido: ${il.prato_base}`);
  if (il.massa && !listas.massas.includes(il.massa)) erro(`cor de massa inválida: ${il.massa}`);
  if (il.cobertura && !listas.coberturas.includes(il.cobertura)) erro(`cobertura inválida: ${il.cobertura}`);
  for (const e of il.enfeites ?? []) {
    if (!enfeitesDisponiveis.has(e)) erro(`ilustração desenha "${e}", mas a receita não tem ingrediente com esse enfeite`);
  }

  // Foto
  if (r.foto !== undefined && r.foto !== null) {
    if (typeof r.foto !== 'string') erro('foto deve ser um caminho de arquivo');
    else if (!existsSync(join(RAIZ, 'public', r.foto))) avisos.push(`foto ainda não recebida: public/${r.foto}`);
  }

  return { erros, avisos, calculo };
}

// Confere o cadastro de ingredientes: fonte existente, valores presentes, medidas com fonte, listas válidas.
export function validarCadastro({ ingredientes, regras }) {
  const erros = ingredientesRepetidos.map((m) => `ingrediente repetido: ${m}`);
  for (const c of Object.values(ingredientes)) {
    const onde = `${c.id} (${c._arquivo})`;
    if (!c.nome) erros.push(`${onde}: sem nome`);
    if (!regras.secoes_mercado[c.secao_mercado]) erros.push(`${onde}: seção de mercado inválida "${c.secao_mercado}"`);
    if (c.enfeite && !regras.ilustracao.enfeites.includes(c.enfeite)) erros.push(`${onde}: enfeite inválido "${c.enfeite}"`);
    if (c.adocante && !regras.adocantes_aceitos.includes(c.adocante)) erros.push(`${onde}: adoçante não aceito "${c.adocante}"`);
    if (c.alternativa_padrao && !ingredientes[c.alternativa_padrao]) erros.push(`${onde}: alternativa_padrao "${c.alternativa_padrao}" não existe`);
    for (const [m, v] of Object.entries(c.gramas_por_medida ?? {})) {
      if (!regras.medidas.includes(m)) erros.push(`${onde}: medida inválida "${m}"`);
      if (!(v?.g > 0) || !v?.fonte) erros.push(`${onde}: medida "${m}" sem gramas ou sem fonte`);
    }
    if (!c.proibido) {
      const v = valoresPor100g(c);
      if (v.erro) erros.push(`${onde}: ${v.erro}`);
    }
  }
  return erros;
}

function jaccard(a, b) {
  const A = new Set(a);
  const B = new Set(b);
  const inter = [...A].filter((x) => B.has(x)).length;
  return inter / (A.size + B.size - inter || 1);
}

export function validarColecao(itens, contexto) {
  const resultados = itens.map(({ arquivo, receita }) => ({ arquivo, receita, ...validarReceita(receita, contexto) }));

  const vistos = { id: new Map(), slug: new Map(), nome: new Map() };
  for (const res of resultados) {
    const r = res.receita;
    for (const [campo, valor] of [['id', r.id], ['slug', r.slug], ['nome', normalizar(r.nome)]]) {
      if (vistos[campo].has(valor)) res.erros.push(`${campo} repetido com ${vistos[campo].get(valor)}`);
      else vistos[campo].set(valor, r.id);
    }
  }

  // Receitas repetidas com nome diferente: mesmos ingredientes principais.
  const principais = (r) => (r.ingredientes ?? []).filter((i) => !i.opcional).map((i) => i.ingrediente)
    .filter((id) => !['sal', 'agua', 'oleo', 'azeite', 'pimenta-do-reino'].includes(id));
  for (let i = 0; i < resultados.length; i++) {
    for (let j = i + 1; j < resultados.length; j++) {
      const a = resultados[i].receita;
      const b = resultados[j].receita;
      const s = jaccard(principais(a), principais(b));
      if (s >= 0.85 && a.categoria === b.categoria) {
        resultados[j].erros.push(`parece a mesma receita que ${a.id} (${a.nome}): ${Math.round(s * 100)}% dos ingredientes iguais`);
      } else if (s >= 0.6 && a.ilustracao?.prato_base === b.ilustracao?.prato_base) {
        resultados[j].avisos.push(`parecida com ${a.id} (${a.nome}): ${Math.round(s * 100)}% dos ingredientes iguais e mesmo prato`);
      }
    }
  }
  return resultados;
}
