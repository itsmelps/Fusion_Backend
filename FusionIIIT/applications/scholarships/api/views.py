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
    return Response(services.mcm_applications_list_for_convenor(request))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def mcm_status_update(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = IdStatusSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    pk = ser.validated_data['id']
    new_status = services.map_mcm_status_from_client(ser.validated_data['status'])
    updated = Mcm.objects.filter(pk=pk).update(status=new_status)
    if not updated:
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
    st = 'Accept' if action == 'accept' else 'Reject'
    updated = Director_gold.objects.filter(pk=pk).update(status=st)
    if not updated:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def director_silver_decision(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = IdStatusSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    st = services.map_medal_status_from_client(ser.validated_data['status'])
    updated = Director_silver.objects.filter(pk=ser.validated_data['id']).update(status=st)
    if not updated:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def dm_proficiency_decision(request):
    if not _spacs_staff(request.user):
        return Response({'detail': 'SPACS staff only'}, status=status.HTTP_403_FORBIDDEN)
    ser = IdStatusSerializer(data=request.data)
    ser.is_valid(raise_exception=True)
    st = services.map_medal_status_from_client(ser.validated_data['status'])
    updated = Proficiency_dm.objects.filter(pk=ser.validated_data['id']).update(status=st)
    if not updated:
        return Response({'detail': 'Not found'}, status=status.HTTP_404_NOT_FOUND)
    return Response({'detail': 'ok'})


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
        services.update_award_catalog(ser.validated_data['id'], ser.validated_data['catalog'])
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
    return Response(services.student_status_rows(selectors.get_mcm_for_student(student)))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def directorgold_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_gold_for_student(student)))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def directorsilver_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_silver_for_student(student)))


@api_view(['POST'])
@authentication_classes([TokenAuthentication, SessionAuthentication])
@permission_classes([IsAuthenticated])
def proficiencydm_show(request):
    if not _student(request.user):
        return Response({'detail': 'Students only'}, status=status.HTTP_403_FORBIDDEN)
    student = request.user.extrainfo.student
    return Response(services.student_status_rows(selectors.get_proficiency_for_student(student)))
