-- Pergunta de triagem sobre ritmo de estudo (pedido do autor: alunos com
-- realidade social/educacional diferente devem receber uma adaptação mais
-- forte de linguagem e suporte, sem que isso seja dito ao aluno no chat).
-- Perguntada aos dois grupos (mesma tela de config. da sala), mas só o PAGE
-- usa o valor (ZPD/UDL da reformatação) -- o prompt base do controle não é
-- afetado. Valores esperados: 'tranquilo' | 'dificuldade' | 'nao_informado'.
ALTER TABLE public.perfil_cognitivo_afetivo
  ADD COLUMN IF NOT EXISTS ritmo_estudo text;
