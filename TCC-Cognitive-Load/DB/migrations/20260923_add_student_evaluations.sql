-- Migration: avaliação pós-chat do aluno (escala de Paas + Likert de
-- satisfação/NPS, Seção 3.6 do TCC), aplicada tanto no grupo controle
-- quanto no experimental (page_enabled) pra permitir comparação estatística.
CREATE TABLE IF NOT EXISTS public.student_evaluations (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  chat_id      uuid REFERENCES public.chats(id) ON DELETE SET NULL,
  student_id   uuid NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
  classroom_id uuid REFERENCES public.classrooms(id) ON DELETE SET NULL,
  page_enabled boolean,
  paas_score   int NOT NULL,
  utilidade    int NOT NULL,
  exemplos     int NOT NULL,
  qualidade    int NOT NULL,
  nps          int NOT NULL,
  comentario   text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_student_evaluations_classroom
  ON public.student_evaluations (classroom_id, page_enabled);
