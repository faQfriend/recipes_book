import json

from django.core.management.base import BaseCommand

from api.models import Tag


class Command(BaseCommand):
    help = 'Load tags from a JSON file'

    def handle(self, *args, **options):
        file_path = 'api/management/data/tags.json'

        with open(file_path, 'r') as file:
            tags_data = json.load(file)

        for tag_data in tags_data:
            slug = tag_data['slug']
            if not Tag.objects.filter(slug=slug).exists():
                Tag.objects.create(**tag_data)
                self.stdout.write(self.style.SUCCESS(
                    f'Тег "{slug}" успешно добавлен!'))
            else:
                self.stdout.write(
                    self.style.SUCCESS(
                        f'Тег "{slug}" уже был добавлен ранее. Пропуск.'))
        self.stdout.write(self.style.SUCCESS('Загрузка выполнена!'))
