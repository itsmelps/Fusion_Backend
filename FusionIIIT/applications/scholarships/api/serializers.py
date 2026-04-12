from rest_framework import serializers

from applications.scholarships.models import Award_and_scholarship


class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award_and_scholarship
        fields = ('id', 'award_name', 'catalog')


class CatalogUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    catalog = serializers.CharField(allow_blank=True)


class PreviousWinnersRequestSerializer(serializers.Serializer):
    programme = serializers.CharField()
    batch = serializers.IntegerField()
    award_id = serializers.IntegerField()


class IdStatusSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    status = serializers.CharField()


class GoldDecisionSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    action = serializers.ChoiceField(choices=('accept', 'reject'))
