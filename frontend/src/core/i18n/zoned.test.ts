import { describe, expect, it } from "vitest";

import {
  addDays,
  dayLabel,
  isoWeekday,
  localDate,
  minutesOfDay,
  mondayOf,
  timeLabel,
  zonedToUtc,
} from "./zoned";

describe("horário no fuso do estabelecimento", () => {
  it("vira o dia pelo fuso do salão, não pelo do aparelho", () => {
    // 02:30 UTC do dia 10 = 23:30 do dia 9 em São Paulo
    expect(localDate("2027-03-10T02:30:00Z", "America/Sao_Paulo")).toBe("2027-03-09");
    expect(localDate("2027-03-10T02:30:00Z", "UTC")).toBe("2027-03-10");
    expect(minutesOfDay("2027-03-10T02:30:00Z", "America/Sao_Paulo")).toBe(23 * 60 + 30);
  });

  it("mostra a hora em 24 h", () => {
    expect(timeLabel("2027-03-10T17:05:00Z", "America/Asuncion", "es-PY")).toBe("14:05");
  });

  it("conta dias sem cair em armadilha de fuso ou horário de verão", () => {
    expect(addDays("2027-02-28", 1)).toBe("2027-03-01");
    expect(addDays("2027-01-01", -1)).toBe("2026-12-31");
    // Nova York muda o relógio em 14/03/2027; o dia continua sendo dia
    expect(addDays("2027-03-13", 1)).toBe("2027-03-14");
  });

  it("semana começa na segunda (igual à API)", () => {
    expect(isoWeekday("2027-03-08")).toBe(0); // segunda
    expect(isoWeekday("2027-03-14")).toBe(6); // domingo
    expect(mondayOf("2027-03-14")).toBe("2027-03-08");
    expect(dayLabel("2027-03-09", "pt-BR")).toBe("ter., 09/03");
  });
});

describe("dia e hora do salão para UTC", () => {
  it("converte pelo fuso do estabelecimento", () => {
    expect(zonedToUtc("2026-11-03", "10:00", "America/Sao_Paulo")).toBe("2026-11-03T13:00:00.000Z");
    expect(zonedToUtc("2026-11-03", "23:30", "America/Asuncion")).toBe("2026-11-04T02:30:00.000Z");
  });

  it("acerta antes e depois de uma mudança de horário de verão", () => {
    // Nova York: 14/03/2027 adianta o relógio (UTC-5 → UTC-4)
    expect(zonedToUtc("2027-03-13", "10:00", "America/New_York")).toBe("2027-03-13T15:00:00.000Z");
    expect(zonedToUtc("2027-03-15", "10:00", "America/New_York")).toBe("2027-03-15T14:00:00.000Z");
  });
});
