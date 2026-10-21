-- Fechamento preguiçoso de sessões abandonadas (RF-B3): precisamos de um
-- timestamp de última atividade real pra decidir com segurança se uma
-- sessão aberta foi esquecida (aba fechada sem "Encerrar Chat") em vez de
-- só assumir um tempo fixo desde o início.
ALTER TABLE public.study_sessions
  ADD COLUMN IF NOT EXISTS last_activity_at timestamptz NOT NULL DEFAULT now();
