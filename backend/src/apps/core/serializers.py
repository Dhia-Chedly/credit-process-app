from rest_framework import serializers


class LiveHealthSerializer(serializers.Serializer[dict[str, str]]):
    service = serializers.CharField()
    status = serializers.ChoiceField(choices=("ok",))


class ReadyHealthSerializer(LiveHealthSerializer):
    database = serializers.ChoiceField(choices=("ok", "unavailable"))
    status = serializers.ChoiceField(choices=("ok", "error"))
