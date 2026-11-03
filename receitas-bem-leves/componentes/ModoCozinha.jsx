'use client';
// Modo cozinha: um passo por vez, letra bem grande, tela sem apagar (Wake Lock) e timer.
import { useCallback, useEffect, useRef, useState } from 'react';

export function ModoCozinha({ receita, fechar }) {
  const [passo, setPasso] = useState(0);
  const [telaAcesa, setTelaAcesa] = useState(false);
  const [fim, setFim] = useState(null);
  const [agora, setAgora] = useState(Date.now());
  const trava = useRef(null);
  const p = receita.preparo[passo];
  const ultimo = passo === receita.preparo.length - 1;

  const pedirTelaAcesa = useCallback(async () => {
    try {
      if ('wakeLock' in navigator) {
        trava.current = await navigator.wakeLock.request('screen');
        setTelaAcesa(true);
        trava.current.addEventListener('release', () => setTelaAcesa(false));
      }
    } catch { setTelaAcesa(false); }
  }, []);

  useEffect(() => {
    pedirTelaAcesa();
    document.documentElement.requestFullscreen?.().catch(() => {});
    // A trava se solta quando a pessoa sai do app; pede de novo ao voltar.
    const voltar = () => { if (document.visibilityState === 'visible') pedirTelaAcesa(); };
    document.addEventListener('visibilitychange', voltar);
    return () => {
      document.removeEventListener('visibilitychange', voltar);
      trava.current?.release().catch(() => {});
      if (document.fullscreenElement) document.exitFullscreen().catch(() => {});
    };
  }, [pedirTelaAcesa]);

  useEffect(() => {
    if (!fim) return undefined;
    const t = setInterval(() => setAgora(Date.now()), 500);
    return () => clearInterval(t);
  }, [fim]);

  const resta = fim ? Math.max(0, fim - agora) : null;
  useEffect(() => {
    if (resta === 0) { try { navigator.vibrate?.([400, 200, 400]); } catch {} }
  }, [resta]);

  const ir = (delta) => {
    if (delta > 0 && ultimo) { fechar(); return; }
    setFim(null);
    setPasso((n) => Math.max(0, Math.min(receita.preparo.length - 1, n + delta)));
  };
  const relogio = resta === null ? `${p.temporizador_min}:00` : resta ? `${Math.floor(resta / 60000)}:${String(Math.floor((resta % 60000) / 1000)).padStart(2, '0')}` : 'Tempo esgotado!';

  return (
    <div className="cozinha" role="dialog" aria-modal="true" aria-label={`Modo cozinha: ${receita.nome}`}>
      <div className="topo-cozinha">
        <span className="contador">Passo {passo + 1} de {receita.preparo.length}</span>
        <button className="fechar" onClick={fechar}>Fechar</button>
      </div>
      <div className="passo" aria-live="polite">
        <div>{p.texto}</div>
        {p.aviso && <div className="atencao">Atenção: {p.aviso}</div>}
        {p.temporizador_min ? (
          <div className="timer">
            <b>{relogio}</b>
            <button className="btn btn-principal" onClick={() => { setAgora(Date.now()); setFim(Date.now() + p.temporizador_min * 60000); }}>
              {fim ? 'Recomeçar' : 'Iniciar'} {p.temporizador_min} min
            </button>
          </div>
        ) : null}
      </div>
      <p className="tela-ligada">{telaAcesa ? 'A tela vai ficar acesa enquanto você cozinha.' : 'Seu celular pode apagar a tela sozinho. Toque nela de vez em quando.'}</p>
      <div className="navegar">
        <button className="anterior" onClick={() => ir(-1)} disabled={passo === 0}>‹ Anterior</button>
        <button className="btn btn-principal" onClick={() => ir(1)}>{ultimo ? 'Terminei' : 'Próximo ›'}</button>
      </div>
    </div>
  );
}
