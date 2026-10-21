-- Modo Estudo: alocação balanceada por aluno (Módulo A), registro de
-- atividade (B), regras de participação (C, calculadas em runtime a partir
-- de B — sem tabela própria), barra de progresso (D, idem), questionário
-- final (E) e apoio ao painel do pesquisador (F).
--
-- Ver especificacao_funcional_modo_estudo.md para o raciocínio completo.
-- Ativação por feature flag: classrooms.study_mode (default false,
-- reversível sem perda de dados do comportamento atual).

ALTER TABLE public.classrooms
  ADD COLUMN IF NOT EXISTS study_mode boolean NOT NULL DEFAULT false;

-- ============================================================
-- Módulo A — configuração travada do estudo (RN-8) e alocação
-- ============================================================

CREATE TABLE IF NOT EXISTS public.study_config (
  id                        uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  classroom_id              uuid NOT NULL REFERENCES public.classrooms(id) ON DELETE CASCADE,
  version                   int NOT NULL,
  janela_dias               int NOT NULL DEFAULT 21,
  idle_encerra_min          int NOT NULL DEFAULT 30,
  idle_cap_min              int NOT NULL DEFAULT 5,
  sessao_min_ativo_min      int NOT NULL DEFAULT 10,
  sessao_min_msg_aluno      int NOT NULL DEFAULT 6,
  duvida_min_palavras       int NOT NULL DEFAULT 5,
  ex_min_msg_aluno          int NOT NULL DEFAULT 3,
  min_analise_sessoes       int NOT NULL DEFAULT 1,
  questionario_min_sessoes  int NOT NULL DEFAULT 2,
  meta_sessoes              int NOT NULL DEFAULT 3,
  meta_sessoes_dias_distintos int NOT NULL DEFAULT 2,
  meta_duvidas              int NOT NULL DEFAULT 6,
  meta_exercicios           int NOT NULL DEFAULT 4,
  meta_questionario         int NOT NULL DEFAULT 1,
  peso_sessoes              numeric(4,2) NOT NULL DEFAULT 0.30,
  peso_duvidas              numeric(4,2) NOT NULL DEFAULT 0.20,
  peso_exercicios           numeric(4,2) NOT NULL DEFAULT 0.30,
  peso_questionario         numeric(4,2) NOT NULL DEFAULT 0.20,
  block_size                int NOT NULL DEFAULT 2,
  random_seed               bigint NOT NULL,
  justification             text,
  locked_at                 timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT ux_study_config_version UNIQUE (classroom_id, version)
);
CREATE INDEX IF NOT EXISTS ix_study_config_classroom_version
  ON public.study_config (classroom_id, version DESC);

-- Blocos permutados pré-gerados por estrato (RF-A3). `claimed_by` é
-- preenchido atomicamente via UPDATE ... WHERE claimed_by IS NULL ORDER BY
-- block_index, position LIMIT 1 (RF-A5) — Postgres serializa UPDATEs
-- concorrentes sobre o mesmo predicado, então duas alocações simultâneas
-- nunca reivindicam o mesmo slot.
CREATE TABLE IF NOT EXISTS public.study_allocation_blocks (
  id             uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  classroom_id   uuid NOT NULL REFERENCES public.classrooms(id) ON DELETE CASCADE,
  config_version int NOT NULL,
  stratum        text NOT NULL CHECK (stratum IN ('nenhuma','alguma')),
  block_index    int NOT NULL,
  position       int NOT NULL,
  group_name     text NOT NULL CHECK (group_name IN ('controle','experimental')),
  claimed_by     uuid REFERENCES public.users(id) ON DELETE SET NULL,
  claimed_at     timestamptz,
  CONSTRAINT ux_study_blocks_slot UNIQUE (classroom_id, config_version, stratum, block_index, position)
);
CREATE INDEX IF NOT EXISTS ix_study_blocks_free
  ON public.study_allocation_blocks (classroom_id, config_version, stratum, block_index, position)
  WHERE claimed_by IS NULL;

-- Participante alocado (RF-A1, RF-A4, RF-A8). Código anônimo não
-- sequencial (RF-A7/cegamento), linha de base da etapa inicial (RF-A0.2),
-- grupo e estrato imutáveis (RI-1, reforçado por trigger abaixo).
CREATE TABLE IF NOT EXISTS public.study_participants (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  student_id         uuid NOT NULL UNIQUE REFERENCES public.users(id) ON DELETE CASCADE,
  classroom_id       uuid NOT NULL REFERENCES public.classrooms(id) ON DELETE CASCADE,
  anon_code          text NOT NULL UNIQUE,
  stratum            text NOT NULL CHECK (stratum IN ('nenhuma','alguma')),
  group_name         text NOT NULL CHECK (group_name IN ('controle','experimental')),
  block_id           uuid NOT NULL REFERENCES public.study_allocation_blocks(id),
  config_version     int NOT NULL,
  e1_contato_previo  text NOT NULL CHECK (e1_contato_previo IN ('Não','Um pouco','Sim')),
  e2_nivel_atual     int NOT NULL CHECK (e2_nivel_atual BETWEEN 1 AND 5),
  e3_ja_cursou       text NOT NULL CHECK (e3_ja_cursou IN ('Sim','Não')),
  allocated_at       timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_study_participants_classroom
  ON public.study_participants (classroom_id, group_name, stratum);

CREATE OR REPLACE FUNCTION public.fn_study_participants_immutable()
RETURNS trigger AS $$
BEGIN
  IF NEW.group_name IS DISTINCT FROM OLD.group_name
     OR NEW.stratum IS DISTINCT FROM OLD.stratum
     OR NEW.student_id IS DISTINCT FROM OLD.student_id
     OR NEW.e1_contato_previo IS DISTINCT FROM OLD.e1_contato_previo
     OR NEW.e2_nivel_atual IS DISTINCT FROM OLD.e2_nivel_atual
     OR NEW.e3_ja_cursou IS DISTINCT FROM OLD.e3_ja_cursou THEN
    RAISE EXCEPTION 'study_participants: grupo/estrato/linha de base são imutáveis (RI-1)';
  END IF;
  RETURN NEW;
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_study_participants_immutable ON public.study_participants;
CREATE TRIGGER trg_study_participants_immutable
  BEFORE UPDATE ON public.study_participants
  FOR EACH ROW EXECUTE FUNCTION public.fn_study_participants_immutable();

-- ============================================================
-- Módulo B — sessões, exercícios e log de eventos (append-only)
-- ============================================================

-- Uma `study_session` é a unidade de "sessão" do glossário (do 1º envio até
-- encerramento explícito/por inatividade), distinta de `chats` (que é o
-- registro do PDF/transcrição final gerado só quando a sessão fecha).
CREATE TABLE IF NOT EXISTS public.study_sessions (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id         uuid NOT NULL REFERENCES public.study_participants(id) ON DELETE CASCADE,
  classroom_id           uuid NOT NULL REFERENCES public.classrooms(id) ON DELETE CASCADE,
  effective_group        text NOT NULL CHECK (effective_group IN ('controle','experimental')),
  config_version         int NOT NULL,
  chat_id                uuid REFERENCES public.chats(id) ON DELETE SET NULL,
  started_at             timestamptz NOT NULL DEFAULT now(),
  ended_at               timestamptz,
  end_reason             text CHECK (end_reason IN ('manual','idle_timeout')),
  active_seconds         int NOT NULL DEFAULT 0,
  student_message_count  int NOT NULL DEFAULT 0,
  evaluation_pending     boolean NOT NULL DEFAULT true,
  is_valid               boolean,
  had_fallback           boolean NOT NULL DEFAULT false
);
CREATE INDEX IF NOT EXISTS ix_study_sessions_participant
  ON public.study_sessions (participant_id, started_at);
CREATE INDEX IF NOT EXISTS ix_study_sessions_open
  ON public.study_sessions (participant_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS public.study_exercises (
  id                     uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  session_id             uuid NOT NULL REFERENCES public.study_sessions(id) ON DELETE CASCADE,
  participant_id         uuid NOT NULL REFERENCES public.study_participants(id) ON DELETE CASCADE,
  started_at             timestamptz NOT NULL DEFAULT now(),
  ended_at               timestamptz,
  status                 text NOT NULL DEFAULT 'em_andamento'
                           CHECK (status IN ('em_andamento','concluido','desistiu','interrompido')),
  motivo_desistencia     text,
  student_message_count  int NOT NULL DEFAULT 0
);
CREATE INDEX IF NOT EXISTS ix_study_exercises_session ON public.study_exercises (session_id);
CREATE INDEX IF NOT EXISTS ix_study_exercises_open ON public.study_exercises (session_id) WHERE ended_at IS NULL;

CREATE TABLE IF NOT EXISTS public.study_events (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id     uuid NOT NULL REFERENCES public.study_participants(id) ON DELETE CASCADE,
  classroom_id       uuid NOT NULL REFERENCES public.classrooms(id) ON DELETE CASCADE,
  effective_group    text NOT NULL CHECK (effective_group IN ('controle','experimental')),
  event_type         text NOT NULL CHECK (event_type IN (
                        'login','session_start','session_end','message',
                        'exercise_start','exercise_end',
                        'evaluation_submitted','questionnaire_submitted'
                      )),
  session_id         uuid REFERENCES public.study_sessions(id) ON DELETE SET NULL,
  exercise_id        uuid REFERENCES public.study_exercises(id) ON DELETE SET NULL,
  message_category   text CHECK (message_category IN ('teorica','exercicio','outra')),
  meta               jsonb,
  created_at         timestamptz NOT NULL DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_study_events_participant
  ON public.study_events (participant_id, created_at);

CREATE OR REPLACE FUNCTION public.fn_study_events_append_only()
RETURNS trigger AS $$
BEGIN
  RAISE EXCEPTION 'study_events é append-only (RI-2)';
END;
$$ LANGUAGE plpgsql;

DROP TRIGGER IF EXISTS trg_study_events_no_update ON public.study_events;
CREATE TRIGGER trg_study_events_no_update
  BEFORE UPDATE ON public.study_events
  FOR EACH ROW EXECUTE FUNCTION public.fn_study_events_append_only();

DROP TRIGGER IF EXISTS trg_study_events_no_delete ON public.study_events;
CREATE TRIGGER trg_study_events_no_delete
  BEFORE DELETE ON public.study_events
  FOR EACH ROW EXECUTE FUNCTION public.fn_study_events_append_only();

-- ============================================================
-- Módulo E — questionário final (uma resposta por participante)
-- ============================================================

CREATE TABLE IF NOT EXISTS public.study_final_questionnaire (
  id                       uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  participant_id           uuid NOT NULL UNIQUE REFERENCES public.study_participants(id) ON DELETE CASCADE,
  group_name               text NOT NULL CHECK (group_name IN ('controle','experimental')),
  q1_ajudou_estudos        int NOT NULL CHECK (q1_ajudou_estudos BETWEEN 1 AND 5),
  q2_recomendaria          int NOT NULL CHECK (q2_recomendaria BETWEEN 1 AND 5),
  q3_exemplos_relevantes   int NOT NULL CHECK (q3_exemplos_relevantes BETWEEN 1 AND 5),
  q4_reduziu_ansiedade     int NOT NULL CHECK (q4_reduziu_ansiedade BETWEEN 1 AND 5),
  q5_facil_entender        int NOT NULL CHECK (q5_facil_entender BETWEEN 1 AND 5),
  q6_nps                   int CHECK (q6_nps BETWEEN 0 AND 10),
  q7_comentario            text,
  submitted_at             timestamptz NOT NULL DEFAULT now()
);
