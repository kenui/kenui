'use client';
import { useSearchParams } from 'next/navigation';
import { Suspense, useEffect, useMemo, useState } from 'react';
import { Moldura } from '../../componentes/Moldura';
import { ListaReceitas } from '../../componentes/Receita';
import { useApp } from '../../componentes/Provedor';
import { FILTROS_VAZIOS, filtrarReceitas, ingredientesParaFiltro } from '../../lib/busca';
import { lerPequeno, gravarPequeno } from '../../lib/armazenamento';

const NOMES_DESTAQUE = { cafe_sem_pao: 'Café da manhã sem pão', substitutos_do_pao: 'Substitutos do pão', doces_e_bolos: 'Doces e bolos', rapidas_15min: 'Rápidas até 15 min' };
const TEMPOS = [[0, 'Qualquer tempo'], [15, 'Até 15 min'], [30, 'Até 30 min'], [60, 'Até 60 min']];

function Receitas() {
  const { pacote } = useApp();
  const params = useSearchParams();
  const [f, setF] = useState(() => ({ ...FILTROS_VAZIOS, ...lerPequeno('filtros', {}) }));

  // Links vindos do Início (?busca= ou ?destaque=) começam uma busca nova.
  useEffect(() => {
    const busca = params.get('busca');
    const destaque = params.get('destaque');
    if (busca !== null || destaque !== null) setF({ ...FILTROS_VAZIOS, busca: busca ?? '', destaque: destaque ?? '' });
  }, [params]);
  useEffect(() => { gravarPequeno('filtros', f); }, [f]);

  const lista = useMemo(() => (pacote ? filtrarReceitas(pacote, pacote.indice, f) : []), [pacote, f]);
  const opcoesEmCasa = useMemo(() => (pacote ? ingredientesParaFiltro(pacote) : []), [pacote]);
  if (!pacote) return null;
  const muda = (campo, valor) => setF((x) => ({ ...x, [campo]: valor }));
  const temFiltro = JSON.stringify(f) !== JSON.stringify(FILTROS_VAZIOS);

  return (
    <>
      <form className="busca" role="search" onSubmit={(e) => { e.preventDefault(); document.activeElement?.blur(); }}>
        <input id="busca-receitas" type="search" placeholder="Buscar: pão, bolo, frango…" aria-label="Buscar receita ou ingrediente" value={f.busca} onChange={(e) => muda('busca', e.target.value)} autoComplete="off" />
      </form>
      <div className="filtros">
        {f.destaque && <div className="chips"><button className="chip" aria-pressed="true" onClick={() => muda('destaque', '')}>{NOMES_DESTAQUE[f.destaque]} ✕</button></div>}
        <div className="chips" role="group" aria-label="Categoria">
          <button className="chip" aria-pressed={!f.categoria} onClick={() => muda('categoria', '')}>Todas</button>
          {Object.entries(pacote.categorias).map(([id, nome]) => (
            <button key={id} className="chip" aria-pressed={f.categoria === id} onClick={() => muda('categoria', id)}>{nome}</button>
          ))}
        </div>
        <div className="chips" role="group" aria-label="Tempo de preparo">
          {TEMPOS.map(([t, nome]) => <button key={t} className="chip" aria-pressed={f.tempo === t} onClick={() => muda('tempo', t)}>{nome}</button>)}
          <button className="chip" aria-pressed={f.lowCarb} onClick={() => muda('lowCarb', !f.lowCarb)}>Low carb</button>
        </div>
        <div className="campo">
          <label htmlFor="em-casa">Tenho em casa:</label>
          <select id="em-casa" value={f.emCasa} onChange={(e) => muda('emCasa', e.target.value)}>
            <option value="">Qualquer ingrediente</option>
            {opcoesEmCasa.map((id) => <option key={id} value={id}>{pacote.ingredientes[id].nome}</option>)}
          </select>
        </div>
      </div>
      <p className="contagem" aria-live="polite">{lista.length} {lista.length === 1 ? 'receita encontrada' : 'receitas encontradas'}</p>
      {lista.length
        ? <ListaReceitas key={JSON.stringify(f)} receitas={lista} />
        : <div className="vazio">Nenhuma receita com esses filtros.</div>}
      {temFiltro && <button className="btn btn-secundario btn-largo" onClick={() => setF(FILTROS_VAZIOS)}>Limpar filtros</button>}
    </>
  );
}

export default function Pagina() {
  return <Moldura titulo="Receitas" ativa="receitas"><Suspense><Receitas /></Suspense></Moldura>;
}
