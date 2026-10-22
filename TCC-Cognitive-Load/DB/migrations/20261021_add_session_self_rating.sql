-- Grava a autoavaliação (nível atual) no momento em que cada sessão começa,
-- nos dois grupos -- não é uma pergunta nova (continua herdada da etapa
-- inicial/perfil, sem reperguntar na config da sala), é só granularidade de
-- log: antes só existia um valor "atual" no perfil, agora fica um retrato
-- por sessão. Só o grupo experimental usa esse valor na inferência de Bloom
-- do PAGE -- aqui é só o registro.
ALTER TABLE public.study_sessions
  ADD COLUMN IF NOT EXISTS self_rating_at_start int;
