# APP: Django
# FILE: apps/api/urls_copy.py
from django.urls import path
from . import copy_mock

urlpatterns = [
    path('copy/status', copy_mock.copy_status, name='copy_status'),
    path('copy/traders', copy_mock.copy_traders, name='copy_traders'),
    path('copy/trades', copy_mock.copy_trades, name='copy_trades'),
    path('discovery/discovery-status', copy_mock.discovery_status, name='discovery_status'),
]