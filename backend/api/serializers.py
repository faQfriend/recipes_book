from collections import OrderedDict

from django.core.validators import MinValueValidator
from django.db import transaction
from djoser.serializers import UserCreateSerializer, UserSerializer
from drf_extra_fields.fields import Base64ImageField
from rest_framework.relations import PrimaryKeyRelatedField
from rest_framework.serializers import (CharField, IntegerField,
                                        ModelSerializer, SerializerMethodField,
                                        ValidationError)

from api.models import Ingredient, IngredientRecipe, Recipe, Subscribe, Tag
from users.models import CustomUser


MIN_COOKING_TIME = 1


class CustomUserCreateSerializer(UserCreateSerializer):
    class Meta(UserCreateSerializer.Meta):
        model = CustomUser
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'password',
        )


class CustomUserSerializer(UserSerializer):
    is_subscribed = SerializerMethodField()

    class Meta(UserSerializer.Meta):
        model = CustomUser
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed'
        )

    def get_is_subscribed(self, obj):
        follower = self.context.get('request').user
        if follower and follower.is_authenticated:
            return Subscribe.objects.filter(author=obj,
                                            follower=follower).exists()
        return False


class TagSerializer(ModelSerializer):

    class Meta:
        model = Tag
        fields = (
            'id',
            'name',
            'color',
            'slug',
        )


class IngredientSerializer(ModelSerializer):

    class Meta:
        model = Ingredient
        fields = (
            'id',
            'name',
            'measurement_unit',
        )


class IngredientRecipeSerializer(ModelSerializer):
    id = PrimaryKeyRelatedField(
        source='ingredient',
        queryset=Ingredient.objects.all()
    )
    name = CharField(
        source='ingredient.name',
        read_only=True
    )
    measurement_unit = CharField(
        source='ingredient.measurement_unit',
        read_only=True
    )
    amount = IntegerField(
        validators=[MinValueValidator(1)]
    )

    class Meta:
        model = IngredientRecipe
        fields = (
            'id',
            'name',
            'measurement_unit',
            'amount',
        )


class RecipeSerializer(ModelSerializer):
    tags = PrimaryKeyRelatedField(
        queryset=Tag.objects.all(),
        many=True,
    )
    author = CustomUserSerializer(
        read_only=True,
    )
    ingredients = IngredientRecipeSerializer(
        source='ingredientrecipe_set',
        many=True
    )
    is_favorited = SerializerMethodField()
    is_in_shopping_cart = SerializerMethodField()
    image = Base64ImageField()

    class Meta:
        model = Recipe
        fields = (
            'id',
            'tags',
            'author',
            'ingredients',
            'is_favorited',
            'is_in_shopping_cart',
            'name',
            'image',
            'text',
            'cooking_time',
        )

    def to_representation(self, instance):
        representation = super().to_representation(instance)
        representation['tags'] = TagSerializer(instance.tags.all(),
                                               many=True).data
        return representation

    def get_is_favorited(self, obj):
        user = self.context['request'].user
        return (obj.favorites.filter(user=user).exists()
                if user.is_authenticated
                else False)

    def get_is_in_shopping_cart(self, obj):
        user = self.context['request'].user
        return (obj.shopping_cart.filter(user=user).exists()
                if user.is_authenticated
                else False)

    def validate_tags(self, value):
        if not value:
            raise ValidationError({'Поле Tags пустое.'})
        tags_data = value

        existing_datas = set()
        for field_data in tags_data:
            if field_data in existing_datas:
                raise ValidationError({f'{field_data} дублируется.'})
            existing_datas.add(field_data)
        return value

    def validate_image(self, value):
        if value is None:
            raise ValidationError({'Поле Image пустое.'})
        return value

    def validate_cooking_time(self, value):
        if value < MIN_COOKING_TIME:
            raise ValidationError({'Поле Cooking_time меньше 1.'})
        return value

    def validate_ingredients(self, value):
        if not value:
            raise ValidationError({'Поле Ingredients пустое.'})
        ingredients_data = value

        existing_ingredients_id = set()
        ingredient_list = []
        for ingredient_data in ingredients_data:
            ingredient_id = ingredient_data['ingredient'].id
            amount = int(ingredient_data['amount'])
            try:
                ingredient = Ingredient.objects.get(id=ingredient_id)
            except Ingredient.DoesNotExist:
                raise ValidationError(
                    {f'Несуществующий ингредиент с id {ingredient_id}'}
                )
            if ingredient_id in existing_ingredients_id:
                raise ValidationError(
                    {f'Ингредиент с id {ingredient_id} дублируется.'}
                )
            existing_ingredients_id.add(ingredient_id)
            if amount < 1:
                raise ValidationError({'Поле amount меньше 1.'})

            ingredient_list.append(
                OrderedDict([('ingredient', ingredient), ('amount', amount)])
            )
        return ingredient_list

    def ingredient_recipe_list(self, ingredients_data, recipe):
        ingredient_recipe_list = []
        for ingredient_data in ingredients_data:
            ingredient = ingredient_data['ingredient']
            amount = ingredient_data['amount']
            ingredient_recipe = IngredientRecipe(
                recipe=recipe,
                ingredient=ingredient,
                amount=amount,
            )
            ingredient_recipe_list.append(ingredient_recipe)
        IngredientRecipe.objects.bulk_create(ingredient_recipe_list)

    @transaction.atomic
    def create(self, validated_data):
        author_data = (self.context['request'].user
                       if self.context.get('request')
                       else None)
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredientrecipe_set')

        recipe = Recipe.objects.create(author=author_data, **validated_data)
        recipe.tags.set(tags_data)

        self.ingredient_recipe_list(ingredients_data, recipe)
        return recipe

    @transaction.atomic
    def update(self, instance, validated_data):
        tags_data = validated_data.pop('tags')
        ingredients_data = validated_data.pop('ingredientrecipe_set')
        updated_recipe = super().update(instance, validated_data)

        updated_recipe.tags.clear()
        updated_recipe.tags.set(tags_data)

        updated_recipe.ingredients.clear()
        self.ingredient_recipe_list(ingredients_data, instance)
        return instance


class RecipeMinifiedSerializer(ModelSerializer):

    class Meta:
        model = Recipe
        fields = (
            'id',
            'image',
            'name',
            'cooking_time',
        )
        read_only_fields = (
            'image',
            'name',
            'cooking_time',
        )

    def validate(self, data):
        recipe = self.context.get('recipe')
        user = self.context.get('user')
        model = self.context.get('model')

        if self.context['request'].method == 'POST':
            if model.objects.filter(
                    recipe=recipe,
                    user=user
            ).exists():
                raise ValidationError({'Рецепт уже в корзине/избранном.'})
            return data

        try:
            model.objects.get(
                recipe=recipe,
                user=user
            )
        except model.DoesNotExist:
            raise ValidationError(
                {'Такого рецепта нет в корзине/избранном.'}
            )
        return data


class SubscribeSerializer(CustomUserSerializer):
    recipes = SerializerMethodField()
    recipes_count = SerializerMethodField()

    class Meta:
        model = CustomUser
        fields = (
            'email',
            'id',
            'username',
            'first_name',
            'last_name',
            'is_subscribed',
            'recipes',
            'recipes_count',
        )
        read_only_fields = (
            'email',
            'username',
            'first_name',
            'last_name',
        )

    def validate(self, data):
        author = self.instance
        follower = self.context.get('request').user

        if self.context['request'].method == 'POST':
            if Subscribe.objects.filter(author=author,
                                        follower=follower).exists():
                raise ValidationError({'Вы уже подписаны.'})
            if author == follower:
                raise ValidationError({'Нельзя подписаться на себя.'})
            return data

        try:
            Subscribe.objects.get(author=author,
                                  follower=follower)
        except Subscribe.DoesNotExist:
            raise ValidationError({'Несуществующая подписка.'},)
        return data

    def get_recipes_count(self, obj):
        return obj.recipe_set.count()

    def get_recipes(self, obj):
        queryset = obj.recipe_set.all()
        recipes_limit = self.context.get('recipes_limit')
        if recipes_limit:
            queryset = queryset[:int(recipes_limit)]
        serializer = RecipeMinifiedSerializer(queryset,
                                              many=True,
                                              read_only=True,)
        return serializer.data
