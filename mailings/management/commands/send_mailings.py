from django.core.management.base import BaseCommand
from django.utils import timezone
from django.core.mail import send_mail
from django.conf import settings
from mailings.models import Mailing, Attempt

class Command(BaseCommand):
    help = 'Отправляет все активные рассылки (статус "Запущена" и текущее время в интервале)'

    def handle(self, *args, **options):
        now = timezone.now()

        # Ищем рассылки, которые должны быть запущены
        active_mailings = Mailing.objects.filter(
            start_time__lte=now,
            end_time__gte=now,
            status='Запущена'
        )

        if not active_mailings.exists():
            self.stdout.write(self.style.WARNING('Нет активных рассылок для отправки.'))
            return

        for mailing in active_mailings:
            recipients = mailing.recipients.all()
            if not recipients.exists():
                self.stdout.write(self.style.WARNING(f'Рассылка {mailing.id} не имеет получателей. Пропущено.'))
                continue

            subject = mailing.message.subject
            body = mailing.message.body
            attempts_to_create = []

            self.stdout.write(f'Отправка рассылки {mailing.id}...')

            for recipient in recipients:
                try:
                    send_mail(
                        subject=subject,
                        message=body,
                        from_email=settings.DEFAULT_FROM_EMAIL,
                        recipient_list=[recipient.email],
                        fail_silently=False,
                    )
                    attempts_to_create.append(
                        Attempt(
                            mailing=mailing,
                            status='Успешно',
                            server_response='Письмо отправлено успешно'
                        )
                    )
                except Exception as e:
                    attempts_to_create.append(
                        Attempt(
                            mailing=mailing,
                            status='Не успешно',
                            server_response=str(e)
                        )
                    )

            # Batch-создание попыток
            Attempt.objects.bulk_create(attempts_to_create)

            # Обновляем статус (на случай, если он изменился)
            mailing.update_status()

            self.stdout.write(self.style.SUCCESS(
                f'Рассылка {mailing.id} завершена. Обработано: {len(attempts_to_create)}.'
            ))

        self.stdout.write(self.style.SUCCESS('Все активные рассылки обработаны.'))