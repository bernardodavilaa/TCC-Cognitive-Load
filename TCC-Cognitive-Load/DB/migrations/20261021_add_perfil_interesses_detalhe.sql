-- Elaboração obrigatória sobre o interesse declarado (pedido do autor:
-- "temas de interesse" sozinho era genérico demais pro PAGE ancorar
-- analogias de verdade -- agora o aluno descreve a experiência dele com
-- o tema, e isso alimenta a reformatação contextual).
ALTER TABLE public.perfil_cognitivo_afetivo
  ADD COLUMN IF NOT EXISTS interesses_detalhe text;
