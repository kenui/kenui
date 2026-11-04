'use client';
// Mostra o conteúdo de um bônus ou de um produto extra a partir de blocos
// (parágrafo, título, lista, tabela, receitas, plano, cardápio de 12 semanas, impressão do caderno...).
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { Fragment, useEffect, useState } from 'react';
import { useApp } from './Provedor';
import { ListaReceitas } from './Receita';
import { Ilustracao } from '../ilustracoes/index.mjs';
import { DIAS, REFEICOES, receitaDoPlano } from '../lib/plano';
import { lerPequeno, gravarPequeno } from '../lib/armazenamento';
import { numero } from '../lib/texto';

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

// Tabela de uma semana. idDe(dia, refeicao) devolve o id da receita.
function TabelaSemana({ titulo, idDe }) {
  const { pacote } = useApp();
  return (
    <section className="bloco">
      {titulo && <h3>{titulo}</h3>}
      <div className="tabela-rolagem">
        <table>
          <thead><tr><th>Dia</th>{REFEICOES.map(([, n]) => <th key={n}>{n}</th>)}</tr></thead>
          <tbody>
            {DIAS.map((dia, d) => (
              <tr key={dia}>
                <th>{dia}</th>
                {REFEICOES.map(([k]) => {
                  const id = idDe(d, k);
                  return <td key={k}><Link href={`/receita/?id=${id}`}>{pacote.porId[id]?.nome}</Link></td>;
                })}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </section>
  );
}

function PlanoCompleto() {
  const { pacote, dados } = useApp();
  return [0, 1, 2, 3].map((s) => <TabelaSemana key={s} titulo={`Semana ${s + 1}`} idDe={(d, k) => receitaDoPlano(pacote, dados.trocas, s, d, k)} />);
}

// Cardápio de 12 semanas: escolhe a semana, vê a tabela e gera a lista de compras.
function PlanoSemanas({ semanas }) {
  const { atualizar } = useApp();
  const router = useRouter();
  const [semana, setSemana] = useState(() => lerPequeno('cardapio12:semana', 0));
  const escolher = (n) => { setSemana(n); gravarPequeno('cardapio12:semana', n); };
  const ids = () => [...new Set(semanas[semana].flatMap((dia) => REFEICOES.map(([k]) => dia[k])))];
  return (
    <>
      <div className="semanas semanas-12 nao-imprimir" role="group" aria-label="Semana">
        {semanas.map((_, n) => <button key={n} className="chip" aria-pressed={semana === n} onClick={() => escolher(n)}>Semana {n + 1}</button>)}
      </div>
      <button className="btn btn-principal btn-largo btn-grande nao-imprimir" onClick={() => { atualizar('lista', { receitas: ids(), marcados: [] }); router.push('/lista/'); }}>
        Lista de compras da semana {semana + 1}
      </button>
      <TabelaSemana titulo={`Semana ${semana + 1}`} idDe={(d, k) => semanas[semana][d][k]} />
      <button className="btn btn-secundario btn-largo nao-imprimir" onClick={() => window.print()}>Imprimir esta semana</button>
    </>
  );
}

function Domingos({ domingos }) {
  const { pacote } = useApp();
  const nome = (id) => (id ? <Link href={`/receita/?id=${id}`}>{pacote.porId[id]?.nome}</Link> : '—');
  return (
    <div className="tabela-rolagem">
      <table>
        <thead><tr><th>Domingo</th><th>Pratos principais</th><th>Acompanhamento</th><th>Lanche da semana</th></tr></thead>
        <tbody>
          {domingos.map((d, i) => (
            <tr key={i}>
              <th>{i + 1}</th>
              <td>{d.principais.map((id, k) => <Fragment key={id}>{k ? ' e ' : ''}{nome(id)}</Fragment>)}</td>
              <td>{nome(d.acompanhamento)}</td>
              <td>{nome(d.lanche)}</td>
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

// Receita completa no formato de folha impressa.
function FolhaReceita({ r }) {
  const { pacote } = useApp();
  return (
    <section className="folha-receita">
      <div className="folha-imagem"><Ilustracao receita={r} ingredientes={pacote.ingredientes} /></div>
      <h2>{r.nome}</h2>
      <p className="folha-meta">{r.tempo.total_min} min · rende {numero(r.rendimento.quantidade)} {r.rendimento.unidade} · por porção ({r.porcao}): {r.nutricao.kcal} kcal e {numero(r.nutricao.carboidratos_g)} g de carboidratos (valores aproximados)</p>
      <div className="folha-colunas">
        <div>
          <h3>Ingredientes</h3>
          <ul>{r.ingredientes.map((i, k) => <li key={k}>{i.grupo ? <b>{i.grupo}: </b> : null}{i.texto}</li>)}</ul>
        </div>
        <div>
          <h3>Modo de preparo</h3>
          <ol>{r.preparo.map((p, k) => <li key={k}>{p.texto}</li>)}</ol>
          {r.forno && <p>Forno: {r.forno.temperatura_c} °C.</p>}
        </div>
      </div>
      <p className="folha-anotacoes">Anotações: ________________________________________________</p>
    </section>
  );
}

// Monta as folhas fora da tela e abre a impressão. O CSS de impressão esconde o resto do app.
function ImprimirReceitas({ texto, ids }) {
  const { pacote } = useApp();
  const [imprimindo, setImprimindo] = useState(false);
  useEffect(() => {
    if (!imprimindo) return undefined;
    document.body.classList.add('imprimindo-folhas');
    const fim = () => { document.body.classList.remove('imprimindo-folhas'); setImprimindo(false); };
    window.addEventListener('afterprint', fim, { once: true });
    const t = setTimeout(() => window.print(), 300);
    return () => { clearTimeout(t); window.removeEventListener('afterprint', fim); document.body.classList.remove('imprimindo-folhas'); };
  }, [imprimindo]);
  return (
    <>
      <button className="btn btn-principal btn-largo btn-grande nao-imprimir" onClick={() => setImprimindo(true)}>{texto}</button>
      {imprimindo && <div className="area-folhas">{ids.map((id) => pacote.porId[id] && <FolhaReceita key={id} r={pacote.porId[id]} />)}</div>}
    </>
  );
}

function SemanaImprimir({ semana, texto }) {
  const { pacote, dados } = useApp();
  const [imprimindo, setImprimindo] = useState(false);
  useEffect(() => {
    if (!imprimindo) return undefined;
    document.body.classList.add('imprimindo-folhas');
    const fim = () => { document.body.classList.remove('imprimindo-folhas'); setImprimindo(false); };
    window.addEventListener('afterprint', fim, { once: true });
    const t = setTimeout(() => window.print(), 200);
    return () => { clearTimeout(t); window.removeEventListener('afterprint', fim); document.body.classList.remove('imprimindo-folhas'); };
  }, [imprimindo]);
  return (
    <>
      <button className="btn btn-secundario btn-largo nao-imprimir" onClick={() => setImprimindo(true)}>{texto}</button>
      {imprimindo && (
        <div className="area-folhas">
          <section className="folha-receita">
            <h2>Cardápio da semana</h2>
            <TabelaSemana idDe={(d, k) => receitaDoPlano(pacote, dados.trocas, semana, d, k)} />
          </section>
        </div>
      )}
    </>
  );
}

export function ConteudoBonus({ bonus }) {
  const { pacote } = useApp();
  const receitasDe = (ids) => ids.map((id) => pacote.porId[id]).filter(Boolean);
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
        if (b.t === 'receitas_ids') return <ListaReceitas key={i} receitas={receitasDe(b.ids)} porPagina={12} />;
        if (b.t === 'plano') return <Fragment key={i}><PlanoCompleto /></Fragment>;
        if (b.t === 'plano_semanas') return <PlanoSemanas key={i} semanas={b.semanas} />;
        if (b.t === 'domingos') return <Domingos key={i} domingos={b.domingos} />;
        if (b.t === 'imprimir_receitas') return <ImprimirReceitas key={i} texto={b.texto} ids={b.ids} />;
        if (b.t === 'plano_semana_imprimir') return <SemanaImprimir key={i} semana={b.semana} texto={b.texto} />;
        if (b.t === 'imprimir') return <button key={i} className="btn btn-principal btn-largo btn-grande" onClick={() => window.print()}>{b.texto}</button>;
        return null;
      })}
    </article>
  );
}
