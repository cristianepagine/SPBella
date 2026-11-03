import qrcode from "qrcode-generator";

/** Margem branca em volta do código, em módulos. A especificação pede 4 para a leitura funcionar. */
export const QR_QUIET_ZONE = 4;

/** Linhas de módulos (true = preto). Correção "M": aguenta papel um pouco amassado ou sujo. */
export function qrMatrix(value: string): boolean[][] {
  const code = qrcode(0, "M");
  code.addData(value);
  code.make();
  const size = code.getModuleCount();
  return Array.from({ length: size }, (_, row) =>
    Array.from({ length: size }, (_, col) => code.isDark(row, col)),
  );
}

/** QR code em SVG: fica nítido em qualquer tamanho, inclusive impresso. */
export function QrCode({
  value,
  label,
  className,
}: {
  value: string;
  label: string;
  className?: string;
}) {
  const matrix = qrMatrix(value);
  const box = matrix.length + QR_QUIET_ZONE * 2;
  const modules = matrix
    .flatMap((cells, row) =>
      cells.map((dark, col) =>
        dark ? `M${col + QR_QUIET_ZONE} ${row + QR_QUIET_ZONE}h1v1h-1z` : "",
      ),
    )
    .join("");
  return (
    <svg
      role="img"
      aria-label={label}
      viewBox={`0 0 ${box} ${box}`}
      shapeRendering="crispEdges"
      className={className}
    >
      <rect width={box} height={box} fill="#fff" />
      <path d={modules} fill="#000" />
    </svg>
  );
}
