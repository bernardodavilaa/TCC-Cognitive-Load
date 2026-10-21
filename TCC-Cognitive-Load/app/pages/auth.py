"""Authentication helpers and shared navigation views."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Dict, Optional

import gradio as gr

from services.auth_store import _hashPw
from services.supabase_client import (
    SupabaseConfigurationError,
    SupabaseOperationError,
    SupabaseUserExistsError,
    create_user_record,
    fetch_user_record,
    fetch_users_by_role,
    log_access_event,
)

from app.config import (
    ROLE_DB_TO_PT,
    ROLE_PT_TO_DB,
    SUPABASE_ACCESS_LOGS_TABLE,
    SUPABASE_SERVICE_ROLE_KEY,
    SUPABASE_URL,
    SUPABASE_USERS_TABLE,
)


@dataclass
class AuthViews:
    header: gr.Markdown
    aviso: gr.Markdown
    view_login: gr.Column
    view_home: gr.Column
    auth_mode: gr.Radio
    username: gr.Textbox
    password: gr.Textbox
    confirm_password: gr.Textbox
    email: gr.Textbox
    full_name: gr.Textbox
    role_radio: gr.Radio
    register_row: gr.Row
    register_role_row: gr.Row
    btn_login: gr.Button
    btn_register: gr.Button
    login_msg: gr.Markdown
    home_greet: gr.Markdown
    btn_go_customize: gr.Button
    btn_logout_home: gr.Button
    student_row: gr.Row
    btn_student_rooms: gr.Button
    teacher_row: gr.Row
    btn_view_students: gr.Button
    btn_teacher_classrooms: gr.Button
    students_out: gr.Markdown


def build_auth_views(*, blocks: gr.Blocks, vertex_cfg: Dict[str, Any], vertex_err: Optional[str]) -> AuthViews:
    """Create header, login and shared home sections."""
    header_msg = "### 👋 Bem-vindo! Faça login para continuar."
    # Mensagem de boas-vindas / instruções para os participantes da pesquisa.
    # TODO(Bernardo): ainda falta o [LINK_QUESTIONARIO] (formulário externo,
    # redundante com o questionário final já implementado dentro do app).
    aviso_msg = """# Bem-vindo(a) à pesquisa do TCC!

                Este é o tutor de programação com IA personalizada, desenvolvido como parte
                do meu Trabalho de Conclusão de Curso na PUC Minas. Muito obrigado por
                participar!

                **Como entrar:** use o **e-mail institucional PUC** que você preencheu no
                formulário de pré-cadastro como usuário (ex.: `joaosilva@sga.pucminas.br` ou
                `1234567@pucminas.edu.br`) e sua **matrícula** como senha.

                **Ainda não fez o pré-cadastro?** Preencha aqui antes de tentar entrar:
                "https://docs.google.com/forms/d/e/1FAIpQLScU8xUbqZPDLqPbpwhat3zF3ukb7j83MQTVox6m1m8vPyVtiQ/viewform"
                — depois de preencher, me avise pelo contato abaixo que eu libero seu acesso.

                **Ao final de cada sessão**, você será convidado a avaliar sua experiência
                dentro do próprio app. Depois de algumas sessões, um questionário final mais
                completo também abre automaticamente. Também respondemos pelo formulário
                externo, se preferir: "[LINK_QUESTIONARIO]"

                **Prazo para participação:** até 06/11/2026.

                Dúvidas ou problema pra entrar? Fale comigo: **(31) 98689-2209** (WhatsApp) —
                Bernardo D'Ávila

                ---
                **— Bernardo D'Ávila Rodrigues Bartholomeu**
                """
    if vertex_err:
        header_msg += f"\n\n> **Atenção**: {vertex_err}"
    else:
        header_msg += (
            f"\n\n> OK: Credenciais Vertex carregadas de: `{(vertex_cfg or {}).get('source_path', '?')}`"
            f" | Projeto: `{(vertex_cfg or {}).get('project', '?')}` | Região: `{(vertex_cfg or {}).get('location', '?')}`"
            f" | Modelo: `{(vertex_cfg or {}).get('model', '?')}`"
        )
    header = gr.Markdown(header_msg, elem_id="hdr")
    aviso = gr.Markdown(aviso_msg, elem_id="hdr")

    with gr.Column(visible=True) as viewLogin:
        gr.Markdown("## 🔐 Login")
        # Cadastro público desativado: alunos entram só pelo pré-cadastro
        # (Forms -> importação). authMode fica fixo em "Login" e escondido;
        # o fluxo de Registrar continua implementado (doRegister/switch_auth_mode)
        # mas sem UI pra acioná-lo, caso precise reativar no futuro.
        authMode = gr.Radio(["Login"], value="Login", label="Modo de acesso", visible=False)
        loginHint = gr.Markdown(
            "💡 Use o **e-mail institucional PUC** preenchido no formulário de "
            "pré-cadastro como usuário (ex.: `joaosilva@sga.pucminas.br`) e sua "
            "**matrícula** como senha. Não fez o pré-cadastro ainda? Preencha o "
            "formulário acima e depois me avise pelo contato informado — sem "
            "cadastro público direto por aqui."
        )
        with gr.Row():
            username = gr.Textbox(label="Usuário", placeholder="ex: joaosilva@sga.pucminas.br")
            password = gr.Textbox(label="Senha", type="password", placeholder="••••••••")
            confirmPassword = gr.Textbox(
                label="Confirmar senha",
                type="password",
                placeholder="Repita a senha",
                visible=False,
            )
        with gr.Row(visible=False) as registerRow:
            email = gr.Textbox(label="E-mail", placeholder="ex: nome@dominio.com")
            fullName = gr.Textbox(label="Nome completo", placeholder="ex: Maria Silva")
        with gr.Row(visible=False) as registerRoleRow:
            roleRadio = gr.Radio(choices=["Aluno", "Professor", "Admin"], label="Perfil", value="Aluno")
        with gr.Row():
            btnLogin = gr.Button("Entrar", variant="primary", visible=True)
            btnRegister = gr.Button("Registrar", visible=False)
        loginMsg = gr.Markdown("")

    with gr.Column(visible=False) as viewHome:
        homeGreet = gr.Markdown("## 🏠 Home")
        gr.Markdown("Escolha uma opção para continuar:")
        with gr.Row():
            btnLogout1 = gr.Button("Sair")
        with gr.Row(visible=False) as studentRow:
            btnStudentRooms = gr.Button("🎒 Minhas Salas", variant="secondary")
        with gr.Row(visible=False) as profRow:
            btnGoCustomize = gr.Button("⚙️ Personalizar o Chat", variant="primary")
            btnViewStudents = gr.Button("👥 Ver alunos cadastrados", variant="secondary")
            btnTeacherClassrooms = gr.Button("🏫 Minhas Salas", variant="primary")
        studentsOut = gr.Markdown("")

    authMode.change(
        switch_auth_mode,
        inputs=authMode,
        outputs=[registerRow, registerRoleRow, btnLogin, btnRegister, confirmPassword, loginMsg, loginHint],
    )

    return AuthViews(
        header=header,
        aviso=aviso,
        view_login=viewLogin,
        view_home=viewHome,
        auth_mode=authMode,
        username=username,
        password=password,
        confirm_password=confirmPassword,
        email=email,
        full_name=fullName,
        role_radio=roleRadio,
        register_row=registerRow,
        register_role_row=registerRoleRow,
        btn_login=btnLogin,
        btn_register=btnRegister,
        login_msg=loginMsg,
        home_greet=homeGreet,
        btn_go_customize=btnGoCustomize,
        btn_logout_home=btnLogout1,
        student_row=studentRow,
        btn_student_rooms=btnStudentRooms,
        teacher_row=profRow,
        btn_view_students=btnViewStudents,
        btn_teacher_classrooms=btnTeacherClassrooms,
        students_out=studentsOut,
    )


def _route_home(auth):
    is_auth = bool(auth and auth.get("isAuth") is True and auth.get("username"))
    login = (auth or {}).get("username") or ""
    display_name = (auth or {}).get("full_name") or (auth or {}).get("display_name") or login
    role = (auth or {}).get("role", "aluno")
    print(
        f"[NAV] _route_home: isAuth={is_auth} user_login='{login}' display='{display_name}' role='{role}'"
    )
    if not is_auth:
        return (
            gr.update(value="### 👋 Bem-vindo! Faça login para continuar.", visible=True),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
        )
    role = str(role).lower()
    header_txt = f"### 👋 Olá, **{display_name}**! (perfil: {role})"
    if role == "admin":
        return (
            gr.update(value=header_txt, visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(value=f"## 🧭 Home do Admin — bem-vindo, **{display_name}**"),
        )
    elif role == "aluno":
        print("Role Student")
        return (
            gr.update(value=header_txt, visible=True),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(visible=False),
            gr.update(value=""),
        )
    else:
        return (
            gr.update(value=header_txt, visible=True),
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
            gr.update(value=f"## 🏠 Home — bem-vindo, **{display_name}**"),
        )


def _teacherUi(auth):
    role = (auth or {}).get("role", "aluno")
    is_prof = str(role).lower() == "professor"
    return gr.update(visible=is_prof), gr.update(value="")


def _studentUi(auth):
    role = (auth or {}).get("role", "aluno")
    is_student_or_admin = str(role).lower() in ("aluno", "admin")
    return gr.update(visible=is_student_or_admin)


def _back_home(auth):
    role = (auth or {}).get("role", "aluno")
    if str(role).lower() == "admin":
        return (
            gr.update(visible=False),
            gr.update(visible=True),
            gr.update(visible=False),
        )
    return (
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=True),
    )


def switch_auth_mode(mode):
    is_register = str(mode or "").strip().lower() == "registrar"
    return (
        gr.update(visible=is_register),
        gr.update(visible=is_register),
        gr.update(visible=not is_register),
        gr.update(visible=is_register),
        gr.update(visible=is_register, value=""),
        gr.update(value=""),
        gr.update(visible=not is_register),
    )


def doRegister(username, password, confirm_password, email, full_name, role, authState):
    raw_username = (username or "").strip()
    raw_email = (email or "").strip()
    login_email = raw_email.lower()
    name = (full_name or "").strip()
    pw = (password or "").strip()
    confirm_pw = (confirm_password or "").strip()
    print(f"[AUTH] doRegister: username='{raw_username.lower()}' email='{login_email}' role='{role}'")
    if not raw_username or not login_email or not name or not pw or not confirm_pw:
        return gr.update(value="Warning: Informe usuário, e-mail, nome, senha e confirmação."), authState

    if pw != confirm_pw:
        return gr.update(value="Warning: As senhas informadas não coincidem."), authState

    role_pt = (role or "aluno").strip().lower() or "aluno"
    supabase_role = ROLE_PT_TO_DB.get(role_pt, "student")

    display_name = name or raw_username or login_email

    try:
        created = create_user_record(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            SUPABASE_USERS_TABLE,
            login=login_email,
            password_hash=_hashPw(pw),
            role=supabase_role,
            username=raw_username,
            full_name=display_name,
            display_name=display_name,
        )
        print(f"[AUTH] doRegister: Supabase created -> {created}")
    except SupabaseConfigurationError:
        warn = "Warning: Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY antes de registrar usuários."
        print("[AUTH] doRegister: configuração Supabase ausente")
        return gr.update(value=warn), authState
    except SupabaseUserExistsError:
        print(f"[AUTH] doRegister: usuário já existe -> {login_email}")
        return gr.update(value="Warning: Usuário já cadastrado."), authState
    except SupabaseOperationError as err:
        print(f"[AUTH] doRegister: erro Supabase -> {err}")
        return gr.update(value=f"ERROR: Erro ao registrar: {err}"), authState
    except Exception as exc:
        print(f"[AUTH] doRegister: erro inesperado -> {exc}")
        return gr.update(value=f"ERROR: Erro inesperado: {exc}"), authState

    return gr.update(value="OK: Usuário registrado! Faça login com suas credenciais."), authState


def doLogin(username, password, authState):
    uname = (username or "").strip()
    pw = (password or "").strip()
    if not uname or not pw:
        return gr.update(value="Warning: Informe usuário e senha."), authState

    try:
        entry = fetch_user_record(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            SUPABASE_USERS_TABLE,
            uname,
        )
    except SupabaseConfigurationError:
        warn = "Warning: Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY para efetuar login."
        return gr.update(value=warn), authState
    except SupabaseOperationError as err:
        print(f"[AUTH] doLogin: erro Supabase -> {err}")
        return gr.update(value=f"ERROR: Erro ao fazer login: {err}"), authState
    except Exception as exc:
        print(f"[AUTH] doLogin: erro inesperado -> {exc}")
        return gr.update(value=f"ERROR: Erro inesperado: {exc}"), authState

    if not entry:
        print(f"[AUTH] doLogin: usuário não encontrado -> {uname}")
        return gr.update(value="ERROR: Usuário ou senha incorretos."), authState

    expected_hash = entry.password_hash or ""
    if expected_hash != _hashPw(pw):
        print(f"[AUTH] doLogin: senha incorreta -> {uname}")
        return gr.update(value="ERROR: Usuário ou senha incorretos."), authState

    mapped_role = ROLE_DB_TO_PT.get((entry.role or "student").strip().lower(), "aluno")
    stored_username = (entry.username or uname or "").strip() or uname
    full_name = (entry.full_name or "").strip()
    display_name = full_name or entry.username or entry.email or stored_username
    authState = {
        "isAuth": True,
        "username": stored_username,
        "role": mapped_role,
        "user_id": entry.id,
        "full_name": full_name or None,
        "display_name": display_name,
    }
    print(f"[AUTH] doLogin: sucesso -> {authState}")

    # Rastreabilidade de uso: nunca bloqueia o login se o log falhar.
    try:
        log_access_event(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            SUPABASE_ACCESS_LOGS_TABLE,
            user_id=entry.id,
            role=mapped_role,
        )
    except Exception as exc:  # pragma: no cover - não deve bloquear o login
        print(f"[AUTH] Falha ao registrar access_log: {exc}")
    return (
        gr.update(
            value=f"OK: Bem-vindo, **{display_name}** (usuário: {stored_username} · perfil: {mapped_role})."
        ),
        authState,
    )


def _doLogout():
    print("[AUTH] logout")
    return (
        {
            "isAuth": False,
            "username": None,
            "full_name": None,
            "display_name": None,
            "role": None,
            "user_id": None,
        },
        gr.update(value="### 👋 Bem-vindo! Faça login para continuar.", visible=True),
        gr.update(visible=True),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
        gr.update(visible=False),
    )


def listStudents(auth):
    role = (auth or {}).get("role", "aluno")
    if str(role).lower() not in ("professor", "admin"):
        return "Warning: Apenas professores/admin podem visualizar a lista de alunos."
    try:
        records = fetch_users_by_role(
            SUPABASE_URL,
            SUPABASE_SERVICE_ROLE_KEY,
            SUPABASE_USERS_TABLE,
            ROLE_PT_TO_DB.get("aluno", "student"),
        )
    except SupabaseConfigurationError:
        return "Warning: Configure SUPABASE_URL e SUPABASE_SERVICE_ROLE_KEY para visualizar os alunos."
    except SupabaseOperationError as err:
        print(f"[AUTH] listStudents: erro Supabase -> {err}")
        return f"ERROR: Erro ao consultar alunos: {err}"
    except Exception as exc:
        print(f"[AUTH] listStudents: erro inesperado -> {exc}")
        return f"ERROR: Erro inesperado ao consultar alunos: {exc}"

    students = []
    for record in records:
        username = (record.username or "").strip()
        full_name = (record.full_name or "").strip()
        fallback = (record.email or "").strip() or (record.id or "").strip()

        if full_name and username:
            label = f"{full_name} (u: {username})"
        elif full_name:
            label = full_name
        elif username and fallback and fallback.lower() != username.lower():
            label = f"{fallback} (u: {username})"
        else:
            label = username or fallback

        if label:
            students.append(label)

    if not students:
        return "Nenhum aluno cadastrado ainda."
    students.sort(key=lambda x: x.lower())
    bullet = "\n".join([f"- {s}" for s in students])
    return f"### Alunos cadastrados ({len(students)})\n\n{bullet}"


__all__ = [
    "AuthViews",
    "build_auth_views",
    "_route_home",
    "_teacherUi",
    "_studentUi",
    "_back_home",
    "switch_auth_mode",
    "doRegister",
    "doLogin",
    "_doLogout",
    "listStudents",
]
