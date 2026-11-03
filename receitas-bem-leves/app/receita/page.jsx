'use client';
import Link from 'next/link';
import { useSearchParams } from 'next/navigation';
import { Fragment, Suspense, useEffect, useState } from 'react';
import { Moldura } from '../../componentes/Moldura';
import { ImagemReceita } from '../../componentes/Receita';
import { ModoCozinha } from '../../componentes/ModoCozinha';
import { useApp } from '../../componentes/Provedor';
import { useAviso } from '../../componentes/Toast';
import { numero } from '../../lib/texto';

const ROTULO_DICA = { substituicao: 'Substituição', dica: 'Dica', conservacao: 'Como guardar' };

function Ingredientes({ receita }) {
  const grupos = [];
  for (const i of receita.ingredientes) {
    const g = i.grupo ?? '';
    if (!grupos.length || grupos.at(-1).nome !== g) grupos.push({ nome: g, itens: [] });
    grupos.at(-1).itens.push(i);
  }
  return grupos.map((g, n) => (
    <Fragment key={n}>
      {g.nome && <h4>{g.nome}</h4>}
      <ul className="ingredientes">
        {g.itens.map((i, k) => (
          <li key={k}>
            {i.texto}
            {i.alternativa && <span className="alt">{i.alternativa.texto}{i.alternativa.observacao ? `. ${i.alternativa.observacao}` : ''}</span>}
          </li>
        ))}
      </ul>
    </Fragment>
  ));
}

function Receita() {
  const { pacote, dados, atualizar } = useApp();
  const id = useSearchParams().get('id');
  const [cozinhando, setCozinhando] = useState(false);
  const [toast, avisar] = useAviso();
  const r = pacote?.porId[id];

  useEffect(() => {
    if (r) atualizar('vistas', (v) => [r.id, ...v.filter((x) => x !== r.id)].slice(0, 12));
  }, [r, atualizar]);

  if (!pacote) return null;
  if (!r) return <div className="vazio">Receita não encontrada.<Link className="btn btn-principal" href="/receitas/">Ver receitas</Link></div>;

  const favorita = dados.favoritos.includes(r.id);
  const naLista = dados.lista.receitas.includes(r.id);
  const t = r.tempo;

  return (
    <>
      <ImagemReceita receita={r} comFoto />
      <div className="receita-cabecalho"><h2>{r.nome}</h2><p>{r.descricao}</p></div>
      <div className="fatos">
        <div className="fato"><small>Tempo</small><b>{t.total_min >= 120 ? `${Math.floor(t.total_min / 60)} h ${t.total_min % 60 ? `${t.total_min % 60} min` : ''}` : `${t.total_min} min`}</b></div>
        <div className="fato"><small>Rende</small><b>{numero(r.rendimento.quantidade)} {r.rendimento.unidade}</b></div>
        <div className="fato"><small>Porção</small><b>{r.porcao}</b></div>
        <div className="fato"><small>Por porção</small><b>{r.nutricao.kcal} kcal · {numero(r.nutricao.carboidratos_g)} g de carboidratos</b></div>
      </div>
      <p className="nota">Valores aproximados, calculados ingrediente por ingrediente com a Tabela TACO (Unicamp) e a tabela da USDA.</p>
      <div className="acoes nao-imprimir">
        <button className="btn btn-principal btn-grande" onClick={() => setCozinhando(true)}>Modo cozinha</button>
        <button className="btn btn-secundario" aria-pressed={favorita} onClick={() => {
          atualizar('favoritos', (f) => (favorita ? f.filter((x) => x !== r.id) : [...f, r.id]));
          avisar(favorita ? 'Tirada dos favoritos' : 'Salva nos favoritos');
        }}>{favorita ? '♥ Favorita' : '♡ Favoritar'}</button>
        <button className="btn btn-secundario" onClick={() => {
          if (!naLista) {
            atualizar('lista', (l) => ({ ...l, receitas: [...l.receitas, r.id] }));
            avisar('Ingredientes na lista de compras');
          } else window.location.href = '/lista/';
        }}>{naLista ? '✓ Na lista' : '+ Lista de compras'}</button>
        <button className="btn btn-secundario" style={{ gridColumn: '1 / -1' }} onClick={() => window.print()}>Imprimir receita</button>
      </div>
      <section className="bloco"><h3>Ingredientes</h3><Ingredientes receita={r} /></section>
      <section className="bloco">
        <h3>Modo de preparo</h3>
        {r.forno && <p className="nota">Forno: {r.forno.temperatura_c} °C{r.forno.preaquecer ? ', preaquecido' : ''}.</p>}
        <ol className="passos">
          {r.preparo.map((p, i) => <li key={i}><div>{p.texto}{p.aviso && <span className="atencao">Atenção: {p.aviso}</span>}</div></li>)}
        </ol>
      </section>
      <section className="bloco">
        <h3>Dicas</h3>
        <ul className="dicas">{r.dicas.map((d, i) => <li key={i}><b>{ROTULO_DICA[d.tipo] ?? 'Dica'}:</b> {d.texto}</li>)}</ul>
      </section>
      {cozinhando && <ModoCozinha receita={r} fechar={() => setCozinhando(false)} />}
      {toast}
    </>
  );
}

function Titulo() {
  const { pacote } = useApp();
  const id = useSearchParams().get('id');
  return pacote?.porId[id]?.nome ?? 'Receita';
}

export default function Pagina() {
  return (
    <Suspense>
      <Moldura titulo={<Suspense fallback="Receita"><Titulo /></Suspense>} ativa="receitas" voltar="/receitas/">
        <Receita />
      </Moldura>
    </Suspense>
  );
}
