from django.conf.urls import url
from django.urls import include, path

from . import web_views

urlpatterns = [
    url(r'^$', web_views.spacs),
    url(r'^student_view/?$', web_views.student_view),
    url(r'^convener_view/?$', web_views.convener_view),
    url(r'^staff_view/?$', web_views.staff_view),
    url(r'^stats/?$', web_views.stats),
    url(r'^convenerCatalogue/?$', web_views.convenerCatalogue),
    url(r'^getWinners/?$', web_views.getWinners),
    url(r'^get_MCM_Flag/?$', web_views.get_MCM_Flag),
    url(r'^getConvocationFlag/?$', web_views.getConvocationFlag),
    url(r'^getContent/?$', web_views.getContent),
    url(r'^updateEndDate/?$', web_views.updateEndDate),
    path('', include('applications.scholarships.api.urls')),
]
