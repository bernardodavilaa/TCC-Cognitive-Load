-- Migration: add matricula column to users, para vincular o pré-cadastro
-- coletado no Forms (nome, e-mail PUC, matrícula) à conta do aluno
ALTER TABLE public.users
  ADD COLUMN IF NOT EXISTS matricula text;
