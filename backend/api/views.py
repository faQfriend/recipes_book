from django.db.models import Sum
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django_filters.rest_framework import DjangoFilterBackend
from djoser.views import UserViewSet
from rest_framework import status
from rest_framework.authentication import (BasicAuthentication,
                                           TokenAuthentication)
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.viewsets import ModelViewSet, ReadOnlyModelViewSet

from api.filters import IngredientFilterSet, RecipeFilterSet
from api.models import (Favorite, Ingredient, IngredientRecipe, Recipe,
                        ShoppingCart, Subscribe, Tag)
from api.pagination import CustomPagination, CustomUserPagination
from api.permissions import IsAdminOrReadOnly, IsAuthorOrReadOnly
from api.serializers import (CustomUserSerializer, IngredientSerializer,
                             RecipeMinifiedSerializer, RecipeSerializer,
                             SubscribeSerializer, TagSerializer)
from users.models import CustomUser


class CustomUserViewSet(UserViewSet):
    queryset = CustomUser.objects.all()
    serializer_class = CustomUserSerializer
    pagination_class = CustomUserPagination
    authentication_classes = [BasicAuthentication, TokenAuthentication]
    permission_classes = [AllowAny | IsAuthenticated]

    @action(
        detail=False,
        methods=['get'],
        permission_classes=[IsAuthenticated],
    )
    def me(self, request):
        user = request.user
        serializer = CustomUserSerializer(user, context={'request': request})
        return Response(serializer.data)

    @action(
        detail=False,
        methods=['get'],
    )
    def subscriptions(self, request):
        user = request.user
        queryset = CustomUser.objects.filter(authors__follower=user)
        page = self.paginate_queryset(queryset)
        recipes_limit = request.GET.get('recipes_limit', None)
        serializer = SubscribeSerializer(
            page,
            many=True,
            context={'recipes_limit': recipes_limit,
                     'request': request},
        )
        if page is not None:
            return self.get_paginated_response(serializer.data)
        return Response(serializer.data)

    @action(
        detail=True,
        methods=['post', 'delete'],
        permission_classes=[IsAuthenticated],
    )
    def subscribe(self, request, **kwargs):
        author_pk = self.kwargs.get('id')
        author = get_object_or_404(CustomUser, pk=author_pk)
        follower = request.user
        recipes_limit = request.GET.get('recipes_limit', None)
        serializer = SubscribeSerializer(
            author,
            data=request.data,
            context={'request': request,
                     'recipes_limit': recipes_limit,
                     'follower': follower},
        )
        serializer.is_valid(raise_exception=True)

        if request.method == 'POST':
            subscription = Subscribe.objects.create(
                author=author,
                follower=follower,
            )
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)

        subscription = Subscribe.objects.get(
            author=author,
            follower=follower
        )
        subscription.delete()
        return Response({'Вы отписаны.'},
                        status=status.HTTP_204_NO_CONTENT)


class TagViewSet(ReadOnlyModelViewSet):
    queryset = Tag.objects.all()
    serializer_class = TagSerializer


class IngredientViewSet(ReadOnlyModelViewSet):
    queryset = Ingredient.objects.all()
    serializer_class = IngredientSerializer
    filter_backends = [DjangoFilterBackend]
    filterset_class = IngredientFilterSet


class RecipeViewSet(ModelViewSet):
    queryset = Recipe.objects.all()
    serializer_class = RecipeSerializer
    permission_classes = [IsAuthorOrReadOnly | IsAdminOrReadOnly]
    pagination_class = CustomPagination
    filter_backends = [DjangoFilterBackend]
    filterset_class = RecipeFilterSet

    def add_obj(self, model, recipe, user):
        model.objects.create(recipe=recipe, user=user)

    def del_obj(self, model, recipe, user):
        obj = model.objects.get(recipe=recipe, user=user)
        obj.delete()

    def serialize_obj(self, model, request, **kwargs):
        recipe_pk = self.kwargs.get('pk')
        recipe = get_object_or_404(Recipe, pk=recipe_pk)
        user = request.user
        serializer = RecipeMinifiedSerializer(recipe,
                                              data=request.data,
                                              context={'request': request,
                                                       'recipe': recipe,
                                                       'user': user,
                                                       'model': model},)
        serializer.is_valid(raise_exception=True)
        return serializer, recipe, user

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=RecipeMinifiedSerializer,
    )
    def shopping_cart(self, request, **kwargs):
        serializer, recipe, user = self.serialize_obj(ShoppingCart,
                                                      request, **kwargs)

        if request.method == 'POST':
            self.add_obj(ShoppingCart, recipe, user)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)

        self.del_obj(ShoppingCart, recipe, user)
        return Response({'Рецепт удален из корзины.'},
                        status=status.HTTP_204_NO_CONTENT)

    def generate_shopping_cart(self, user):
        ingredients_queryset = IngredientRecipe.objects.filter(
            recipe__shopping_cart__user=user
        ).values(
            'ingredient__name',
            'ingredient__measurement_unit',
        ).annotate(total_amount=Sum('amount'))

        shopping_cart_content = 'Список покупок: \n\n'
        shopping_cart_content += '\n'.join([
            f'{index + 1}. {ingredient["ingredient__name"]}:'
            f' {ingredient["total_amount"]}'
            f' {ingredient["ingredient__measurement_unit"]}'
            for index, ingredient in enumerate(ingredients_queryset)
        ])
        return shopping_cart_content

    @action(
        detail=False,
        methods=['get'],
    )
    def download_shopping_cart(self, request):
        user_shopping_cart_content = self.generate_shopping_cart(request.user)

        file_name = 'shopping_cart.txt'
        response = HttpResponse(user_shopping_cart_content,
                                content_type='text/plain')
        response['Content-Disposition'] = f'attachment; filename={file_name}'
        return response

    @action(
        detail=True,
        methods=['post', 'delete'],
        serializer_class=RecipeMinifiedSerializer,
    )
    def favorite(self, request, **kwargs):
        serializer, recipe, user = self.serialize_obj(Favorite,
                                                      request, **kwargs)
        if request.method == 'POST':
            self.add_obj(Favorite, recipe, user)
            return Response(serializer.data,
                            status=status.HTTP_201_CREATED)

        self.del_obj(Favorite, recipe, user)
        return Response({'Рецепт удален из избранного.'},
                        status=status.HTTP_204_NO_CONTENT)
