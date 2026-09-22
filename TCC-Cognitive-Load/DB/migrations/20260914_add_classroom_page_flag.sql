-- Migration: add page_enabled flag to classrooms, para o desenho
-- quasi-experimental (turmas designadas como grupo controle ou experimental
-- do Módulo PAGE de Reformatação Contextual)
ALTER TABLE public.classrooms
  ADD COLUMN IF NOT EXISTS page_enabled boolean NOT NULL DEFAULT false;
