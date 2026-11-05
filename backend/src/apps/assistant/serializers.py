from typing import Any

from rest_framework import serializers


class ConversationMessageSerializer(serializers.Serializer[Any]):
    role = serializers.CharField(max_length=9)
    content = serializers.CharField(max_length=2_000, trim_whitespace=True)

    def validate_role(self, value: str) -> str:
        if value not in {"user", "assistant"}:
            raise serializers.ValidationError("Role must be user or assistant.")
        return value


class AssistantRequestSerializer(serializers.Serializer[Any]):
    message = serializers.CharField(max_length=2_000, trim_whitespace=True)
    history = ConversationMessageSerializer(many=True, required=False, default=list)

    def validate_history(self, value: list[dict[str, str]]) -> list[dict[str, str]]:
        if len(value) > 6:
            raise serializers.ValidationError("Keep at most the six most recent messages.")
        return value


class AssistantSourceSerializer(serializers.Serializer[Any]):
    type = serializers.CharField()
    label = serializers.CharField()  # type: ignore[assignment]
    detail = serializers.CharField(required=False)


class AssistantLinkSerializer(serializers.Serializer[Any]):
    label = serializers.CharField()  # type: ignore[assignment]
    url = serializers.CharField()


class AssistantResponseSerializer(serializers.Serializer[Any]):
    answer = serializers.CharField()
    sources = AssistantSourceSerializer(many=True)
    links = AssistantLinkSerializer(many=True)
    suggestions = serializers.ListField(child=serializers.CharField())
