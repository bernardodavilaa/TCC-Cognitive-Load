-- Migration: registra eventos de acesso (login) por usuário, pra
-- rastreabilidade de uso individual (frequência de uso, Seção 3.6 do TCC).
CREATE TABLE IF NOT EXISTS public.access_logs (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id    uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  role       text,
  event      text NOT NULL DEFAULT 'login',
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_access_logs_user_id
  ON public.access_logs (user_id, created_at DESC);
