'use client';
// Estado do app: login, pacote de receitas (guardado no aparelho para uso offline)
// e dados da pessoa (favoritos, vistas, lista de compras, trocas do plano).
import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from 'react';
import { MODO_DEMO, supabase } from '../lib/supabase';
import { apagarTudo, gravarGrande, gravarPequeno, lerGrande, lerPequeno } from '../lib/armazenamento';
import { criarIndice } from '../lib/busca';

const Contexto = createContext(null);
export const useApp = () => useContext(Contexto);

const TRINTA_DIAS = 30 * 24 * 60 * 60 * 1000;

function prepararPacote(bruto) {
  if (!bruto) return null;
  const porId = Object.fromEntries(bruto.receitas.map((r) => [r.id, r]));
  const pacote = { ...bruto, porId };
  pacote.indice = criarIndice(pacote);
  return pacote;
}

function dadosIniciais() {
  return {
    favoritos: lerPequeno('favoritos', []),
    vistas: lerPequeno('vistas', []),
    lista: lerPequeno('lista', { receitas: [], marcados: [] }),
    trocas: lerPequeno('trocas', {}),
  };
}

export function Provedor({ children }) {
  const [status, setStatus] = useState('carregando');
  const [pacote, setPacote] = useState(null);
  const [email, setEmail] = useState('');
  const [dados, setDados] = useState({ favoritos: [], vistas: [], lista: { receitas: [], marcados: [] }, trocas: {} });
  const usuarioId = useRef(null);
  const sincronizar = useRef(null);

  const carregar = useCallback(async () => {
    setDados(dadosIniciais());
    if (MODO_DEMO) {
      const r = await fetch('/pacote-demo.json');
      setPacote(prepararPacote(await r.json()));
      setEmail('demonstracao@receitasbemleves');
      setStatus('pronto');
      return;
    }
    const s = supabase();
    const { data: { session } } = await s.auth.getSession();
    if (!session) { setStatus('sem_login'); return; }
    setEmail(session.user.email);
    usuarioId.current = session.user.id;

    const guardado = await lerGrande('pacote');
    const ultimaConferencia = lerPequeno('conferido_em', 0);
    if (guardado) { setPacote(prepararPacote(guardado)); setStatus('pronto'); }

    try {
      const { data, error } = await s.from('pacote_receitas').select('versao').order('publicado_em', { ascending: false }).limit(1);
      if (error) throw error;
      if (!data?.length) {
        // A regra de acesso do banco só libera o pacote para compras ativas.
        await apagarTudo();
        await s.auth.signOut();
        setPacote(null);
        setStatus('bloqueado');
        return;
      }
      gravarPequeno('conferido_em', Date.now());
      if (!guardado || guardado.versao !== data[0].versao) {
        const { data: completo, error: e2 } = await s.from('pacote_receitas').select('versao, conteudo').eq('versao', data[0].versao).single();
        if (e2) throw e2;
        const bruto = { ...completo.conteudo, versao: completo.versao };
        await gravarGrande('pacote', bruto);
        setPacote(prepararPacote(bruto));
        setStatus('pronto');
      }
      carregarDadosDaConta(s, session.user.id);
    } catch {
      // Sem internet: usa o que está guardado, desde que conferido nos últimos 30 dias.
      if (!guardado) setStatus('sem_internet');
      else if (Date.now() - ultimaConferencia > TRINTA_DIAS) setStatus('conferir');
    }
  }, []);

  async function carregarDadosDaConta(s, id) {
    const { data } = await s.from('dados_do_usuario').select('favoritos, trocas').eq('user_id', id).maybeSingle();
    if (!data) return;
    setDados((d) => {
      const novo = {
        ...d,
        favoritos: [...new Set([...(data.favoritos ?? []), ...d.favoritos])],
        trocas: { ...(data.trocas ?? {}), ...d.trocas },
      };
      gravarPequeno('favoritos', novo.favoritos);
      gravarPequeno('trocas', novo.trocas);
      return novo;
    });
  }

  useEffect(() => { carregar(); }, [carregar]);

  // Guarda no aparelho e manda uma cópia de favoritos e trocas para a conta (com atraso de 2 s).
  const atualizar = useCallback((campo, valor) => {
    setDados((d) => {
      const novo = { ...d, [campo]: typeof valor === 'function' ? valor(d[campo]) : valor };
      gravarPequeno(campo, novo[campo]);
      if (!MODO_DEMO && usuarioId.current && (campo === 'favoritos' || campo === 'trocas')) {
        clearTimeout(sincronizar.current);
        sincronizar.current = setTimeout(() => {
          supabase().from('dados_do_usuario').upsert({
            user_id: usuarioId.current, favoritos: novo.favoritos, trocas: novo.trocas, atualizado_em: new Date().toISOString(),
          }).then(() => {}, () => {});
        }, 2000);
      }
      return novo;
    });
  }, []);

  const sair = useCallback(async () => {
    await apagarTudo();
    if (!MODO_DEMO) await supabase().auth.signOut().catch(() => {});
    setPacote(null);
    setStatus(MODO_DEMO ? 'pronto' : 'sem_login');
    if (MODO_DEMO) carregar();
  }, [carregar]);

  const valor = useMemo(() => ({ status, pacote, email, dados, atualizar, sair, recarregar: carregar }), [status, pacote, email, dados, atualizar, sair, carregar]);
  return <Contexto.Provider value={valor}>{children}</Contexto.Provider>;
}
