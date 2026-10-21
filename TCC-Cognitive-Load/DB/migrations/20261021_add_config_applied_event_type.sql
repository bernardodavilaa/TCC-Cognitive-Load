-- Novo event_type 'config_applied' em study_events: mede o esforço de
-- preencher a configuração da sala (RF novo -- tempo entre abrir a tela de
-- configuração e clicar em "Aplicar Configuração da Sala"), guardado em
-- meta.seconds_to_apply. Precisa recriar o CHECK constraint porque não foi
-- criado com nome próprio (usa o nome padrão do Postgres).
ALTER TABLE public.study_events
  DROP CONSTRAINT IF EXISTS study_events_event_type_check;
ALTER TABLE public.study_events
  ADD CONSTRAINT study_events_event_type_check CHECK (event_type IN (
    'login', 'session_start', 'session_end', 'message',
    'exercise_start', 'exercise_end',
    'evaluation_submitted', 'questionnaire_submitted', 'config_applied'
  ));
