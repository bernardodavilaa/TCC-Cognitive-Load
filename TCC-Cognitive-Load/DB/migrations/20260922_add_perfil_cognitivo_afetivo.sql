-- Migration: cria a tabela de perfil cognitivo-afetivo do aluno, persistido
-- entre sessões e consumido pelo Módulo PAGE de Reformatação Contextual
-- (memória não-paramétrica, cf. Koopman et al. / PLUM).
CREATE TABLE IF NOT EXISTS public.perfil_cognitivo_afetivo (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id             uuid NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  curso_periodo          text,
  contato_previo         text,
  interesses             text,
  estilo_preferido       text,
  detalhamento_preferido text,
  autoavaliacao          int,
  updated_at             timestamptz NOT NULL DEFAULT now()
);
