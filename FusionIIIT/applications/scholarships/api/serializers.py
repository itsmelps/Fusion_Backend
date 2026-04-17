from rest_framework import serializers

from applications.scholarships.models import Award_and_scholarship


class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award_and_scholarship
        fields = ('id', 'award_name', 'catalog', 'publish_flag', 'version', 'cpi_cutoff', 'income_ceiling', 'eligible_programme')


class CatalogUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    catalog = serializers.CharField(allow_blank=True)
    publish = serializers.BooleanField(required=False, allow_null=True)


class PreviousWinnersRequestSerializer(serializers.Serializer):
    programme = serializers.CharField()
    batch = serializers.IntegerField()
    award_id = serializers.IntegerField()


class IdStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()


class GoldDecisionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=('accept', 'reject', 'forward', 'ask_info'))
    note = serializers.CharField(required=False, allow_blank=True)


class ApplicationNoteSerializer(serializers.Serializer):
    id = serializers.IntegerField(read_only=True)
    note = serializers.CharField()
    created_at = serializers.DateTimeField(read_only=True)
    author_name = serializers.CharField(read_only=True)
    is_read = serializers.BooleanField(read_only=True)
