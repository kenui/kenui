'use client';
import Link from 'next/link';
import { useRouter } from 'next/navigation';
import { useState } from 'react';
import { Moldura } from '../../componentes/Moldura';
import { useApp } from '../../componentes/Provedor';
import { useAviso } from '../../componentes/Toast';
import { DIAS, REFEICOES, chaveRefeicao, opcoesDeTroca, receitaDoPlano, receitasDaSemana } from '../../lib/plano';
import { lerPequeno, gravarPequeno } from '../../lib/armazenamento';

function JanelaTroca({ pacote, alvo, escolher, fechar }) {
  const [quantas, setQuantas] = useState(12);
  const atual = pacote.porId[alvo.atual];
  const opcoes = opcoesDeTroca(pacote, alvo.atual, alvo.refeicao);
  return (
    <div className="janela" role="dialog" aria-modal="true" aria-label="Trocar refeição" onClick={(e) => e.target === e.currentTarget && fechar()}>
      <div className="janela-corpo">
        <h2>Trocar {alvo.nomeRefeicao.toLowerCase()} de {alvo.dia.toLowerCase()}</h2>
        <p className="nota">Agora: {atual?.nome}. Escolha outra receita:</p>
        {opcoes.slice(0, quantas).map((r) => (
          <button key={r.id} className="opcao" onClick={() => escolher(r.id)}>
            <span>{r.nome}<small>{r.tempo.total_min} min{r.low_carb ? ' · Low carb' : ''}</small></span>
            <span aria-hidden="true">›</span>
          </button>
        ))}
        {quantas < opcoes.length && <button className="btn btn-secundario" onClick={() => setQuantas((q) => q + 12)}>Ver mais opções</button>}
        <button className="btn btn-secundario" onClick={fechar}>Cancelar</button>
      </div>
    </div>
  );
}

function Plano() {
  const { pacote, dados, atualizar } = useApp();
  const router = useRouter();
  const [semana, setSemanaEstado] = useState(() => lerPequeno('semana', 0));
  const [alvo, setAlvo] = useState(null);
  const [toast, avisar] = useAviso();
  if (!pacote) return null;
  const setSemana = (n) => { setSemanaEstado(n); gravarPequeno('semana', n); };
  const trocas = dados.trocas;

  return (
    <>
      <div className="semanas" role="group" aria-label="Semana">
        {[0, 1, 2, 3].map((n) => <button key={n} className="chip" aria-pressed={semana === n} onClick={() => setSemana(n)}>Semana {n + 1}</button>)}
      </div>
      <button className="btn btn-principal btn-largo btn-grande" onClick={() => {
        atualizar('lista', { receitas: receitasDaSemana(pacote, trocas, semana), marcados: [] });
        router.push('/lista/');
      }}>Lista de compras da semana {semana + 1}</button>
      <h2 className="so-imprimir">Semana {semana + 1}</h2>
      {DIAS.map((dia, d) => (
        <section key={dia} className="dia">
          <h2 className="titulo-dia">{dia}</h2>
          {REFEICOES.map(([k, nome]) => {
            const id = receitaDoPlano(pacote, trocas, semana, d, k);
            const r = pacote.porId[id];
            return (
              <div key={k} className="refeicao">
                <div><small>{nome}</small><Link href={`/receita/?id=${id}`}>{r?.nome}</Link></div>
                <button className="btn-trocar" aria-label={`Trocar ${nome} de ${dia}`} onClick={() => setAlvo({ semana, dia, d, refeicao: k, nomeRefeicao: nome, atual: id })}>Trocar</button>
              </div>
            );
          })}
        </section>
      ))}
      <div className="bloco nao-imprimir">
        <button className="btn btn-secundario btn-largo" onClick={() => window.print()}>Imprimir esta semana</button>
        <Link className="btn btn-secundario btn-largo" href="/bonus/cardapio-4-semanas/">Versão para imprimir das 4 semanas</Link>
      </div>
      {alvo && (
        <JanelaTroca pacote={pacote} alvo={alvo} fechar={() => setAlvo(null)} escolher={(novo) => {
          atualizar('trocas', (t) => ({ ...t, [chaveRefeicao(alvo.semana, alvo.d, alvo.refeicao)]: novo }));
          setAlvo(null);
          avisar(`Trocado por ${pacote.porId[novo].nome}`);
        }} />
      )}
      {toast}
    </>
  );
}

export default function Pagina() {
  return <Moldura titulo="Plano de 4 semanas" ativa="plano"><Plano /></Moldura>;
}
