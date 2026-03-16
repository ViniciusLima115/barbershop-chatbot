"use client";

import Link from "next/link";
import { useEffect, useState } from "react";
import { useParams } from "next/navigation";

import {
  getBookingByToken,
  lookupPublicBarbershopById,
  rescheduleBookingByToken,
  PublicAgendamentoTokenResponse,
  PublicLookupResponse,
} from "@/services/api";

function hojeISO() {
  return new Date().toISOString().slice(0, 10);
}

function formatarDataHora(valor: string) {
  const data = new Date(valor);
  if (Number.isNaN(data.getTime())) return valor;
  return data.toLocaleString("pt-BR", {
    weekday: "long",
    day: "2-digit",
    month: "long",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
  });
}

export default function ReagendarPage() {
  const params = useParams<{ token: string }>();
  const token = params?.token ?? "";

  const [loadingBooking, setLoadingBooking] = useState(true);
  const [loadingSlots, setLoadingSlots] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [erro, setErro] = useState<string | null>(null);
  const [sucesso, setSucesso] = useState<string | null>(null);
  const [booking, setBooking] = useState<PublicAgendamentoTokenResponse | null>(null);
  const [lookup, setLookup] = useState<PublicLookupResponse | null>(null);

  const [today] = useState(() => hojeISO());
  const [data, setData] = useState(() => hojeISO());
  const [barbeiroId, setBarbeiroId] = useState<number | null>(null);
  const [servicoId, setServicoId] = useState<number | null>(null);
  const [horaInicio, setHoraInicio] = useState<string | null>(null);

  useEffect(() => {
    if (!token) return;
    let ativo = true;

    async function carregar() {
      setLoadingBooking(true);
      setErro(null);
      try {
        const b = await getBookingByToken(token);
        if (!ativo) return;
        setBooking(b);
        setBarbeiroId(b.barbeiro_id);
        setServicoId(b.servico_id);
        const dataExistente = b.data_hora_inicio.slice(0, 10);
        setData(dataExistente >= hojeISO() ? dataExistente : hojeISO());
      } catch (err) {
        if (!ativo) return;
        setErro(err instanceof Error ? err.message : "Não foi possível carregar o agendamento.");
      } finally {
        if (ativo) setLoadingBooking(false);
      }
    }

    carregar();
    return () => { ativo = false; };
  }, [token]);

  useEffect(() => {
    if (!booking || !barbeiroId || !servicoId || !data) return;
    let ativo = true;

    async function carregarSlots() {
      setLoadingSlots(true);
      try {
        const resultado = await lookupPublicBarbershopById({
          barbearia_id: booking!.barbearia_id,
          data,
          barbeiro_id: barbeiroId!,
          servico_id: servicoId!,
        });
        if (!ativo) return;
        setLookup(resultado);
        setHoraInicio((atual) => {
          if (!atual) return null;
          return resultado.horarios_grade.some((s) => s.hora === atual && s.disponivel)
            ? atual
            : null;
        });
      } catch {
        if (!ativo) return;
      } finally {
        if (ativo) setLoadingSlots(false);
      }
    }

    carregarSlots();
    return () => { ativo = false; };
  }, [booking, barbeiroId, servicoId, data]);

  async function onSubmit() {
    if (!horaInicio) {
      setErro("Selecione um horário disponível.");
      return;
    }
    setSubmitting(true);
    setErro(null);
    setSucesso(null);
    try {
      const dataHoraInicio = `${data}T${horaInicio}:00`;
      const atualizado = await rescheduleBookingByToken(token, dataHoraInicio);
      setBooking(atualizado);
      setSucesso("Agendamento reagendado com sucesso!");
      setHoraInicio(null);
    } catch (err) {
      setErro(err instanceof Error ? err.message : "Não foi possível reagendar.");
    } finally {
      setSubmitting(false);
    }
  }

  const linkBarbearia = booking?.slug
    ? `/${booking.slug}`
    : booking
      ? `/agendar/${booking.barbearia_id}`
      : "/";

  const inputStyle: React.CSSProperties = {
    width: "100%",
    padding: "10px 12px",
    borderRadius: 10,
    border: "1.5px solid #e5d5c5",
    backgroundColor: "#faf7f4",
    fontSize: 14,
    color: "#1a120b",
    outline: "none",
    boxSizing: "border-box",
  };

  const labelStyle: React.CSSProperties = {
    display: "flex",
    flexDirection: "column",
    gap: 5,
  };

  const labelTextStyle: React.CSSProperties = {
    fontSize: 10,
    fontWeight: 700,
    letterSpacing: "0.14em",
    textTransform: "uppercase",
    color: "#c36b2d",
    margin: 0,
  };

  return (
    <div
      style={{
        minHeight: "100vh",
        backgroundColor: "#f5efe7",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        fontFamily: "system-ui, -apple-system, sans-serif",
      }}
    >
      {/* Top brand bar */}
      <div
        style={{
          width: "100%",
          backgroundColor: "#1a120b",
          padding: "14px 24px",
          display: "flex",
          alignItems: "center",
          gap: "10px",
        }}
      >
        <div
          style={{
            width: 32,
            height: 32,
            borderRadius: 8,
            backgroundColor: "#c36b2d",
            display: "flex",
            alignItems: "center",
            justifyContent: "center",
            fontSize: 16,
          }}
        >
          ✂
        </div>
        <span style={{ color: "#f5efe7", fontWeight: 700, fontSize: 15, letterSpacing: "0.02em" }}>
          Virtual Barber
        </span>
      </div>

      {/* Card */}
      <div
        style={{
          width: "100%",
          maxWidth: 580,
          margin: "40px 16px",
          backgroundColor: "#ffffff",
          borderRadius: 20,
          boxShadow: "0 4px 24px rgba(0,0,0,0.10)",
          overflow: "hidden",
        }}
      >
        {/* Header */}
        <div
          style={{
            background: "linear-gradient(135deg, #1a120b 0%, #3b1f0d 100%)",
            padding: "32px 32px 28px",
          }}
        >
          <p
            style={{
              margin: 0,
              fontSize: 11,
              fontWeight: 700,
              letterSpacing: "0.18em",
              textTransform: "uppercase",
              color: "#f2c89a",
            }}
          >
            Email de agendamento
          </p>
          <h1
            style={{
              margin: "10px 0 6px",
              fontSize: 26,
              fontWeight: 800,
              color: "#ffffff",
              lineHeight: 1.2,
            }}
          >
            Escolher novo horário
          </h1>
          <p style={{ margin: 0, fontSize: 14, color: "#e8d5c0" }}>
            Selecione data e horário para seu reagendamento.
          </p>
        </div>

        {/* Body */}
        <div style={{ padding: "28px 32px 32px" }}>

          {loadingBooking && (
            <p style={{ color: "#9ca3af", fontSize: 14, margin: 0 }}>
              Carregando agendamento...
            </p>
          )}

          {!loadingBooking && !booking && (
            <div
              style={{
                backgroundColor: "#fff1f2",
                border: "1px solid #fecdd3",
                borderRadius: 12,
                padding: "12px 16px",
                fontSize: 14,
                color: "#9f1239",
              }}
            >
              {erro ?? "Agendamento não encontrado."}
            </div>
          )}

          {booking && (
            <>
              {/* Current booking info */}
              <div
                style={{
                  backgroundColor: "#faf7f4",
                  borderRadius: 14,
                  padding: "20px 22px",
                  marginBottom: 24,
                  display: "grid",
                  gridTemplateColumns: "1fr 1fr",
                  gap: "16px 24px",
                }}
              >
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Cliente</p>
                  <p style={{ margin: 0, fontSize: 15, fontWeight: 600, color: "#1a120b" }}>
                    {booking.cliente_nome}
                  </p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Horário atual</p>
                  <p style={{ margin: 0, fontSize: 13, fontWeight: 500, color: "#1a120b", lineHeight: 1.4 }}>
                    {formatarDataHora(booking.data_hora_inicio)}
                  </p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Serviço</p>
                  <p style={{ margin: 0, fontSize: 14, color: "#1a120b" }}>{booking.servico_nome}</p>
                </div>
                <div>
                  <p style={{ ...labelTextStyle, marginBottom: 4 }}>Barbeiro</p>
                  <p style={{ margin: 0, fontSize: 14, color: "#1a120b" }}>{booking.barbeiro_nome}</p>
                </div>
              </div>

              {/* Feedback */}
              {sucesso && (
                <div
                  style={{
                    backgroundColor: "#f0fdf4",
                    border: "1px solid #bbf7d0",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#14532d",
                    fontWeight: 600,
                  }}
                >
                  ✓ {sucesso}
                </div>
              )}

              {erro && !sucesso && (
                <div
                  style={{
                    backgroundColor: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#9f1239",
                  }}
                >
                  {erro}
                </div>
              )}

              {booking.status === "cancelado" && (
                <div
                  style={{
                    backgroundColor: "#fff1f2",
                    border: "1px solid #fecdd3",
                    borderRadius: 12,
                    padding: "12px 16px",
                    marginBottom: 20,
                    fontSize: 14,
                    color: "#9f1239",
                  }}
                >
                  Este agendamento foi cancelado e não pode ser reagendado.
                </div>
              )}

              {!sucesso && booking.status !== "cancelado" && (
                <>
                  {/* Selectors */}
                  {lookup && (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "1fr 1fr 1fr",
                        gap: 12,
                        marginBottom: 20,
                      }}
                    >
                      <label style={labelStyle}>
                        <span style={labelTextStyle}>Barbeiro</span>
                        <select
                          style={inputStyle}
                          value={barbeiroId ?? ""}
                          onChange={(e) => {
                            setBarbeiroId(Number(e.target.value));
                            setHoraInicio(null);
                          }}
                        >
                          {lookup.barbeiros.map((b) => (
                            <option key={b.id} value={b.id}>{b.nome}</option>
                          ))}
                        </select>
                      </label>

                      <label style={labelStyle}>
                        <span style={labelTextStyle}>Serviço</span>
                        <select
                          style={inputStyle}
                          value={servicoId ?? ""}
                          onChange={(e) => {
                            setServicoId(Number(e.target.value));
                            setHoraInicio(null);
                          }}
                        >
                          {lookup.servicos.map((s) => (
                            <option key={s.id} value={s.id}>{s.nome}</option>
                          ))}
                        </select>
                      </label>

                      <label style={labelStyle}>
                        <span style={labelTextStyle}>Data</span>
                        <input
                          type="date"
                          style={inputStyle}
                          min={today}
                          value={data}
                          onChange={(e) => {
                            setData(e.target.value);
                            setHoraInicio(null);
                          }}
                        />
                      </label>
                    </div>
                  )}

                  {/* Time slots */}
                  {loadingSlots ? (
                    <p style={{ color: "#9ca3af", fontSize: 13, marginBottom: 20 }}>
                      Carregando horários...
                    </p>
                  ) : lookup && lookup.horarios_grade.length > 0 ? (
                    <div
                      style={{
                        display: "grid",
                        gridTemplateColumns: "repeat(5, 1fr)",
                        gap: 8,
                        marginBottom: 24,
                      }}
                    >
                      {lookup.horarios_grade.map((slot) => (
                        <button
                          key={slot.hora}
                          type="button"
                          disabled={!slot.disponivel}
                          onClick={() => setHoraInicio(slot.hora)}
                          style={{
                            padding: "10px 4px",
                            borderRadius: 10,
                            border: "1.5px solid",
                            borderColor: !slot.disponivel
                              ? "#e5d5c5"
                              : horaInicio === slot.hora
                                ? "#c36b2d"
                                : "#e5d5c5",
                            backgroundColor: !slot.disponivel
                              ? "#faf7f4"
                              : horaInicio === slot.hora
                                ? "#c36b2d"
                                : "#ffffff",
                            color: !slot.disponivel
                              ? "#c4a882"
                              : horaInicio === slot.hora
                                ? "#ffffff"
                                : "#1a120b",
                            fontSize: 13,
                            fontWeight: 600,
                            cursor: slot.disponivel ? "pointer" : "not-allowed",
                            opacity: slot.disponivel ? 1 : 0.5,
                            display: "flex",
                            flexDirection: "column",
                            alignItems: "center",
                            gap: 2,
                          }}
                        >
                          <span>{slot.hora}</span>
                          <span style={{ fontSize: 10, fontWeight: 400, opacity: 0.7 }}>
                            {slot.disponivel ? "Livre" : "Ocup."}
                          </span>
                        </button>
                      ))}
                    </div>
                  ) : lookup ? (
                    <p style={{ color: "#9ca3af", fontSize: 13, marginBottom: 20 }}>
                      Nenhum horário disponível nesta data.
                    </p>
                  ) : null}

                  <button
                    type="button"
                    disabled={submitting || !horaInicio}
                    onClick={onSubmit}
                    style={{
                      width: "100%",
                      padding: "14px 20px",
                      borderRadius: 12,
                      border: "none",
                      backgroundColor: "#c36b2d",
                      color: "#ffffff",
                      fontSize: 15,
                      fontWeight: 700,
                      cursor: submitting || !horaInicio ? "not-allowed" : "pointer",
                      opacity: submitting || !horaInicio ? 0.6 : 1,
                      transition: "opacity 0.15s",
                    }}
                  >
                    {submitting ? "Reagendando..." : "Confirmar novo horário"}
                  </button>
                </>
              )}

              {(sucesso || booking.status === "cancelado") && (
                <Link
                  href={linkBarbearia}
                  style={{
                    display: "block",
                    textAlign: "center",
                    marginTop: 12,
                    padding: "13px 20px",
                    borderRadius: 12,
                    border: "1.5px solid #e5d5c5",
                    color: "#3b1f0d",
                    fontSize: 14,
                    fontWeight: 600,
                    textDecoration: "none",
                  }}
                >
                  Voltar para o site da barbearia →
                </Link>
              )}
            </>
          )}
        </div>
      </div>

      {/* Footer */}
      <p style={{ fontSize: 12, color: "#a18070", marginBottom: 32 }}>
        Powered by Virtual Barber
      </p>
    </div>
  );
}
