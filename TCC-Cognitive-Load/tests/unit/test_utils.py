"""Unit: app.utils (helpers puros de UI, offline)."""

import pytest

from app import utils

pytestmark = pytest.mark.unit


def test_normalize_username():
    assert utils._normalize_username("  Augusto ") == "augusto"
    assert utils._normalize_username(None) == ""


def test_legacy_owner_sentinel():
    assert utils._legacy_owner_sentinel("  Prof ") == "legacy-owner::prof"
    assert utils._legacy_owner_sentinel("") is None


def test_merge_notice():
    assert utils._merge_notice("corpo", "") == "corpo"
    assert utils._merge_notice("", "aviso") == "aviso"
    assert utils._merge_notice("corpo", "aviso") == "aviso\n\ncorpo"


def test_user_role_helpers():
    assert utils._is_admin({"role": "admin"}) is True
    assert utils._is_teacher({"role": "professor"}) is True
    assert utils._is_teacher({"role": "aluno"}) is False
    assert utils._user_role(None) == ""


def test_get_class_by_id():
    rooms = [{"id": "a"}, {"id": "b"}]
    assert utils._get_class_by_id(rooms, "b") == {"id": "b"}
    assert utils._get_class_by_id(rooms, "z") is None
    assert utils._get_class_by_id(None, "a") is None


def test_class_member_labels_basico_e_legacy_owner():
    classroom = {
        "members": {
            "students": ["id2", "id1"],
            "student_labels": {"id1": "Ana", "id2": "Bob"},
        }
    }
    assert utils._class_member_labels(classroom, "students") == ["Ana", "Bob"]

    legacy = {
        "members": {
            "teachers": ["legacy-owner::prof"],
            "teacher_labels": {"legacy-owner::prof": "Prof Antigo"},
        }
    }
    assert utils._class_member_labels(legacy, "teachers") == ["Prof Antigo (responsável)"]


def test_auth_matches_classroom_owner_por_id_e_por_login():
    by_id = {"owner_id": "u-1"}
    assert utils._auth_matches_classroom_owner({"user_id": "u-1"}, by_id) is True
    assert utils._auth_matches_classroom_owner({"user_id": "u-2"}, by_id) is False

    by_login = {"owner_login": "Prof@x.com"}
    assert utils._auth_matches_classroom_owner({"username": "prof@x.com"}, by_login) is True
    assert utils._auth_matches_classroom_owner({"username": "outro"}, by_login) is False


def test_auth_matches_classroom_teacher_por_id_e_por_username():
    classroom = {
        "members": {
            "teachers": ["t-1", "t-2"],
            "teacher_usernames": {"t-1": "Fulano", "t-2": "Beltrano"},
        }
    }
    assert utils._auth_matches_classroom_teacher({"user_id": "t-2"}, classroom) is True
    assert utils._auth_matches_classroom_teacher({"username": "fulano"}, classroom) is True
    assert utils._auth_matches_classroom_teacher({"username": "ninguem"}, classroom) is False
