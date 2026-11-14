from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
)
from django.urls import reverse_lazy
from .models import Recipient, Message, Mailing

from django.utils import timezone
from django.db.models import Count

from django.shortcuts import get_object_or_404, redirect
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from .models import Attempt

class HomeView(TemplateView):
    template_name = 'mailings/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()

        # Общее количество всех рассылок
        context['total_mailings'] = Mailing.objects.count()

        # Количество активных рассылок
        # (статус 'Запущена' и текущее время между start_time и end_time)
        active_mailings = Mailing.objects.filter(
            status='Запущена',
            start_time__lte=now,
            end_time__gte=now
        )
        context['active_mailings'] = active_mailings.count()

        # Количество уникальных получателей
        context['total_recipients'] = Recipient.objects.count()

        return context


class RecipientListView(ListView):
    model = Recipient
    template_name = 'mailings/recipient_list.html'
    context_object_name = 'recipients'


class RecipientCreateView(CreateView):
    model = Recipient
    fields = ['email', 'full_name', 'comment']
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')


class RecipientUpdateView(UpdateView):
    model = Recipient
    fields = ['email', 'full_name', 'comment']
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')


class RecipientDeleteView(DeleteView):
    model = Recipient
    template_name = 'mailings/recipient_confirm_delete.html'
    success_url = reverse_lazy('mailings:recipient_list')


# --- Сообщения ---
class MessageListView(ListView):
    model = Message
    template_name = 'mailings/message_list.html'
    context_object_name = 'messages'


class MessageCreateView(CreateView):
    model = Message
    fields = ['subject', 'body']
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')


class MessageUpdateView(UpdateView):
    model = Message
    fields = ['subject', 'body']
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')


class MessageDeleteView(DeleteView):
    model = Message
    template_name = 'mailings/message_confirm_delete.html'
    success_url = reverse_lazy('mailings:message_list')


# --- Рассылки ---
class MailingListView(ListView):
    model = Mailing
    template_name = 'mailings/mailing_list.html'
    context_object_name = 'mailings'

    def get_queryset(self):
        # Пока показываем все рассылки (права доступа добавим в Части 2)
        return Mailing.objects.all()


class MailingCreateView(CreateView):
    model = Mailing
    fields = ['start_time', 'end_time', 'message', 'recipients']
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def form_valid(self, form):
        # При создании сразу вычисляем статус
        form.instance.status = 'Создана'
        response = super().form_valid(form)
        self.object.update_status()
        return response


class MailingUpdateView(UpdateView):
    model = Mailing
    fields = ['start_time', 'end_time', 'message', 'recipients']
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')


class MailingDeleteView(DeleteView):
    model = Mailing
    template_name = 'mailings/mailing_confirm_delete.html'
    success_url = reverse_lazy('mailings:mailing_list')


class MailingDetailView(DetailView):
    model = Mailing
    template_name = 'mailings/mailing_detail.html'
    context_object_name = 'mailing'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.update_status()  # ← пересчёт и сохранение статуса
        return obj


def mailing_send(request, pk):
    mailing = get_object_or_404(Mailing, pk=pk)

    # 1. Проверка времени
    now = timezone.now()
    if not (mailing.start_time <= now <= mailing.end_time):
        messages.error(request, 'Отправка невозможна: текущее время вне интервала рассылки.')
        return redirect('mailings:mailing_detail', pk=pk)

    # 2. Получение получателей
    recipients = mailing.recipients.all()
    if not recipients.exists():
        messages.warning(request, 'У рассылки нет получателей.')
        return redirect('mailings:mailing_detail', pk=pk)

    # 3. Подготовка списка для batch-создания попыток
    attempts_to_create = []
    subject = mailing.message.subject
    body = mailing.message.body

    for recipient in recipients:
        try:
            # Отправка письма
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings,
                                                                  'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
                recipient_list=[recipient.email],
                fail_silently=False,
            )
            # Успешная попытка
            attempts_to_create.append(
                Attempt(
                    mailing=mailing,
                    status='Успешно',
                    server_response='Письмо отправлено успешно'
                )
            )
        except Exception as e:
            # Неуспешная попытка
            attempts_to_create.append(
                Attempt(
                    mailing=mailing,
                    status='Не успешно',
                    server_response=str(e)
                )
            )

    # 4. Batch-создание попыток
    Attempt.objects.bulk_create(attempts_to_create)

    # 5. Обновление статуса (на случай, если он ещё не "Запущена")
    mailing.update_status()

    messages.success(request, f'Рассылка завершена. Обработано получателей: {len(attempts_to_create)}.')
    return redirect('mailings:mailing_detail', pk=pk)