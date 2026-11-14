from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
)
from django.urls import reverse_lazy
from .models import Recipient, Message, Mailing


# --- Главная страница (заглушка, заполним в Шаге 5) ---
class HomeView(TemplateView):
    template_name = 'mailings/home.html'


# --- Получатели ---
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