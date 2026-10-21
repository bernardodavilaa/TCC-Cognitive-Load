-- Novo item na barra de progresso: preencher os "temas de interesse"
-- (chips) conta como dose de personalização recebida -- pedido do autor pra
-- medir melhor o quanto a personalização de fato aconteceu, não só
-- sessões/dúvidas/exercícios/questionário. Rebalanceia os pesos existentes
-- pra continuarem somando 1.0 (100%) quando todas as metas são > 0:
-- sessões 0.30->0.25, dúvidas 0.20->0.15, exercícios 0.30->0.25,
-- questionário fica 0.20, interesses entra com 0.15.
ALTER TABLE public.study_config
  ADD COLUMN IF NOT EXISTS peso_interesses numeric(4,2) NOT NULL DEFAULT 0.15;

ALTER TABLE public.study_config
  ALTER COLUMN peso_sessoes SET DEFAULT 0.25,
  ALTER COLUMN peso_duvidas SET DEFAULT 0.15,
  ALTER COLUMN peso_exercicios SET DEFAULT 0.25;

-- Rebalanceia linhas já existentes (só dados de teste até aqui -- o estudo
-- real ainda não começou) pra já refletir o novo split.
UPDATE public.study_config
SET peso_sessoes = 0.25, peso_duvidas = 0.15, peso_exercicios = 0.25
WHERE peso_sessoes = 0.30 AND peso_duvidas = 0.20 AND peso_exercicios = 0.30;
