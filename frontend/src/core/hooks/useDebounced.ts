import { useEffect, useState } from "react";

/** Devolve o valor só depois que ele parou de mudar por `delay` ms (para não buscar a cada tecla). */
export function useDebounced<T>(value: T, delay = 300): T {
  const [debounced, setDebounced] = useState(value);
  useEffect(() => {
    const timer = setTimeout(() => setDebounced(value), delay);
    return () => clearTimeout(timer);
  }, [value, delay]);
  return debounced;
}
