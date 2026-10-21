-- Dados estruturados dos "temas de interesse" (chips: até 3 temas de uma
-- lista fixa + detalhe opcional por tema), usados pra análise separada do
-- texto livre que o PAGE/prompt base consome, e pra pré-preencher o
-- formulário em sessões futuras do mesmo aluno. Supersede o free-text de
-- "interesses_detalhe" (20261021_add_perfil_interesses_detalhe.sql): aquele
-- campo único e genérico demais virou uma lista estruturada por tema.
ALTER TABLE public.perfil_cognitivo_afetivo
  ADD COLUMN IF NOT EXISTS interesses_estruturado jsonb;
