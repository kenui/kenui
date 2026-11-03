'use client';
// Mensagem curta que aparece por 2,6 segundos ("Salva nos favoritos").
import { useCallback, useRef, useState } from 'react';

export function useAviso() {
  const [texto, setTexto] = useState('');
  const tempo = useRef(null);
  const avisar = useCallback((t) => {
    setTexto(t);
    clearTimeout(tempo.current);
    tempo.current = setTimeout(() => setTexto(''), 2600);
  }, []);
  const elemento = <div className="toast" role="status" hidden={!texto}>{texto}</div>;
  return [elemento, avisar];
}
