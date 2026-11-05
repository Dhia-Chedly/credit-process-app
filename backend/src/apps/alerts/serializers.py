from rest_framework import serializers

from apps.alerts.models import DelayAlert


class DelayAlertSerializer(serializers.ModelSerializer[DelayAlert]):
    agency_name = serializers.CharField(source="agency.name", read_only=True)
    reference = serializers.CharField(source="credit_request.reference", read_only=True)
    application_id = serializers.UUIDField(source="credit_request_id", read_only=True)
    rule_label = serializers.CharField(source="get_rule_display", read_only=True)
    state_label = serializers.CharField(source="get_state_display", read_only=True)

    class Meta:
        model = DelayAlert
        fields = (
            "id",
            "agency",
            "agency_name",
            "reference",
            "application_id",
            "rule",
            "rule_label",
            "state",
            "state_label",
            "reporting_period",
            "started_on",
            "responsible_role",
            "responsible_name",
        )
        read_only_fields = fields
