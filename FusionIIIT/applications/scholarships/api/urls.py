from django.urls import path

from . import views

urlpatterns = [
    path('check-application-window/', views.check_application_window),
    path('mcm_update/', views.mcm_update),
    path('directorgold_update/', views.directorgold_update),
    path('directorsilver_update/', views.directorsilver_update),
    path('proficiencydm_update/', views.proficiencydm_update),
    path('scholarship-details/', views.scholarship_details),
    path('mcm/status-update/', views.mcm_status_update),
    path('director_gold_list/', views.director_gold_list),
    path('director-silver/', views.director_silver_list),
    path('dm-proficiency-list/', views.dm_proficiency_list),
    path('director-gold/accept-reject/', views.director_gold_decision),
    path('api/director_silver/decision/', views.director_silver_decision),
    path('api/dm-proficiency/decsion/', views.dm_proficiency_decision),
    path('api/dm-proficiency/decision/', views.dm_proficiency_decision),
    path('release', views.release_invite),
    path('release/', views.release_invite),
    path('create-award/', views.create_award_list),
    path('award/', views.award_catalog_update),
    path('get-winners/', views.get_winners),
    path('mcm_show/', views.mcm_show),
    path('directorgold_show/', views.directorgold_show),
    path('directorsilver_show/', views.directorsilver_show),
    path('proficiencydm_show/', views.proficiencydm_show),
    # T3: Withdrawal
    path('withdraw/', views.withdraw_application),
    # T4: Withdrawal acknowledgement
    path('withdrawals/', views.list_withdrawals),
    path('withdrawals/acknowledge/', views.acknowledge_withdrawal),
    # T5: PDF download
    path('download-application/', views.download_application_pdf),
    # T6: Forward to convener
    path('forward-application/', views.forward_application),
    # T7: Draft auto-save
    path('draft/save/', views.save_draft),
    path('draft/get/', views.get_draft),
    path('draft/delete/', views.delete_draft),
    # T8: Catalog versioning
    path('create-award-new/', views.create_award),
    path('retire-award/', views.retire_award),
    # T10: Document reuse
    path('my-documents/', views.list_student_documents),
]
