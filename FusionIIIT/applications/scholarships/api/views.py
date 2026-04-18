import datetime

from jsonschema import ValidationError as JsonSchemaValidationError

from rest_framework import status
from rest_framework.authentication import SessionAuthentication, TokenAuthentication
from rest_framework.decorators import (
    api_view,
    authentication_classes,
    permission_classes,
)
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response

from applications.scholarships import selectors, services
from applications.scholarships.models import (
    Award_and_scholarship,
    Director_gold,
    Director_silver,
    Mcm,
    Proficiency_dm,
)

from .serializers import (
    AwardSerializer,
    CatalogUpdateSerializer,
    GoldDecisionSerializer,
    IdStatusSerializer,
    PreviousWinnersRequestSerializer,
)


def _student(user):
    return getattr(user.extrainfo, 'user_type', None) == 'student'


def _spacs_staff(user):
    return selectors.is_spacs_convenor(user) or selectors.is_spacs_assistant(user)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def check_application_window(request):
    award = (request.data.get('award') if hasattr(request, 'data') else None) or request.POST.get(
        'award'
    )
    return Response(services.application_window_payload(award))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def mcm_update(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    try:
        return Response(services.submit_mcm_api(request), status=status.HTTP_200_OK)
    except JsonSchemaValidationError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Award_and_scholarship.DoesNotExist:
        return Response({'detail': 'Unknown award'}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Exception as exc:
        import traceback
        print(traceback.format_exc())
        return Response({'detail': f"Internal Server Error: {str(exc)}"}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def directorgold_update(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    try:
        return Response(services.submit_director_gold_api(request), status=status.HTTP_200_OK)
    except JsonSchemaValidationError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Award_and_scholarship.DoesNotExist:
        return Response({'detail': 'Unknown award'}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def directorsilver_update(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    try:
        return Response(services.submit_director_silver_api(request), status=status.HTTP_200_OK)
    except JsonSchemaValidationError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Award_and_scholarship.DoesNotExist:
        return Response({'detail': 'Unknown award'}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def proficiencydm_update(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    try:
        return Response(services.submit_proficiency_dm_api(request), status=status.HTTP_200_OK)
    except JsonSchemaValidationError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    except Award_and_scholarship.DoesNotExist:
        return Response({'detail': 'Unknown award'}, status=status.HTTP_400_BAD_REQUEST)
    except ValueError as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def scholarship_details(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    
    if selectors.is_spacs_convenor(request.user):
        return Response(services.mcm_applications_list_for_convenor(request))
    else:
        return Response(services.mcm_applications_list_for_assistant(request))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def mcm_status_update(request):
    """UC-003: SPACS staff updates application status (Accept/Reject/Forward/AskInfo)."""
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    
    ser = GoldDecisionSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    pk = ser.validated_data['id']
    action = ser.validated_data['action']
    note_text = ser.validated_data.get('note')
    
    status_map = {
        'accept': 'Accept',
        'reject': 'Reject',
        'forward': 'Forwarded',
        'ask_info': 'Incomplete'
    }
    new_status = status_map.get(action)
    
    try:
        mcm = Mcm.objects.get(pk=pk)
        if action == 'forward' and not selectors.is_spacs_assistant(request.user):
             return Response({'detail': 'Only assistants can forward.'}, status=status.HTTP_403_FORBIDDEN)
        if action in ('accept', 'reject') and not selectors.is_spacs_convenor(request.user):
             return Response({'detail': 'Only convenor can finalize.'}, status=status.HTTP_403_FORBIDDEN)

        if note_text:
            services.add_application_note('mcm', pk, note_text, request.user.extrainfo)

        mcm.status = new_status
        mcm.save()
        
        # Send notification
        try:
            from notification.views import scholarship_portal_notif
            scholarship_portal_notif(request.user, mcm.student.id.user, f'mcm_{new_status.lower()}')
        except Exception:
            pass
            
    except Mcm.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    
    return Response({'detail': 'ok'})


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def director_gold_list(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    return Response(services.director_gold_list(request))


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def director_silver_list(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    return Response(services.director_silver_list(request))


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def dm_proficiency_list(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    return Response(services.proficiency_dm_list(request))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def director_gold_decision(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = GoldDecisionSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    pk = ser.validated_data['id']
    action = ser.validated_data['action']
    note_text = ser.validated_data.get('note')
    
    status_map = {
        'accept': 'Accept',
        'reject': 'Reject',
        'forward': 'Forwarded',
        'ask_info': 'Incomplete'
    }
    new_status = status_map.get(action)
    
    try:
        obj = Director_gold.objects.get(pk=pk)
        if action == 'forward' and not selectors.is_spacs_assistant(request.user):
             return Response({'detail': 'Only assistants can forward.'}, status=status.HTTP_403_FORBIDDEN)
        if action in ('accept', 'reject') and not selectors.is_spacs_convenor(request.user):
             return Response({'detail': 'Only convenor can finalize.'}, status=status.HTTP_403_FORBIDDEN)

        if note_text:
            services.add_application_note('gold', pk, note_text, request.user.extrainfo)

        obj.status = new_status
        obj.save()
    except Director_gold.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def director_silver_decision(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = GoldDecisionSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    pk = ser.validated_data['id']
    action = ser.validated_data['action']
    note_text = ser.validated_data.get('note')
    
    status_map = {
        'accept': 'Accept',
        'reject': 'Reject',
        'forward': 'Forwarded',
        'ask_info': 'Incomplete'
    }
    new_status = status_map.get(action)
    
    try:
        obj = Director_silver.objects.get(pk=pk)
        if action == 'forward' and not selectors.is_spacs_assistant(request.user):
             return Response({'detail': 'Only assistants can forward.'}, status=status.HTTP_403_FORBIDDEN)
        if action in ('accept', 'reject') and not selectors.is_spacs_convenor(request.user):
             return Response({'detail': 'Only convenor can finalize.'}, status=status.HTTP_403_FORBIDDEN)

        if note_text:
            services.add_application_note('silver', pk, note_text, request.user.extrainfo)

        obj.status = new_status
        obj.save()
    except Director_silver.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def dm_proficiency_decision(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = GoldDecisionSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    pk = ser.validated_data['id']
    action = ser.validated_data['action']
    note_text = ser.validated_data.get('note')
    
    status_map = {
        'accept': 'Accept',
        'reject': 'Reject',
        'forward': 'Forwarded',
        'ask_info': 'Incomplete'
    }
    new_status = status_map.get(action)
    
    try:
        obj = Proficiency_dm.objects.get(pk=pk)
        if action == 'forward' and not selectors.is_spacs_assistant(request.user):
             return Response({'detail': 'Only assistants can forward.'}, status=status.HTTP_403_FORBIDDEN)
        if action in ('accept', 'reject') and not selectors.is_spacs_convenor(request.user):
             return Response({'detail': 'Only convenor can finalize.'}, status=status.HTTP_403_FORBIDDEN)

        if note_text:
            services.add_application_note('dm', pk, note_text, request.user.extrainfo)

        obj.status = new_status
        obj.save()
    except Proficiency_dm.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def list_application_notes(request):
    scholarship_type = request.query_params.get('scholarship_type')
    application_id = request.query_params.get('application_id')
    return Response(services.get_application_notes(scholarship_type, application_id))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def manage_application_note(request):
    """Mark note as read or delete note."""
    note_id = request.data.get('note_id')
    action = request.data.get('action') # 'read', 'delete'
    from applications.scholarships.models import ApplicationNote
    try:
        note = ApplicationNote.objects.get(pk=note_id)
        if action == 'read':
            note.is_read = True
            note.save()
        elif action == 'delete':
            note.delete()
        return Response({'detail': 'ok'})
    except ApplicationNote.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def release_invite(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    try:
        services.create_invite_release(request.user, request.data)
    except Exception as exc:
        return Response({'detail': str(exc)}, status=status.HTTP_400_BAD_REQUEST)
    return Response({'detail': 'Invited'})


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_award_list(request):
    qs = selectors.get_all_awards()
    return Response(AwardSerializer(qs, many=True).data)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def award_catalog_update(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = CatalogUpdateSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    try:
        services.update_award_catalog(
            ser.validated_data['id'],
            ser.validated_data['catalog'],
            publish=ser.validated_data.get('publish'),
            award_name=ser.validated_data.get('award_name'),
            cpi_cutoff=ser.validated_data.get('cpi_cutoff'),
            income_ceiling=ser.validated_data.get('income_ceiling'),
            eligible_programme=ser.validated_data.get('eligible_programme')
        )
    except Award_and_scholarship.DoesNotExist:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_winners(request):
    ser = PreviousWinnersRequestSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    payload = services.previous_winners_payload(
        ser.validated_data['programme'],
        ser.validated_data['batch'],
        ser.validated_data['award_id'],
    )
    return Response(payload)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def mcm_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_mcm_for_student(student), request))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def directorgold_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_gold_for_student(student), request))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def directorsilver_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_silver_for_student(student), request))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def proficiencydm_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_proficiency_for_student(student), request))


# T3: Withdrawal Feature
@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def withdraw_application(request):
    """UC-004: Student withdraws a pending application. BR-009: only before review. BR-010: only owner."""
    if not _student(request.user):
        return Response({'detail': 'Students only.'}, status=status.HTTP_403_FORBIDDEN)
    
    scholarship_type = request.data.get('scholarship_type')
    application_id = request.data.get('application_id')
    reason = (request.data.get('reason') or '').strip()
    
    if not reason:
        return Response({'detail': 'A withdrawal reason is required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    model_map = {'mcm': Mcm, 'gold': Director_gold, 'silver': Director_silver, 'dm': Proficiency_dm}
    Model = model_map.get(scholarship_type)
    if not Model:
        return Response({'detail': 'Unknown scholarship type.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        app = Model.objects.get(pk=application_id)
    except Model.DoesNotExist:
        return Response({'detail': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    student = request.user.extrainfo.student
    
    # BR-SPACS-010: ownership check
    if app.student != student:
        return Response({'detail': 'You can only withdraw your own application.'}, status=status.HTTP_403_FORBIDDEN)
    
    # BR-SPACS-009: only allow withdrawal if not yet forwarded
    if app.status != 'Submitted':
        return Response(
            {'detail': f'Withdrawal not allowed. Your application status is "{app.status}". '
                       'You can only withdraw before the application is forwarded.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create withdrawal record (for acknowledgement by assistant)
    from applications.scholarships.models import Withdrawal
    Withdrawal.objects.create(
        scholarship_type=scholarship_type,
        application_id=application_id,
        student=student,
        reason=reason,
    )
    
    return Response({'detail': 'Your withdrawal request has been submitted and is pending approval.'})


# T4: Withdrawal Acknowledgement
@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def list_withdrawals(request):
    """UC-005: SPACS staff views pending withdrawal requests."""
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only.'}, status=status.HTTP_403_FORBIDDEN)
    
    from applications.scholarships.models import Withdrawal, Mcm, Director_gold, Director_silver, Proficiency_dm
    model_map = {'mcm': Mcm, 'gold': Director_gold, 'silver': Director_silver, 'dm': Proficiency_dm}
    pending = Withdrawal.objects.filter(acknowledged=False).select_related('student__id__user')
    data = [
        {
            'id': w.id,
            'student_name': w.student.id.user.get_full_name() or w.student.id.user.username,
            'student_id': str(w.student_id),
            'scholarship_type': w.get_scholarship_type_display(),
            'scholarship_type_key': w.scholarship_type,
            'application_id': w.application_id,
            'reason': w.reason,
            'requested_at': w.requested_at.strftime('%Y-%m-%d %H:%M'),
        }
        for w in pending
    ]

    # Join with application data for "View Details" in frontend
    for item in data:
        Model = model_map.get(item['scholarship_type_key'])
        try:
            app_obj = Model.objects.get(pk=item['application_id'])
            # Basic serialization for the detail modal
            item['application_data'] = {
                'id': app_obj.id,
                'status': app_obj.status,
                'date': app_obj.date.isoformat() if hasattr(app_obj, 'date') else None,
                'academic_year': getattr(app_obj, 'academic_year', '2024-25'),
                'semester': getattr(app_obj, 'semester', 1),
            }
            # Include more fields for a rich detail view
            for field in app_obj._meta.fields:
                val = getattr(app_obj, field.name)
                if isinstance(val, (str, int, float, bool)) or val is None:
                    item['application_data'][field.name] = val
        except:
            item['application_data'] = None

    return Response(data)


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def acknowledge_withdrawal(request):
    """UC-005: SPACS Assistant handles a withdrawal decision (APPROVE/REJECT)."""
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only.'}, status=status.HTTP_403_FORBIDDEN)
    
    withdrawal_id = request.data.get('withdrawal_id')
    action = request.data.get('action', 'approve') # 'approve' or 'reject'
    
    try:
        from applications.scholarships.models import Withdrawal, Mcm, Director_gold, Director_silver, Proficiency_dm
        import datetime as dt
        w = Withdrawal.objects.select_related('student__id__user').get(pk=withdrawal_id, acknowledged=False)
    except Withdrawal.DoesNotExist:
        return Response({'detail': 'Withdrawal request not found or already handled.'}, status=status.HTTP_404_NOT_FOUND)
    
    if action == 'approve':
        # Delete the target application
        model_map = {'mcm': Mcm, 'gold': Director_gold, 'silver': Director_silver, 'dm': Proficiency_dm}
        Model = model_map.get(w.scholarship_type)
        if Model:
            Model.objects.filter(pk=w.application_id).delete()
        
        # Mark withdrawal as handled and delete it (User requested deletion)
        w.delete()
        return Response({'detail': 'Withdrawal approved. Application removed.'})
    
    else:
        # Reject: Just delete the withdrawal request record.
        # This keeps the application active and "moves it back" to its original list.
        w.delete()
        return Response({'detail': 'Withdrawal rejected. Application remains active.'})


# T5: Application Download/Print
@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def download_application_pdf(request):
    """
    UC-007 / BR-SPACS-012: Generate and serve a PDF of a scholarship application.
    Query params: scholarship_type (mcm/gold/silver/dm), application_id (int)
    """
    scholarship_type = request.query_params.get('scholarship_type')
    application_id   = request.query_params.get('application_id')
    
    model_map = {'mcm': Mcm, 'gold': Director_gold, 'silver': Director_silver, 'dm': Proficiency_dm}
    Model = model_map.get(scholarship_type)
    if not Model:
        return Response({'detail': 'Unknown scholarship type.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        app = Model.objects.select_related('student__id__user', 'award_id').get(pk=application_id)
    except Model.DoesNotExist:
        return Response({'detail': 'Application not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    # BR-SPACS-012: access control — only owning student or SPACS staff
    is_owner = (
        _student(request.user) and
        app.student == request.user.extrainfo.student
    )
    if not is_owner and not _spacs_staff(request.user):
        return Response({'detail': 'Access denied.'}, status=status.HTTP_403_FORBIDDEN)
    
    # Build context dict with all application fields
    context = {
        'app': app,
        'student': app.student,
        'award': app.award_id,
        'scholarship_type': scholarship_type,
        'generated_at': datetime.date.today().strftime('%d %B %Y'),
    }
    
    # Render HTML template to string, convert to PDF
    from django.template.loader import render_to_string
    from django.http import HttpResponse
    html_string = render_to_string('scholarships/application_pdf.html', context)
    
    filename = f"SPACS_{scholarship_type.upper()}_application_{application_id}.pdf"
    response = HttpResponse(content_type='application/pdf')
    response['Content-Disposition'] = f'attachment; filename="{filename}"'
    
    try:
        from xhtml2pdf import pisa
        pisa_status = pisa.CreatePDF(html_string, dest=response)
        if pisa_status.err:
            return Response({'detail': 'PDF generation errors'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    except Exception as e:
        return Response({'detail': f'PDF generation failed: {str(e)}'}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
    
    return response


# T6: Explicit Forward Action
@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def forward_application(request):
    """UC-009: SPACS Assistant explicitly forwards a verified application to convener."""
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only.'}, status=status.HTTP_403_FORBIDDEN)
    
    scholarship_type = request.data.get('scholarship_type')
    application_id   = request.data.get('application_id')
    notes            = request.data.get('notes', '')
    
    model_map = {'mcm': Mcm, 'gold': Director_gold, 'silver': Director_silver, 'dm': Proficiency_dm}
    Model = model_map.get(scholarship_type)
    if not Model:
        return Response({'detail': 'Unknown type.'}, status=status.HTTP_400_BAD_REQUEST)
    
    try:
        app = Model.objects.select_related('student__id__user').get(pk=application_id)
    except Model.DoesNotExist:
        return Response({'detail': 'Not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    if app.status != 'Complete':
        return Response(
            {'detail': 'Only applications with status "Verified" (Complete) can be forwarded.'},
            status=status.HTTP_400_BAD_REQUEST
        )
    
    # Create forward record
    from applications.scholarships.models import ApplicationForward
    _, created = ApplicationForward.objects.get_or_create(
        scholarship_type=scholarship_type,
        application_id=application_id,
        defaults={'forwarded_by': request.user.extrainfo, 'notes': notes}
    )
    if not created:
        return Response({'detail': 'Application already forwarded.'}, status=status.HTTP_400_BAD_REQUEST)
    
    # BR-SPACS-008: notify student
    try:
        scholarship_portal_notif(request.user, app.student.id.user, 'application_forwarded_to_convener')
    except Exception:
        pass
    
    return Response({'detail': f'Application #{application_id} forwarded to convener.'})


# T7: Draft Auto-Save
@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def save_draft(request):
    """BR-SPACS-007: Save or update a form draft for the current student."""
    if not _student(request.user):
        return Response({'detail': 'Students only.'}, status=status.HTTP_403_FORBIDDEN)
    
    award_type = request.data.get('award_type')
    draft_data = request.data.get('draft_data')
    
    if not award_type or draft_data is None:
        return Response({'detail': 'award_type and draft_data are required.'}, status=status.HTTP_400_BAD_REQUEST)
    
    student = request.user.extrainfo.student
    from applications.scholarships.models import ApplicationDraft
    import json
    
    draft, _ = ApplicationDraft.objects.update_or_create(
        student=student,
        award_type=award_type,
        defaults={'draft_data': json.dumps(draft_data)}
    )
    return Response({'detail': 'Draft saved.', 'updated_at': draft.updated_at.isoformat()})


@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def get_draft(request):
    """BR-SPACS-007: Retrieve saved draft for the current student and award type."""
    if not _student(request.user):
        return Response({'detail': 'Students only.'}, status=status.HTTP_403_FORBIDDEN)
    
    award_type = request.query_params.get('award_type')
    student = request.user.extrainfo.student
    from applications.scholarships.models import ApplicationDraft
    import json
    
    try:
        draft = ApplicationDraft.objects.get(student=student, award_type=award_type)
        return Response({'draft_data': json.loads(draft.draft_data), 'updated_at': draft.updated_at.isoformat()})
    except ApplicationDraft.DoesNotExist:
        return Response({'draft_data': None})


@api_view(['DELETE'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def delete_draft(request):
    """BR-SPACS-007: Delete draft after successful submission."""
    if not _student(request.user):
        return Response({'detail': 'Students only.'}, status=status.HTTP_403_FORBIDDEN)
    
    award_type = request.query_params.get('award_type')
    student = request.user.extrainfo.student
    from applications.scholarships.models import ApplicationDraft
    ApplicationDraft.objects.filter(student=student, award_type=award_type).delete()
    return Response({'detail': 'Draft deleted.'})


# T8: Catalog Versioning & Publish Flag
@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def create_award(request):
    """UC-010: Convener creates a new scholarship/award entry."""
    if not selectors.is_spacs_convenor(request.user):
        return Response({'detail': 'SPACS Convenor only.'}, status=status.HTTP_403_FORBIDDEN)
    
    award_name = (request.data.get('award_name') or '').strip()
    catalog    = (request.data.get('catalog') or '').strip()
    cpi_cutoff = float(request.data.get('cpi_cutoff', 0))
    income_ceiling = int(request.data.get('income_ceiling', 0))
    eligible_programme = (request.data.get('eligible_programme') or 'all').strip()
    
    # Optional: allow setting publish_flag directly, default True
    publish_flag = request.data.get('publish_flag', True)
    
    if not award_name:
        return Response({'detail': 'award_name is required.'}, status=status.HTTP_400_BAD_REQUEST)
    if Award_and_scholarship.objects.filter(award_name=award_name).exists():
        return Response({'detail': f'Award "{award_name}" already exists.'}, status=status.HTTP_400_BAD_REQUEST)
    
    award = Award_and_scholarship.objects.create(
        award_name=award_name,
        catalog=catalog,
        publish_flag=publish_flag,
        cpi_cutoff=cpi_cutoff,
        income_ceiling=income_ceiling,
        eligible_programme=eligible_programme,
        version=1,
    )
    return Response({
        'id': award.id, 
        'award_name': award.award_name, 
        'detail': f'Award "{award_name}" created successfully.'
    })


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def retire_award(request):
    """UC-012: Convener retires (unpublishes) an award from the active catalogue."""
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only.'}, status=status.HTTP_403_FORBIDDEN)
    
    award_id = request.data.get('id')
    try:
        award = Award_and_scholarship.objects.get(pk=award_id)
    except Award_and_scholarship.DoesNotExist:
        return Response({'detail': 'Award not found.'}, status=status.HTTP_404_NOT_FOUND)
    
    award.publish_flag = False
    award.save(update_fields=['publish_flag'])
    return Response({'detail': f'Award "{award.award_name}" has been retired (unpublished).'})


# T10: Document Reuse
@api_view(['GET'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def list_student_documents(request):
    """BR-SPACS-003: Return valid previously uploaded documents for the current student."""
    if not _student(request.user):
        return Response({'detail': 'Students only.'}, status=status.HTTP_403_FORBIDDEN)
    
    student = request.user.extrainfo.student
    import datetime as dt
    from applications.scholarships.models import StudentDocument
    from django.db.models import Q
    today = dt.date.today()
    
    # Return documents that are not yet expired (or have no expiry)
    docs = StudentDocument.objects.filter(
        student=student
    ).filter(
        Q(valid_until__isnull=True) | Q(valid_until__gte=today)
    ).order_by('-uploaded_at')
    
    data = [
        {
            'id': d.id,
            'doc_type': d.doc_type,
            'doc_type_label': d.get_doc_type_display(),
            'uploaded_at': d.uploaded_at.strftime('%Y-%m-%d'),
            'valid_until': d.valid_until.strftime('%Y-%m-%d') if d.valid_until else None,
            'file_url': request.build_absolute_uri(d.file.url),
        }
        for d in docs
    ]
    return Response(data)
