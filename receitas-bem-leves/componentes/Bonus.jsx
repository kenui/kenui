'use client';
// Mostra o conteúdo de um bônus a partir de blocos (parágrafo, título, lista, tabela, receitas, plano).
import Link from 'next/link';
import { Fragment, useState } from 'react';
import { useApp } from './Provedor';
import { ListaReceitas } from './Receita';
import { DIAS, REFEICOES, receitaDoPlano } from '../lib/plano';
import { lerPequeno, gravarPequeno } from '../lib/armazenamento';

function Checklist({ chave, itens }) {
  const [marcados, setMarcados] = useState(() => lerPequeno(`bonus:${chave}`, []));
  const marcar = (i, sim) => {
    const novo = sim ? [...marcados, i] : marcados.filter((x) => x !== i);
    setMarcados(novo);
    gravarPequeno(`bonus:${chave}`, novo);
  };
  return itens.map((t, i) => (
    <div key={i} className={`item-compra${marcados.includes(i) ? ' marcado' : ''}`}>
      <input type="checkbox" id={`${chave}-${i}`} checked={marcados.includes(i)} onChange={(e) => marcar(i, e.target.checked)} />
      <label htmlFor={`${chave}-${i}`}>{t}</label>
    </div>
  ));
}

function PlanoCompleto() {
  const { pacote, dados } = useApp();
  return [0, 1, 2, 3].map((s) => (
    <section key={s} className="bloco">
      <h3>Semana {s + 1}</h3>
      <div className="tabela-rolagem">
        <table>
          <thead><tr><th>Dia</th>{REFEICOES.map(([, n]) => <th key={n}>{n}</th>)}</tr></thead>
          <tbody>
            {DIAS.map((dia, d) => (
              <tr key={dia}>
                <th>{dia}</th>
                {REFEICOES.map(([k]) => {
                  const id = receitaDoPlano(pacote, dados.trocas, s, d, k);
                  return <td key={k}><Link href={`/receita/?id=${id}`}>{pacote.porId[id]?.nome}</Link></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  ));
}

export function ConteudoBonus({ bonus }) {
  const { pacote } = useApp();
  return (
    <article className="texto-longo">
      <h2>{bonus.titulo}</h2>
      {bonus.blocos.map((b, i) => {
        if (b.t === 'p') return <p key={i}>{b.texto}</p>;
        if (b.t === 'h') return <h3 key={i}>{b.texto}</h3>;
        if (b.t === 'lista') return <ul key={i}>{b.itens.map((t, k) => <li key={k}>{t}</li>)}</ul>;
        if (b.t === 'checklist') return <div key={i} className="grupo-mercado"><Checklist chave={`${bonus.slug}-${i}`} itens={b.itens} /></div>;
        if (b.t === 'tabela') {
          return (
            <div key={i} className="tabela-rolagem">
              <table>
                <thead><tr>{b.cabecalho.map((c) => <th key={c}>{c}</th>)}</tr></thead>
                <tbody>{b.linhas.map((l, k) => <tr key={k}>{l.map((c, j) => <td key={j}>{c}</td>)}</tr>)}</tbody>
              </table>
            </div>
          );
        }
        if (b.t === 'receitas') return <ListaReceitas key={i} receitas={pacote.receitas.filter((r) => r.categoria === b.categoria)} />;
        if (b.t === 'plano') return <Fragment key={i}><PlanoCompleto /></Fragment>;
        if (b.t === 'imprimir') return <button key={i} className="btn btn-principal btn-largo btn-grande" onClick={() => window.print()}>{b.texto}</button>;
        return null;
      })}
    </article>
  );
}
