"""
Write operations and orchestration for the scholarships module (SPACS).
API views should stay thin and delegate here; legacy web_views remain unchanged.
"""

import datetime
from functools import reduce
from operator import or_

from django.db.models import Q
from jsonschema import validate

from applications.academic_information.models import Student
from notification.views import scholarship_portal_notif

from . import selectors
from .models import (
    Award_and_scholarship,
    Director_gold,
    Director_silver,
    Mcm,
    Notification,
    Proficiency_dm,
    Release,
)
from .validations import (
    MCM_list,
    MCM_schema,
    gold_list,
    gold_schema,
    proficiency_list,
    proficiency_schema,
    silver_list,
    silver_schema,
)


def normalize_programme_from_invite(programme):
    return {
        'BTech': 'B.Tech',
        'MTech': 'M.Tech',
        'MDes': 'M.Des',
        'PhD': 'PhD',
    }.get(programme, programme)


def map_invite_award_to_release(award_ui):
    """Map Fusion-client InviteApplications values to Release.award."""
    mapping = {
        'MCM Scholarship': 'Merit-cum-Means Scholarship',
        "Director's Silver Medal": 'Convocation Medals',
        "Director's Gold Medal": 'Convocation Medals',
        'D&M Proficiency Gold Medal': 'Convocation Medals',
        'Notional Prizes': 'Notional Prizes',
    }
    return mapping.get(award_ui, award_ui)


def check_student_eligibility(student, award_obj):
    """
    BR-SPACS-001: Check student meets award eligibility.
    Returns (is_eligible: bool, reason: str).
    """
    # CPI check
    if award_obj.cpi_cutoff > 0:
        from applications.academic_information.models import Spi
        spis = Spi.objects.filter(student=student).order_by('-semester')
        if not spis.exists():
            return False, "No academic record found. Cannot verify CPI."
        latest_cpi = spis.first().spi if hasattr(spis.first(), 'spi') else 0.0
        if latest_cpi < award_obj.cpi_cutoff:
            return False, f"Your CPI ({latest_cpi:.2f}) is below the required minimum ({award_obj.cpi_cutoff:.2f})."
    
    # Income ceiling check
    if award_obj.income_ceiling > 0:
        # Get latest MCM application to check annual_income
        latest_mcm = Mcm.objects.filter(student=student).order_by('-date').first()
        if latest_mcm and latest_mcm.annual_income > award_obj.income_ceiling:
            return False, f"Your annual family income (₹{latest_mcm.annual_income}) exceeds the maximum limit (₹{award_obj.income_ceiling})."
    
    # Programme check
    if award_obj.eligible_programme != 'all':
        if student.programme != award_obj.eligible_programme:
            return False, f"This award is only open to {award_obj.eligible_programme} students."
    
    return True, "Eligible"


def resolve_award_for_submission(post):
    """
    Resolve Award_and_scholarship from React FormData (award / award_type).
    """
    raw = (post.get('award') or post.get('award_type') or '').strip()
    if not raw:
        raise ValueError('Missing award type')

    key = raw.lower().replace(' ', '')
    if 'merit' in key and 'mean' in key:
        name = 'Merit-cum-Means Scholarship'
    elif "director'sgold" in key or raw == "Director's Gold Medal":
        name = "Director's Gold Medal"
    elif "director'ssilver" in key or raw == "Director's Silver Medal":
        name = "Director's Silver Medal"
    elif 'd&m' in key or 'dmproficiency' in key:
        name = 'D&M Proficiency Gold Medal'
    else:
        name = raw

    try:
        award = Award_and_scholarship.objects.get(award_name=name)
        if not award.publish_flag:
            raise ValueError(f'Award "{award.award_name}" is not currently active.')
        return award
    except Award_and_scholarship.DoesNotExist:
        short_to_id = {
            "Director's Gold": 2,
            "Director's Silver": 3,
            'D&M Proficiency Gold Medal': 5,
            'Merit-cum-means Scholarship': 1,
        }
        aid = short_to_id.get(raw)
        if aid:
            award = Award_and_scholarship.objects.get(pk=aid)
            if not award.publish_flag:
                raise ValueError(f'Award "{award.award_name}" is not currently active.')
            return award
        raise


def application_window_payload(award_raw):
    """Return dict for /check-application-window/ (Fusion client)."""
    text = (award_raw or '').lower()
    if 'merit' in text and 'mean' in text:
        open_ = selectors.get_active_mcm_releases().exists()
        label = 'Merit-cum-Means Scholarship'
    else:
        open_ = selectors.get_active_convocation_releases().exists()
        label = 'Convocation Medals'
    if open_:
        return {
            'result': 'Success',
            'message': f'Applications are open for {label}.',
        }
    return {
        'result': 'Failure',
        'message': (
            f'No active invitation window for {label}. '
            'You can still fill the form; submission may only succeed when the '
            'SPACS office has opened the application period.'
        ),
    }


def create_invite_release(convenor_user, payload):
    """
    JSON body: award, programme, batch, startdate, enddate, remarks.
    Mirrors convener_view 'Submit' release + notifications.
    """
    award_ui = payload.get('award')
    programme = normalize_programme_from_invite(payload.get('programme', ''))
    batch = str(payload.get('batch', ''))
    from_date = payload.get('startdate')
    to_date = payload.get('enddate')
    remarks = payload.get('remarks', '')

    release_award = map_invite_award_to_release(award_ui)
    d_time = datetime.datetime.now()

    rel = Release.objects.create(
        date_time=d_time,
        programme=programme,
        startdate=from_date,
        enddate=to_date,
        award=release_award,
        remarks=remarks,
        batch=batch,
        notif_visible=1,
    )

    if release_award == 'Notional Prizes':
        return rel

    if batch == 'all':
        active_batches = range(
            datetime.datetime.now().year - 4,
            datetime.datetime.now().year + 1,
        )
        query = reduce(or_, (Q(id__id__startswith=str(b)) for b in active_batches))
        recipient = Student.objects.filter(programme=programme).filter(query)
    else:
        recipient = Student.objects.filter(
            programme=programme,
            id__id__startswith=batch,
        )

    for student in recipient:
        scholarship_portal_notif(
            convenor_user, student.id.user, 'award_' + release_award
        )

    if release_award == 'Merit-cum-Means Scholarship':
        Notification.objects.bulk_create(
            [
                Notification(
                    release_id=rel,
                    student_id=s,
                    notification_mcm_flag=True,
                    invite_mcm_accept_flag=False,
                )
                for s in recipient
            ]
        )
    elif release_award == 'Convocation Medals':
        Notification.objects.bulk_create(
            [
                Notification(
                    release_id=rel,
                    student_id=s,
                    notification_convocation_flag=True,
                    invite_convocation_accept_flag=False,
                )
                for s in recipient
            ]
        )

    return rel


def update_award_catalog(award_pk, catalog_text, publish=None, **kwargs):
    award = Award_and_scholarship.objects.get(pk=award_pk)
    award.catalog = catalog_text
    award.version = award.version + 1
    update_fields = ['catalog', 'version']

    if publish is not None:
        award.publish_flag = publish
        update_fields.append('publish_flag')

    if 'award_name' in kwargs and kwargs['award_name']:
        award.award_name = kwargs['award_name']
        update_fields.append('award_name')
        
    if 'cpi_cutoff' in kwargs and kwargs['cpi_cutoff'] is not None:
        award.cpi_cutoff = kwargs['cpi_cutoff']
        update_fields.append('cpi_cutoff')
        
    if 'income_ceiling' in kwargs and kwargs['income_ceiling'] is not None:
        award.income_ceiling = kwargs['income_ceiling']
        update_fields.append('income_ceiling')
        
    if 'eligible_programme' in kwargs and kwargs['eligible_programme']:
        award.eligible_programme = kwargs['eligible_programme']
        update_fields.append('eligible_programme')

    award.save(update_fields=update_fields)
    return award


def map_mcm_status_from_client(status):
    s = (status or '').upper()
    if s == 'ACCEPTED':
        return 'Accept'
    if s == 'REJECTED':
        return 'Reject'
    if s == 'UNDER_REVIEW' or s == 'INCOMPLETE':
        return 'Incomplete'
    if s == 'FORWARDED':
        return 'Forwarded'
    return status


def map_medal_status_from_client(status):
    s = (status or '').upper()
    if s == 'ACCEPTED':
        return 'Accept'
    if s == 'REJECTED':
        return 'Reject'
    if s == 'FORWARDED':
        return 'Forwarded'
    if s == 'INCOMPLETE':
        return 'Incomplete'
    return status


def _mcm_file_urls(mcm, request):
    def u(f):
        if not f or not getattr(f, 'name', None):
            return None
        try:
            return request.build_absolute_uri(f.url)
        except Exception:
            return f.url

    return {
        'income_certificate': u(mcm.income_certificate),
        'Marksheet': u(getattr(mcm, 'marksheet', None)),
        'Fee_Receipt': u(getattr(mcm, 'fee_receipt', None)),
        'Bank_details': u(getattr(mcm, 'bank_details', None)),
        'Affidavit': u(getattr(mcm, 'affidavit', None)),
        'Aadhar_card': u(getattr(mcm, 'aadhar_card', None)),
    }


def _serialize_mcm(m, request):
    from .models import Withdrawal
    stud = m.student
    user = stud.id.user
    is_pending = Withdrawal.objects.filter(application_id=m.id, scholarship_type='mcm', acknowledged=False).exists()
    return {
        'id': m.id,
        'student': user.get_full_name() or user.username,
        'student_id': user.username,
        'status': m.status,
        'date': m.date.isoformat() if m.date else None,
        'annual_income': m.annual_income,
        'category': m.category or getattr(stud, 'category', None),
        'cpi': m.cpi or getattr(stud, 'cpi', None),
        'academic_year': m.academic_year,
        'semester': m.semester,
        'remarks': m.remarks,
        'programme': getattr(stud, 'programme', None),
        'department': getattr(stud.id.department, 'name', None),
        'income_father': m.income_father,
        'income_mother': m.income_mother,
        'income_other': m.income_other,
        'father_occ': m.father_occ,
        'mother_occ': m.mother_occ,
        'father_occ_desc': m.father_occ_desc,
        'mother_occ_desc': m.mother_occ_desc,
        'four_wheeler': m.four_wheeler,
        'four_wheeler_desc': m.four_wheeler_desc,
        'two_wheeler': m.two_wheeler,
        'two_wheeler_desc': m.two_wheeler_desc,
        'house': m.house,
        'plot_area': m.plot_area,
        'constructed_area': m.constructed_area,
        'school_fee': m.school_fee,
        'school_name': m.school_name,
        'bank_name': m.bank_name,
        'loan_amount': m.loan_amount,
        'college_fee': m.college_fee,
        'college_name': m.college_name,
        'brother_name': m.brother_name,
        'brother_occupation': m.brother_occupation,
        'sister_name': m.sister_name,
        'sister_occupation': m.sister_occupation,
        'withdrawal_pending': is_pending,
        **_mcm_file_urls(m, request),
    }


def mcm_applications_list_for_convenor(request):
    """Convenor sees only FORWARDED MCM applications."""
    return [_serialize_mcm(m, request) for m in selectors.get_all_mcm().filter(status='Forwarded')]


def mcm_applications_list_for_assistant(request):
    """Assistant sees all MCM applications (Pending, Incomplete, etc.)."""
    return [_serialize_mcm(m, request) for m in selectors.get_all_mcm()]


def add_application_note(scholarship_type, application_id, note_text, author_info):
    from .models import ApplicationNote
    return ApplicationNote.objects.create(
        scholarship_type=scholarship_type,
        application_id=application_id,
        note=note_text,
        author=author_info
    )


def get_application_notes(scholarship_type, application_id):
    from .models import ApplicationNote
    notes = ApplicationNote.objects.filter(
        scholarship_type=scholarship_type,
        application_id=application_id
    ).order_by('-created_at')
    return [
        {
            'id': n.id,
            'note': n.note,
            'created_at': n.created_at.strftime('%Y-%m-%d %H:%M'),
            'author_name': n.author.user.get_full_name() or n.author.user.username,
            'is_read': n.is_read
        }
        for n in notes
    ]


def _medal_row(obj, request):
    from .models import Withdrawal, Director_gold, Director_silver, Proficiency_dm
    
    stype = 'dm'
    if isinstance(obj, Director_gold): stype = 'gold'
    elif isinstance(obj, Director_silver): stype = 'silver'
    
    is_pending = Withdrawal.objects.filter(application_id=obj.id, scholarship_type=stype, acknowledged=False).exists()
    
    data = {
        'id': obj.id,
        'student': obj.student.id.user.get_full_name() or str(obj.student),
        'student_id': obj.student.id.user.username,
        'category': getattr(obj.student, 'category', None),
        'cpi': getattr(obj.student, 'cpi', None),
        'programme': getattr(obj.student, 'programme', None),
        'department': getattr(obj.student.id.department, 'name', None),
        'status': obj.status,
        'date': obj.date.isoformat() if obj.date else None,
        'relevant_document': (
            request.build_absolute_uri(obj.relevant_document.url)
            if obj.relevant_document
            else None
        ),
        # Common medal fields
        'correspondence_address': getattr(obj, 'correspondence_address', None),
        'financial_assistance': getattr(obj, 'financial_assistance', None),
        'grand_total': getattr(obj, 'grand_total', None),
        'nearest_policestation': getattr(obj, 'nearest_policestation', None),
        'nearest_railwaystation': getattr(obj, 'nearest_railwaystation', None),
        'justification': getattr(obj, 'justification', None),
    }
    
    # Model-specific fields
    if isinstance(obj, Director_gold):
        data.update({
            'academic_achievements': obj.academic_achievements,
            'science_inside': obj.science_inside,
            'science_outside': obj.science_outside,
            'games_inside': obj.games_inside,
            'games_outside': obj.games_outside,
            'cultural_inside': obj.cultural_inside,
            'cultural_outside': obj.cultural_outside,
            'social': obj.social,
            'corporate': obj.corporate,
            'hall_activities': obj.hall_activities,
            'gymkhana_activities': obj.gymkhana_activities,
            'institute_activities': obj.institute_activities,
            'counselling_activities': obj.counselling_activities,
            'other_activities': obj.other_activities,
        })
    elif isinstance(obj, Director_silver):
        data.update({
            'inside_achievements': obj.inside_achievements,
            'outside_achievements': obj.outside_achievements,
        })
    elif isinstance(obj, Proficiency_dm):
        data.update({
            'title_name': obj.title_name,
            'no_of_students': obj.no_of_students,
            'brief_description': obj.brief_description,
            'topic_ece': obj.ece_topic,
            'topic_cse': obj.cse_topic,
            'topic_mech': obj.mech_topic,
            'topic_design': obj.design_topic,
        })
    
    data['withdrawal_pending'] = is_pending
    return data


def director_gold_list(request):
    return [_medal_row(x, request) for x in selectors.get_all_gold()]


def director_silver_list(request):
    return [_medal_row(x, request) for x in selectors.get_all_silver()]


def proficiency_dm_list(request):
    return [_medal_row(x, request) for x in selectors.get_all_proficiency()]


def student_status_rows(queryset, request=None):
    rows = []
    for x in queryset:
        if isinstance(x, Mcm):
            rows.append(_serialize_mcm(x, request))
        elif isinstance(x, (Director_gold, Director_silver, Proficiency_dm)):
            rows.append(_medal_row(x, request))
        else:
            rows.append({
                'id': x.id,
                'status': x.status,
                'student': x.student.id.user.get_full_name() or str(x.student),
                'date': x.date.isoformat() if x.date else None,
            })
    return rows


def previous_winners_payload(programme, year, award_id):
    qs = selectors.get_previous_winners_by_award_id(programme, year, award_id)
    if not qs.exists():
        return {
            'result': 'Success',
            'student_name': [],
            'roll': [],
            'student_program': [],
        }
    names, rolls, programs = [], [], []
    for w in qs:
        extra = w.student.id
        names.append(extra.user.first_name)
        rolls.append(str(w.student_id))
        programs.append(w.student.programme)
    return {
        'result': 'Success',
        'student_name': names,
        'roll': rolls,
        'student_program': programs,
    }


def submit_mcm_api(request):
    """Multipart MCM submit (React); mirrors submitMCM field names."""
    user = request.user
    post = request.POST
    files = request.FILES

    for n in Notification.objects.select_related('student_id', 'release_id').filter(
        student_id=user.extrainfo.id
    ):
        n.invite_mcm_accept_flag = False
        n.save(update_fields=['invite_mcm_accept_flag'])

    award_obj = resolve_award_for_submission(post)
    student = user.extrainfo.student

    # T1: BR-SPACS-001 - Eligibility validation
    is_eligible, reason = check_student_eligibility(student, award_obj)
    if not is_eligible:
        raise ValueError(f"Eligibility check failed: {reason}")

    father_occ = post.get('father_occ')
    mother_occ = post.get('mother_occ')
    brother_name = post.get('brother_name')
    sister_name = post.get('sister_name')
    brother_occupation = post.get('brother_occupation')
    sister_occupation = post.get('sister_occupation')
    income_father = int(post.get('father_income') or post.get('income_father') or 0)
    income_mother = int(post.get('mother_income') or post.get('income_mother') or 0)
    income_other = int(post.get('other_income') or post.get('income_other') or 0)
    father_occ_desc = post.get('father_occ_desc')
    mother_occ_desc = post.get('mother_occ_desc')
    four_wheeler = post.get('four_wheeler')
    four_wheeler_desc = post.get('four_wheeler_desc')
    two_wheeler_desc = post.get('two_wheeler_desc')
    two_wheeler = post.get('two_wheeler')
    house = post.get('house')
    plot_area = post.get('plot_area')
    constructed_area = post.get('constructed_area')
    school_fee = post.get('school_fee')
    school_name = post.get('school_name')
    college_fee = post.get('college_fee')
    college_name = post.get('college_name')
    loan_amount = post.get('loan_amount')
    bank_name = post.get('bank_name')
    income_certificate = files.get('income_certificate')
    marksheet = files.get('Marksheet')
    fee_receipt = files.get('Fee_Receipt')
    bank_details = files.get('Bank_details')
    affidavit = files.get('Affidavit')
    aadhar_card = files.get('Aadhar_card')
    
    # New fields
    academic_year = post.get('academic_year')
    semester = post.get('semester')
    remarks = post.get('remarks')
    category = post.get('category')
    cpi = post.get('cpi')

    def _opt_num(v, default=None):
        if v is None or v == '':
            return default
        try:
            return float(v) if '.' in str(v) else int(v)
        except (TypeError, ValueError):
            return default

    # Re-extract with robust defaults
    income_father = _opt_num(post.get('father_income') or post.get('income_father'), 0)
    income_mother = _opt_num(post.get('mother_income') or post.get('income_mother'), 0)
    income_other = _opt_num(post.get('other_income') or post.get('income_other'), 0)
    
    annual_income = income_father + income_mother + income_other

    application_id = post.get('application_id')

    data_insert = {
        'brother_name': brother_name,
        'brother_occupation': brother_occupation,
        'sister_name': sister_name,
        'sister_occupation': sister_occupation,
        'income_father': income_father,
        'income_mother': income_mother,
        'income_other': income_other,
        'father_occ': father_occ,
        'mother_occ': mother_occ,
        'father_occ_desc': father_occ_desc,
        'mother_occ_desc': mother_occ_desc,
        'four_wheeler': _opt_num(four_wheeler),
        'four_wheeler_desc': four_wheeler_desc,
        'two_wheeler': _opt_num(two_wheeler),
        'two_wheeler_desc': two_wheeler_desc,
        'house': house,
        'plot_area': _opt_num(plot_area),
        'constructed_area': _opt_num(constructed_area),
        'school_fee': _opt_num(school_fee),
        'school_name': school_name,
        'bank_name': bank_name,
        'loan_amount': _opt_num(loan_amount),
        'college_fee': _opt_num(college_fee),
        'college_name': college_name,
        'annual_income': annual_income,
    }

    for column in MCM_list:
        validate(instance=data_insert[column], schema=MCM_schema[column])

    today = datetime.datetime.today().strftime('%Y-%m-%d')
    releases = Release.objects.filter(
        Q(startdate__lte=today, enddate__gte=today),
        award='Merit-cum-Means Scholarship',
    )

    common = dict(
        father_occ=father_occ,
        mother_occ=mother_occ,
        brother_name=brother_name,
        sister_name=sister_name,
        income_father=income_father,
        income_mother=income_mother,
        income_other=income_other,
        brother_occupation=brother_occupation,
        sister_occupation=sister_occupation,
        student=student,
        annual_income=annual_income,
        income_certificate=income_certificate,
        award_id=award_obj,
        father_occ_desc=father_occ_desc,
        mother_occ_desc=mother_occ_desc,
        four_wheeler=data_insert['four_wheeler'],
        four_wheeler_desc=four_wheeler_desc,
        two_wheeler_desc=two_wheeler_desc,
        two_wheeler=data_insert['two_wheeler'],
        house=house,
        plot_area=data_insert['plot_area'],
        constructed_area=data_insert['constructed_area'],
        school_fee=data_insert['school_fee'],
        school_name=school_name,
        bank_name=bank_name,
        loan_amount=data_insert['loan_amount'],
        college_fee=data_insert['college_fee'],
        college_name=college_name,
        marksheet=marksheet,
        fee_receipt=fee_receipt,
        bank_details=bank_details,
        affidavit=affidavit,
        aadhar_card=aadhar_card,
        academic_year=academic_year,
        semester=_opt_num(semester),
        remarks=remarks,
        category=category,
        cpi=_opt_num(cpi),
    )

    file_keys = (
        'income_certificate',
        'marksheet',
        'fee_receipt',
        'bank_details',
        'affidavit',
        'aadhar_card',
    )

    # T12: Explicit application_id update
    if application_id:
        try:
            existing_app = Mcm.objects.get(pk=application_id, student=student)
            # BR-SPACS-002: Safety check
            if existing_app.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                 raise ValueError(f"Application #{application_id} (status: {existing_app.status}) cannot be modified.")
            
            upd = {k: v for k, v in common.items() if k != 'student'}
            for fk in file_keys:
                if upd.get(fk) is None:
                    upd.pop(fk, None)
            Mcm.objects.filter(pk=application_id).update(status='Submitted', **upd)
            return {'detail': 'Updated successfully'}
        except Mcm.DoesNotExist:
            pass # Fallback to release-based logic if ID is invalid

    for release in releases:
        existing = Mcm.objects.select_related('award_id', 'student').filter(
            Q(date__gte=release.startdate, date__lte=release.enddate),
            student=student,
        )
        if existing.exists():
            existing_obj = existing.first()
            # T2: BR-SPACS-002 - Prevent re-submission of verified applications
            if existing_obj.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                raise ValueError(
                    f"Your application (status: {existing_obj.status}) cannot be modified. "
                    "It has already been reviewed. Contact SPACS office if you need to make changes."
                )
            # Only update if still INCOMPLETE
            upd = {k: v for k, v in common.items() if k != 'student'}
            for fk in file_keys:
                if upd.get(fk) is None:
                    upd.pop(fk, None)
            existing.update(status='Submitted', **upd)
        else:
            Mcm.objects.create(status='Submitted', **common)
        break
    else:
        # If no active release but we are here, create anyway (legacy fallback)
        Mcm.objects.create(status='Submitted', **common)

    return {'detail': 'Submitted'}


def submit_director_gold_api(request):
    user = request.user
    files = request.FILES

    for n in Notification.objects.select_related('student_id', 'release_id').filter(
        student_id=user.extrainfo.id
    ):
        n.invite_convocation_accept_flag = False
        n.save(update_fields=['invite_convocation_accept_flag'])

    relevant_document = files.get('Marksheet') or files.get('myfile')
    award_obj = resolve_award_for_submission(request.POST)
    student_id = user.extrainfo.student

    # T1: BR-SPACS-001 - Eligibility validation
    is_eligible, reason = check_student_eligibility(student_id, award_obj)
    if not is_eligible:
        raise ValueError(f"Eligibility check failed: {reason}")

    academic_achievements = request.POST.get('academic_achievements')
    science_inside = request.POST.get('science_inside')
    science_outside = request.POST.get('science_outside')
    games_inside = request.POST.get('games_inside')
    games_outside = request.POST.get('games_outside')
    cultural_inside = request.POST.get('cultural_inside')
    cultural_outside = request.POST.get('cultural_outside')
    social = request.POST.get('social')
    corporate = request.POST.get('corporate')
    hall_activities = request.POST.get('hall_activities')
    gymkhana_activities = request.POST.get('gymkhana_activities')
    institute_activities = request.POST.get('institute_activities')
    counselling_activities = request.POST.get('counselling_activities')
    other_activities = request.POST.get('other_activities')
    justification = request.POST.get('justification')
    correspondence_address = request.POST.get('correspondence_address')
    financial_assistance = request.POST.get('financial_assistance')
    grand_total = request.POST.get('grand_total')
    nearest_policestation = request.POST.get('nearest_policestation')
    nearest_railwaystation = request.POST.get('nearest_railwaystation')

    try:
        gt_val = int(grand_total) if str(grand_total).strip() else None
    except (TypeError, ValueError):
        gt_val = None

    data_insert = {
        'academic_achievements': academic_achievements,
        'science_inside': science_inside,
        'science_outside': science_outside,
        'games_inside': games_inside,
        'games_outside': games_outside,
        'cultural_inside': cultural_inside,
        'cultural_outside': cultural_outside,
        'social': social,
        'corporate': corporate,
        'hall_activities': hall_activities,
        'gymkhana_activities': gymkhana_activities,
        'institute_activities': institute_activities,
        'counselling_activities': counselling_activities,
        'other_activities': other_activities,
        'justification': justification,
        'correspondence_address': correspondence_address,
        'financial_assistance': financial_assistance,
        'grand_total': gt_val,
        'nearest_policestation': nearest_policestation,
        'nearest_railwaystation': nearest_railwaystation,
    }
    for column in gold_list:
        validate(instance=data_insert[column], schema=gold_schema[column])

    today = datetime.datetime.today().strftime('%Y-%m-%d')
    releases = Release.objects.filter(
        Q(startdate__lte=today, enddate__gte=today),
        award='Convocation Medals',
    )

    gt = gt_val

    application_id = request.POST.get('application_id')
    if application_id:
        try:
            existing_app = Director_gold.objects.get(pk=application_id, student=student_id)
            if existing_app.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                 raise ValueError(f"Application #{application_id} (status: {existing_app.status}) cannot be modified.")
            
            upd_fields = dict(
                student=student_id,
                relevant_document=relevant_document,
                award_id=award_obj,
                academic_achievements=academic_achievements,
                science_inside=science_inside,
                science_outside=science_outside,
                games_inside=games_inside,
                games_outside=games_outside,
                cultural_inside=cultural_inside,
                cultural_outside=cultural_outside,
                social=social,
                corporate=corporate,
                hall_activities=hall_activities,
                gymkhana_activities=gymkhana_activities,
                institute_activities=institute_activities,
                counselling_activities=counselling_activities,
                other_activities=other_activities,
                correspondence_address=correspondence_address,
                financial_assistance=financial_assistance,
                grand_total=gt,
                nearest_policestation=nearest_policestation,
                nearest_railwaystation=nearest_railwaystation,
                justification=justification,
                status='Submitted',
            )
            if upd_fields.get('relevant_document') is None:
                upd_fields.pop('relevant_document', None)
            Director_gold.objects.filter(pk=application_id).update(**upd_fields)
            return {'detail': 'Updated successfully'}
        except Director_gold.DoesNotExist:
            pass

    for release in releases:
        existing = Director_gold.objects.select_related('student', 'award_id').filter(
            Q(date__gte=release.startdate, date__lte=release.enddate),
            student=student_id,
        )
        fields = dict(
            student=student_id,
            relevant_document=relevant_document,
            award_id=award_obj,
            academic_achievements=academic_achievements,
            science_inside=science_inside,
            science_outside=science_outside,
            games_inside=games_inside,
            games_outside=games_outside,
            cultural_inside=cultural_inside,
            cultural_outside=cultural_outside,
            social=social,
            corporate=corporate,
            hall_activities=hall_activities,
            gymkhana_activities=gymkhana_activities,
            institute_activities=institute_activities,
            counselling_activities=counselling_activities,
            other_activities=other_activities,
            correspondence_address=correspondence_address,
            financial_assistance=financial_assistance,
            grand_total=gt,
            nearest_policestation=nearest_policestation,
            nearest_railwaystation=nearest_railwaystation,
            justification=justification,
            status='Submitted',
        )
        if existing.exists():
            existing_obj = existing.first()
            # T2: BR-SPACS-002 - Prevent re-submission of verified applications
            if existing_obj.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                raise ValueError(
                    f"Your application (status: {existing_obj.status}) cannot be modified. "
                    "It has already been reviewed. Contact SPACS office if you need to make changes."
                )
            upd = dict(fields)
            if upd.get('relevant_document') is None:
                upd.pop('relevant_document', None)
            existing.update(**upd)
        else:
            Director_gold.objects.create(**fields)
        break
    else:
        Director_gold.objects.create(
            student=student_id,
            relevant_document=relevant_document,
            award_id=award_obj,
            academic_achievements=academic_achievements,
            science_inside=science_inside,
            science_outside=science_outside,
            games_inside=games_inside,
            games_outside=games_outside,
            cultural_inside=cultural_inside,
            cultural_outside=cultural_outside,
            social=social,
            corporate=corporate,
            hall_activities=hall_activities,
            gymkhana_activities=gymkhana_activities,
            institute_activities=institute_activities,
            counselling_activities=counselling_activities,
            other_activities=other_activities,
            correspondence_address=correspondence_address,
            financial_assistance=financial_assistance,
            grand_total=gt,
            nearest_policestation=nearest_policestation,
            nearest_railwaystation=nearest_railwaystation,
            justification=justification,
            status='Submitted',
        )

    return {'detail': 'Submitted'}


def submit_director_silver_api(request):
    user = request.user
    files = request.FILES
    post = request.POST

    for n in Notification.objects.select_related('student_id', 'release_id').filter(
        student_id=user.extrainfo.id
    ):
        n.invite_convocation_accept_flag = False
        n.save(update_fields=['invite_convocation_accept_flag'])

    relevant_document = files.get('Marksheet') or files.get('myfile')
    award_obj = resolve_award_for_submission(post)
    award_type = post.get('award-type') or post.get('award_type')
    student_id = user.extrainfo.student

    # T1: BR-SPACS-001 - Eligibility validation
    is_eligible, reason = check_student_eligibility(student_id, award_obj)
    if not is_eligible:
        raise ValueError(f"Eligibility check failed: {reason}")

    inside_achievements = post.get('inside_achievements')
    outside_achievements = post.get('outside_achievements')
    justification = post.get('justification')
    correspondence_address = post.get('correspondence_address') or post.get('c_address')
    financial_assistance = post.get('financial_assistance')
    grand_total = post.get('grand_total')
    nearest_policestation = post.get('nearest_policestation') or post.get('nps')
    nearest_railwaystation = post.get('nearest_railwaystation') or post.get('nrs')

    try:
        gt_silver = int(grand_total) if str(grand_total).strip() else None
    except (TypeError, ValueError):
        gt_silver = None

    data_insert = {
        'nearest_policestation': nearest_policestation,
        'nearest_railwaystation': nearest_railwaystation,
        'correspondence_address': correspondence_address,
        'financial_assistance': financial_assistance,
        'grand_total': gt_silver,
        'inside_achievements': inside_achievements,
        'justification': justification,
        'outside_achievements': outside_achievements,
    }
    for column in silver_list:
        validate(instance=data_insert[column], schema=silver_schema[column])

    today = datetime.datetime.today().strftime('%Y-%m-%d')
    releases = Release.objects.filter(
        Q(startdate__lte=today, enddate__gte=today),
        award='Convocation Medals',
    )

    gt = gt_silver

    application_id = request.POST.get('application_id')
    if application_id:
        try:
            existing_app = Director_silver.objects.get(pk=application_id, student=student_id)
            if existing_app.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                 raise ValueError(f"Application #{application_id} (status: {existing_app.status}) cannot be modified.")
            
            upd_fields = dict(
                student=student_id,
                award_id=award_obj,
                award_type=award_type,
                relevant_document=relevant_document,
                inside_achievements=inside_achievements,
                justification=justification,
                correspondence_address=correspondence_address,
                financial_assistance=financial_assistance,
                grand_total=gt,
                nearest_policestation=nearest_policestation,
                nearest_railwaystation=nearest_railwaystation,
                outside_achievements=outside_achievements,
                status='Submitted',
            )
            if upd_fields.get('relevant_document') is None:
                upd_fields.pop('relevant_document', None)
            Director_silver.objects.filter(pk=application_id).update(**upd_fields)
            return {'detail': 'Updated successfully'}
        except Director_silver.DoesNotExist:
            pass

    for release in releases:
        existing = Director_silver.objects.select_related('student', 'award_id').filter(
            Q(date__gte=release.startdate, date__lte=release.enddate),
            student=student_id,
        )
        fields = dict(
            student=student_id,
            award_id=award_obj,
            award_type=award_type,
            relevant_document=relevant_document,
            inside_achievements=inside_achievements,
            justification=justification,
            correspondence_address=correspondence_address,
            financial_assistance=financial_assistance,
            grand_total=gt,
            nearest_policestation=nearest_policestation,
            nearest_railwaystation=nearest_railwaystation,
            outside_achievements=outside_achievements,
            status='Submitted',
        )
        if existing.exists():
            existing_obj = existing.first()
            # T2: BR-SPACS-002 - Prevent re-submission of verified applications
            if existing_obj.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                raise ValueError(
                    f"Your application (status: {existing_obj.status}) cannot be modified. "
                    "It has already been reviewed. Contact SPACS office if you need to make changes."
                )
            upd = dict(fields)
            if upd.get('relevant_document') is None:
                upd.pop('relevant_document', None)
            existing.update(**upd)
        else:
            Director_silver.objects.create(**fields)
        break
    else:
        Director_silver.objects.create(
            student=student_id,
            award_id=award_obj,
            award_type=award_type,
            relevant_document=relevant_document,
            inside_achievements=inside_achievements,
            justification=justification,
            correspondence_address=correspondence_address,
            financial_assistance=financial_assistance,
            grand_total=gt,
            nearest_policestation=nearest_policestation,
            nearest_railwaystation=nearest_railwaystation,
            outside_achievements=outside_achievements,
            status='Submitted',
        )

    return {'detail': 'Submitted'}


def _safe_int(val, default=0):
    try:
        if val is None or val == '':
            return default
        return int(val)
    except (TypeError, ValueError):
        return default


def submit_proficiency_dm_api(request):
    user = request.user
    post = request.POST
    files = request.FILES

    for n in Notification.objects.select_related('student_id', 'release_id').filter(
        student_id=user.extrainfo.id
    ):
        n.invite_convocation_accept_flag = False
        n.save(update_fields=['invite_convocation_accept_flag'])

    title_name = post.get('title') or post.get('title_name')
    no_of_students = _safe_int(post.get('students') or post.get('no_of_students'), 1)
    relevant_document = files.get('Marksheet') or files.get('myfile')
    award_obj = resolve_award_for_submission(post)
    award_type = post.get('award-type') or post.get('award_type')
    student_id = user.extrainfo.student

    # T1: BR-SPACS-001 - Eligibility validation
    is_eligible, reason = check_student_eligibility(student_id, award_obj)
    if not is_eligible:
        raise ValueError(f"Eligibility check failed: {reason}")

    roll_no1 = _safe_int(post.get('roll_no1'))
    roll_no2 = _safe_int(post.get('roll_no2'))
    roll_no3 = _safe_int(post.get('roll_no3'))
    roll_no4 = _safe_int(post.get('roll_no4'))
    roll_no5 = _safe_int(post.get('roll_no5'))
    ece_topic = post.get('ece_topic')
    cse_topic = post.get('cse_topic')
    mech_topic = post.get('mech_topic')
    design_topic = post.get('design_topic')
    ece_percentage = _safe_int(post.get('ece_percentage'))
    cse_percentage = _safe_int(post.get('cse_percentage'))
    mech_percentage = _safe_int(post.get('mech_percentage'))
    design_percentage = _safe_int(post.get('design_percentage'))
    brief_description = post.get('brief_description')
    justification = post.get('justification')
    correspondence_address = post.get('correspondence_address') or post.get('c_address')
    financial_assistance = post.get('financial_assistance')
    nearest_policestation = post.get('nearest_policestation') or post.get('nps')
    nearest_railwaystation = post.get('nearest_railwaystation') or post.get('nrs')

    gt_dm = _safe_int(post.get('grand_total'))

    data_insert = {
        'title_name': title_name,
        'award_type': award_type,
        'nearest_policestation': nearest_policestation,
        'nearest_railwaystation': nearest_railwaystation,
        'correspondence_address': correspondence_address,
        'financial_assistance': financial_assistance,
        'brief_description': brief_description,
        'justification': justification,
        'grand_total': gt_dm,
        'ece_topic': ece_topic,
        'cse_topic': cse_topic,
        'mech_topic': mech_topic,
        'design_topic': design_topic,
        'ece_percentage': ece_percentage,
        'cse_percentage': cse_percentage,
        'mech_percentage': mech_percentage,
        'design_percentage': design_percentage,
    }
    for column in proficiency_list:
        validate(instance=data_insert[column], schema=proficiency_schema[column])

    today = datetime.datetime.today().strftime('%Y-%m-%d')
    releases = Release.objects.filter(
        Q(startdate__lte=today, enddate__gte=today),
        award='Convocation Medals',
    )

    base = dict(
        title_name=title_name,
        no_of_students=no_of_students,
        student=student_id,
        award_id=award_obj,
        award_type=award_type,
        relevant_document=relevant_document,
        roll_no1=roll_no1,
        roll_no2=roll_no2,
        roll_no3=roll_no3,
        roll_no4=roll_no4,
        roll_no5=roll_no5,
        ece_topic=ece_topic,
        cse_topic=cse_topic,
        mech_topic=mech_topic,
        design_topic=design_topic,
        ece_percentage=ece_percentage,
        cse_percentage=cse_percentage,
        mech_percentage=mech_percentage,
        design_percentage=design_percentage,
        brief_description=brief_description,
        correspondence_address=correspondence_address,
        financial_assistance=financial_assistance,
        grand_total=gt_dm,
        nearest_policestation=nearest_policestation,
        nearest_railwaystation=nearest_railwaystation,
        justification=justification,
        status='Submitted',
    )

    application_id = request.POST.get('application_id')
    if application_id:
        try:
            existing_app = Proficiency_dm.objects.get(pk=application_id, student=student_id)
            if existing_app.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                 raise ValueError(f"Application #{application_id} (status: {existing_app.status}) cannot be modified.")
            
            upd = dict(base)
            if upd.get('relevant_document') is None:
                upd.pop('relevant_document', None)
            Proficiency_dm.objects.filter(pk=application_id).update(**upd)
            return {'detail': 'Updated successfully'}
        except Proficiency_dm.DoesNotExist:
            pass

    for release in releases:
        existing = Proficiency_dm.objects.select_related('student', 'award_id').filter(
            Q(date__gte=release.startdate, date__lte=release.enddate),
            student=student_id,
        )
        if existing.exists():
            existing_obj = existing.first()
            # T2: BR-SPACS-002 - Prevent re-submission of verified applications
            if existing_obj.status in ('Submitted', 'Forwarded', 'Accept', 'Reject'):
                raise ValueError(
                    f"Your application (status: {existing_obj.status}) cannot be modified. "
                    "It has already been reviewed. Contact SPACS office if you need to make changes."
                )
            upd = dict(base)
            if upd.get('relevant_document') is None:
                upd.pop('relevant_document', None)
            existing.update(**upd)
        else:
            Proficiency_dm.objects.create(**base)
        break
    else:
        Proficiency_dm.objects.create(**base)

    return {'detail': 'Submitted'}
