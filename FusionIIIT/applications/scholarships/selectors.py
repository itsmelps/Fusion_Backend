"""
selectors.py — Read-only database query helpers for the scholarships module.

Ref: S1 (4B Refactoring Plan)
Purpose: Centralise read/select queryset operations. Write operations live
         in services.py; legacy template views remain in web_views.py.
"""

import datetime
from functools import reduce
from operator import or_

from django.db.models import Q

from applications.academic_information.models import Spi, Student
from applications.globals.models import Designation, ExtraInfo, HoldsDesignation

from .models import (
    Award_and_scholarship,
    Director_gold,
    Director_silver,
    Mcm,
    Notification,
    Previous_winner,
    Proficiency_dm,
    Release,
)


# ── Award & Release ───────────────────────────────────────────────────────────

def get_award_by_name(award_name):
    return Award_and_scholarship.objects.get(award_name=award_name)


def get_all_awards():
    return Award_and_scholarship.objects.all()


def get_all_releases():
    return Release.objects.all()


def get_active_mcm_releases():
    return Release.objects.filter(
        award='Merit-cum-Means Scholarship'
    )


def get_active_convocation_releases():
    return Release.objects.filter(
        award='Convocation Medals'
    )


# ── Applications ──────────────────────────────────────────────────────────────

def get_all_mcm():
    return Mcm.objects.select_related('award_id', 'student').all()


def get_all_gold():
    return Director_gold.objects.select_related('student', 'award_id').all()


def get_all_silver():
    return Director_silver.objects.select_related('student', 'award_id').all()


def get_all_proficiency():
    return Proficiency_dm.objects.select_related('student', 'award_id').all()


def get_mcm_for_student(student):
    return Mcm.objects.select_related('award_id', 'student').filter(student=student)


def get_gold_for_student(student):
    return Director_gold.objects.select_related('student', 'award_id').filter(student=student)


def get_silver_for_student(student):
    return Director_silver.objects.select_related('student', 'award_id').filter(student=student)


def get_proficiency_for_student(student):
    return Proficiency_dm.objects.select_related('student', 'award_id').filter(student=student)


# ── Notifications ─────────────────────────────────────────────────────────────

def get_notifications_for_student(extrainfo_id):
    return Notification.objects.select_related(
        'student_id', 'release_id'
    ).filter(student_id=extrainfo_id)


def get_notifications_ordered(extrainfo_id):
    return Notification.objects.select_related(
        'student_id', 'release_id'
    ).filter(student_id=extrainfo_id).order_by('-release_id__date_time')


# ── Previous Winners ──────────────────────────────────────────────────────────

def get_previous_winners(award_name, year, programme):
    award = get_award_by_name(award_name)
    return Previous_winner.objects.select_related(
        'student', 'award_id'
    ).filter(year=year, award_id=award, programme=programme)


# ── Students ──────────────────────────────────────────────────────────────────

def get_all_students():
    return Student.objects.all()


def get_all_spi():
    return Spi.objects.all()


def get_recipient_students(programme, batch):
    """Return the Student queryset for a given programme and batch selection."""
    if batch == 'all':
        active_batches = range(
            datetime.datetime.now().year - 4,
            datetime.datetime.now().year + 1
        )
        query = reduce(or_, (Q(id__id__startswith=b) for b in active_batches))
        return Student.objects.filter(programme=programme).filter(query)
    return Student.objects.filter(programme=programme, id__id__startswith=batch)


# ── Designations ─────────────────────────────────────────────────────────────

def get_convenor_designation():
    return Designation.objects.get(name='spacsconvenor')


def get_assistant_designation():
    return Designation.objects.get(name='spacsassistant')


def get_holds_designation(designation):
    return HoldsDesignation.objects.get(designation=designation)


def user_holds_designation_name(user, designation_name):
    return HoldsDesignation.objects.filter(
        user=user,
        designation__name=designation_name,
    ).exists()


def is_spacs_convenor(user):
    return user_holds_designation_name(user, 'spacsconvenor')


def is_spacs_assistant(user):
    return user_holds_designation_name(user, 'spacsassistant')


def get_award_by_id(pk):
    return Award_and_scholarship.objects.get(pk=pk)


def get_previous_winners_by_award_id(programme, year, award_id):
    """
    Match winners by the student's current programme (authoritative) as well as
    the denormalized Previous_winner.programme (legacy rows defaulted to B.Tech).
    """
    return Previous_winner.objects.select_related('student', 'student__id', 'award_id').filter(
        year=year,
        award_id_id=award_id,
    ).filter(
        Q(student__programme=programme) | Q(programme=programme),
    )
