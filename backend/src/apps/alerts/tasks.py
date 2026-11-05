from collections import defaultdict

from celery import shared_task
from django.conf import settings
from django.core.mail import EmailMultiAlternatives

from apps.alerts.models import DelayAlert


@shared_task(
    name="alerts.send_delay_alert_emails",
    autoretry_for=(Exception,),
    retry_backoff=True,
    max_retries=3,
)  # type: ignore[untyped-decorator]
def send_delay_alert_emails(alert_ids: list[str]) -> int:
    """Send one monthly summary per CA/GP; escalations never send email."""
    if (
        not settings.ALERT_EMAIL_ENABLED
        or not settings.EMAIL_HOST
        or not settings.DEFAULT_FROM_EMAIL
    ):
        return 0
    alerts = DelayAlert.objects.filter(pk__in=alert_ids, state=DelayAlert.State.NEW).select_related(
        "credit_request"
    )
    grouped: dict[tuple[str, str], list[DelayAlert]] = defaultdict(list)
    for alert in alerts:
        employee = (
            alert.credit_request.ca_caa
            if alert.responsible_role == "CA/CAA"
            else alert.credit_request.gp
        )
        if employee and employee.email:
            grouped[(employee.email, alert.responsible_name or alert.responsible_role)].append(
                alert
            )
    sent = 0
    for (email, name), items in grouped.items():
        period = items[0].reporting_period.strftime("%m/%Y")
        lines = [
            f"Bonjour {name},",
            "",
            f"Le Suivi d'encours {period} signale les retards suivants :",
            "",
        ]
        lines.extend(
            f"- {item.credit_request.reference} — {item.get_rule_display()} "
            f"— depuis le {item.started_on:%d/%m/%Y}"
            for item in items
        )
        lines.extend(
            ["", "Action attendue : mettre à jour le prochain suivi après traitement du dossier."]
        )
        subject = f"[Credit Operations Platform] {len(items)} alerte(s) de délai — {period}"
        EmailMultiAlternatives(
            subject, "\n".join(lines), settings.DEFAULT_FROM_EMAIL, [email]
        ).send(fail_silently=False)
        sent += 1
    return sent
