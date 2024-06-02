from rest_framework.pagination import (LimitOffsetPagination,
                                       PageNumberPagination)


class CustomPagination(PageNumberPagination):
    page_size = 6
    page_size_query_param = 'limit'


class NonePagination(PageNumberPagination):
    page_size = None
    max_page_size = None
    page_query_param = 'page'


class CustomUserPagination(LimitOffsetPagination):
    default_limit = 10
    max_limit = 100
