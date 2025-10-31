from rest_framework import serializers
from .models import Marker, EntryPassword , Invite
from django.contrib.auth import get_user_model

User = get_user_model()

class EntryPasswordSerializer(serializers.Serializer):
    password = serializers.CharField(required=True, min_length=8)

class LoginSerializer(serializers.Serializer):
    username = serializers.CharField()
    password = serializers.CharField()

    def to_representation(self, instance):
        ret = super().to_representation(instance)
        ret.pop('password', None)
        return ret


class RegisterSerializer(serializers.ModelSerializer):
    email = serializers.EmailField(validators=[])

    class Meta:
        model = User
        fields = ('id', 'email', 'username', 'password')
        extra_kwargs = {'password': {'write_only': True}}

    def validate_email(self, value):
        if not User.objects.filter(email=value).exists():
            raise serializers.ValidationError("Email not registered.")
        return value

    def create(self, validated_data):
        user = User.objects.get(email=validated_data['email'])
        user.username = validated_data.get('username', user.username)
        user.set_password(validated_data['password'])
        user.save()
        return user

class MarkerSerializer(serializers.ModelSerializer):
    class Meta:
        model = Marker
        fields = [
            'id', 
            'name', 
            'lat', 
            'lng', 
            'user',
            'image',
            'created_at'
        ]

        extra_kwargs = {
            'user': {'write_only': True, 'required': False}
        }

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ['id', 'username', 'role']