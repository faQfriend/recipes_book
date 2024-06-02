import json

from django.core.management.base import BaseCommand

from api.models import Ingredient


class Command(BaseCommand):
    help = 'Load tags from a JSON file'

    def handle(self, *args, **options):
        file_path = 'api/management/data/ingredients.json'

        with open(file_path, 'r') as file:
            ingredients_data = json.load(file)

        for ingredient_data in ingredients_data:
            name = ingredient_data['name']
            if not Ingredient.objects.filter(name=name).exists():
                Ingredient.objects.create(**ingredient_data)
                self.stdout.write(self.style.SUCCESS(
                    f'Ингредиент "{name}" успешно добавлен!'))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Ингредиент "{name}" уже был добавлен ранее.'
                        f'Пропуск.')
                )
        self.stdout.write(self.style.SUCCESS('Загрузка выполнена!'))
