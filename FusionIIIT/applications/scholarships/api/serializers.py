from rest_framework import serializers

from applications.scholarships.models import (
    Award_and_scholarship, 
    Mcm, 
    Director_gold, 
    Director_silver, 
    Proficiency_dm
)


class AwardSerializer(serializers.ModelSerializer):
    class Meta:
        model = Award_and_scholarship
        fields = ('id', 'award_name', 'catalog', 'publish_flag', 'version', 'cpi_cutoff', 'income_ceiling', 'eligible_programme')


class CatalogUpdateSerializer(serializers.Serializer):
    id = serializers.IntegerField()
    catalog = serializers.CharField(allow_blank=True)
    award_name = serializers.CharField(required=False, allow_blank=True)
    cpi_cutoff = serializers.FloatField(required=False, allow_null=True)
    income_ceiling = serializers.IntegerField(required=False, allow_null=True)
    eligible_programme = serializers.CharField(required=False, allow_blank=True)
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


class McmSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.id.user.get_full_name', read_only=True)
    type_name = serializers.CharField(source='award_id.award_name', read_only=True)

    class Meta:
        model = Mcm
        fields = '__all__'


class GoldSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.id.user.get_full_name', read_only=True)
    type_name = serializers.CharField(source='award_id.award_name', read_only=True)

    class Meta:
        model = Director_gold
        fields = '__all__'


class SilverSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.id.user.get_full_name', read_only=True)
    type_name = serializers.CharField(source='award_id.award_name', read_only=True)

    class Meta:
        model = Director_silver
        fields = '__all__'


class PDMSerializer(serializers.ModelSerializer):
    student_name = serializers.CharField(source='student.id.user.get_full_name', read_only=True)
    type_name = serializers.CharField(source='award_id.award_name', read_only=True)

    class Meta:
        model = Proficiency_dm
        fields = '__all__'
