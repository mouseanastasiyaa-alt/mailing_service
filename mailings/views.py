from django.views.generic import (
    ListView, CreateView, UpdateView, DeleteView, DetailView, TemplateView
)
from django.urls import reverse_lazy
from django.utils import timezone
from django.shortcuts import get_object_or_404, redirect, render
from django.contrib import messages
from django.core.mail import send_mail
from django.conf import settings
from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.contrib.auth import login
from django.contrib.auth.models import User
from django.utils.http import urlsafe_base64_encode, urlsafe_base64_decode
from django.utils.encoding import force_bytes, force_str
from django.contrib.auth.tokens import default_token_generator

from .models import Recipient, Message, Mailing, Attempt
from .forms import RegistrationForm, MailingForm
from django.views.decorators.cache import cache_page
from django.utils.decorators import method_decorator


# --- Вспомогательные функции ---
def is_manager(user):
    """Проверяет, состоит ли пользователь в группе 'Менеджеры'."""
    return user.is_authenticated and user.groups.filter(name='Менеджеры').exists()


# --- Главная страница ---
@method_decorator(cache_page(60), name='dispatch')
class HomeView(TemplateView):
    template_name = 'mailings/home.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        user = self.request.user

        if not user.is_authenticated:
            context['total_mailings'] = 0
            context['active_mailings'] = 0
            context['total_recipients'] = 0
            return context

        if is_manager(user):
            context['total_mailings'] = Mailing.objects.count()
            context['active_mailings'] = Mailing.objects.filter(
                status='Запущена',
                start_time__lte=now,
                end_time__gte=now
            ).count()
            context['total_recipients'] = Recipient.objects.count()
        else:
            context['total_mailings'] = Mailing.objects.filter(owner=user).count()
            context['active_mailings'] = Mailing.objects.filter(
                owner=user,
                status='Запущена',
                start_time__lte=now,
                end_time__gte=now
            ).count()
            context['total_recipients'] = Recipient.objects.filter(owner=user).count()

        return context


# --- Получатели ---
class RecipientListView(LoginRequiredMixin, ListView):
    model = Recipient
    template_name = 'mailings/recipient_list.html'
    context_object_name = 'recipients'

    def get_queryset(self):
        if is_manager(self.request.user):
            return Recipient.objects.all()
        return Recipient.objects.filter(owner=self.request.user)


class RecipientCreateView(LoginRequiredMixin, CreateView):
    model = Recipient
    fields = ['email', 'full_name', 'comment']
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class RecipientUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Recipient
    fields = ['email', 'full_name', 'comment']
    template_name = 'mailings/recipient_form.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


class RecipientDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Recipient
    template_name = 'mailings/recipient_confirm_delete.html'
    success_url = reverse_lazy('mailings:recipient_list')

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


# --- Сообщения ---
class MessageListView(LoginRequiredMixin, ListView):
    model = Message
    template_name = 'mailings/message_list.html'
    context_object_name = 'messages'

    def get_queryset(self):
        if is_manager(self.request.user):
            return Message.objects.all()
        return Message.objects.filter(owner=self.request.user)


class MessageCreateView(LoginRequiredMixin, CreateView):
    model = Message
    fields = ['subject', 'body']
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')

    def form_valid(self, form):
        form.instance.owner = self.request.user
        return super().form_valid(form)


class MessageUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Message
    fields = ['subject', 'body']
    template_name = 'mailings/message_form.html'
    success_url = reverse_lazy('mailings:message_list')

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


class MessageDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Message
    template_name = 'mailings/message_confirm_delete.html'
    success_url = reverse_lazy('mailings:message_list')

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


# --- Рассылки ---
class MailingListView(LoginRequiredMixin, ListView):
    model = Mailing
    template_name = 'mailings/mailing_list.html'
    context_object_name = 'mailings'

    def get_queryset(self):
        if is_manager(self.request.user):
            return Mailing.objects.all()
        return Mailing.objects.filter(owner=self.request.user)


class MailingCreateView(LoginRequiredMixin, CreateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def form_valid(self, form):
        form.instance.owner = self.request.user
        form.instance.status = 'Создана'
        response = super().form_valid(form)
        self.object.update_status()
        return response


class MailingUpdateView(LoginRequiredMixin, UserPassesTestMixin, UpdateView):
    model = Mailing
    form_class = MailingForm
    template_name = 'mailings/mailing_form.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def get_form_kwargs(self):
        kwargs = super().get_form_kwargs()
        kwargs['user'] = self.request.user
        return kwargs

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


class MailingDeleteView(LoginRequiredMixin, UserPassesTestMixin, DeleteView):
    model = Mailing
    template_name = 'mailings/mailing_confirm_delete.html'
    success_url = reverse_lazy('mailings:mailing_list')

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


class MailingDetailView(LoginRequiredMixin, UserPassesTestMixin, DetailView):
    model = Mailing
    template_name = 'mailings/mailing_detail.html'
    context_object_name = 'mailing'

    def get_object(self, queryset=None):
        obj = super().get_object(queryset)
        obj.update_status()
        return obj

    def test_func(self):
        obj = self.get_object()
        return is_manager(self.request.user) or obj.owner == self.request.user


# --- Отправка рассылки ---
def mailing_send(request, pk):
    mailing = get_object_or_404(Mailing, pk=pk)

    now = timezone.now()
    if not (mailing.start_time <= now <= mailing.end_time):
        messages.error(request, 'Отправка невозможна: текущее время вне интервала рассылки.')
        return redirect('mailings:mailing_detail', pk=pk)

    recipients = mailing.recipients.all()
    if not recipients.exists():
        messages.warning(request, 'У рассылки нет получателей.')
        return redirect('mailings:mailing_detail', pk=pk)

    attempts_to_create = []
    subject = mailing.message.subject
    body = mailing.message.body

    for recipient in recipients:
        try:
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL if hasattr(settings, 'DEFAULT_FROM_EMAIL') else 'noreply@example.com',
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

    Attempt.objects.bulk_create(attempts_to_create)
    mailing.update_status()

    messages.success(request, f'Рассылка завершена. Обработано получателей: {len(attempts_to_create)}.')
    return redirect('mailings:mailing_detail', pk=pk)


# --- Регистрация и активация ---
def register(request):
    if request.method == 'POST':
        form = RegistrationForm(request.POST)
        if form.is_valid():
            user = form.save(commit=False)
            user.is_active = False
            user.set_password(form.cleaned_data['password'])
            user.save()

            token = default_token_generator.make_token(user)
            uid = urlsafe_base64_encode(force_bytes(user.pk))
            activation_link = request.build_absolute_uri(
                f'/accounts/activate/{uid}/{token}/'
            )

            subject = 'Подтверждение регистрации'
            message = f'Здравствуйте, {user.username}!\n\nДля активации аккаунта перейдите по ссылке:\n{activation_link}'
            send_mail(
                subject=subject,
                message=message,
                from_email='noreply@example.com',
                recipient_list=[user.email],
                fail_silently=False,
            )

            return render(request, 'registration/registration_success.html', {'email': user.email})
    else:
        form = RegistrationForm()

    return render(request, 'registration/register.html', {'form': form})


def activate(request, uidb64, token):
    try:
        uid = force_str(urlsafe_base64_decode(uidb64))
        user = User.objects.get(pk=uid)
    except (TypeError, ValueError, OverflowError, User.DoesNotExist):
        user = None

    if user is not None and default_token_generator.check_token(user, token):
        user.is_active = True
        user.save()
        login(request, user)
        return render(request, 'registration/activation_success.html')
    else:
        return render(request, 'registration/activation_invalid.html')


from django.db.models import Count, Q

@method_decorator(cache_page(30), name='dispatch')
class StatisticsView(LoginRequiredMixin, TemplateView):
    template_name = 'mailings/statistics.html'

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        user = self.request.user

        # Фильтруем рассылки: менеджер видит все, пользователь — только свои
        if is_manager(user):
            mailings = Mailing.objects.all()
            attempts = Attempt.objects.all()
        else:
            mailings = Mailing.objects.filter(owner=user)
            attempts = Attempt.objects.filter(mailing__owner=user)

        # 1. Общее количество отправленных сообщений (успешных попыток)
        context['total_sent'] = attempts.filter(status='Успешно').count()

        # 2. Статистика по попыткам
        context['total_success'] = attempts.filter(status='Успешно').count()
        context['total_failed'] = attempts.filter(status='Не успешно').count()

        # 3. Детализация по каждой рассылке (сколько успешных и неуспешных попыток)
        mailing_stats = []
        for mailing in mailings:
            m_attempts = attempts.filter(mailing=mailing)
            mailing_stats.append({
                'mailing': mailing,
                'success': m_attempts.filter(status='Успешно').count(),
                'failed': m_attempts.filter(status='Не успешно').count(),
                'total': m_attempts.count(),
            })
        context['mailing_stats'] = mailing_stats

        return context